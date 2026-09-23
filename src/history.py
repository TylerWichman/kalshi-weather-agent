"""Historical Kalshi market-data loader (spec v3 Phase 2, economic half).

Pulls settled weather ladders with their price history so the 24-48h edge can be
backtested against real prices, rather than waiting for the live pipeline to
accumulate.

## Routing across the live/historical cutoff

Kalshi partitions exchange data. `GET /historical/cutoff` returns
`market_settled_ts` (currently 2026-07-24); markets settled before it are served
only by `/historical/*`, markets after it only by the live endpoints. Verified
both directions -- each route returns 6 markets on its own side and 0 on the
other. This module routes per market and never assumes one window.

**The two tiers use different field names**, which is a silent-corruption trap:

    live        yes_bid.close_dollars   volume_fp   open_interest_fp
    historical  yes_bid.close           volume      open_interest

Reading historical rows with live names yields `None` everywhere, which looks
like "no quotes" rather than an error. `_num()` accepts either spelling.

## Trade-level data is NOT available pre-cutoff

`/markets/trades?ticker=` works only for post-cutoff markets. `/historical/trades`
accepts **no ticker filter at all** -- `ticker` 404s, and `market_ticker`,
`event_ticker` and `series_ticker` are silently ignored and return unfiltered
results. Its only real filters are `min_ts`/`max_ts`, and the firehose runs
~1000 trades/hour exchange-wide of which roughly **2 per 1000 are weather**.
Scanning it for one market's prints is not practical.

Consequence, and it is the main limitation of this backtest: for everything before
2026-07-24 we have **candles only**. Candles do carry bid/ask OHLC plus traded
price OHLC and volume, which is enough for the conservative fill model in
`src/fillsim.py` -- but queue position is unobservable either way. See that module.

Usage:
    python -m src.history load --series KXHIGHNY --days 200
    python -m src.history load --all
    python -m src.history status
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from . import db, kalshi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHLIST = os.path.join(ROOT, "config", "watchlist.json")
DB_PATH = os.path.join(ROOT, "data", "history.sqlite")

BASE = "https://api.elections.kalshi.com/trade-api/v2"
UA = {"User-Agent": "kalshi-weather-agent history (tylerwichman13@gmail.com)"}

# Section 8 watchlist. LAX and NYC are still LOADED -- the sizing exclusion in
# src/risk.py is a trading gate, not a data gate, and they must keep being scored.
WATCH_SERIES = [
    "KXHIGHLAX", "KXHIGHMIA", "KXHIGHNY", "KXHIGHAUS",
    "KXHIGHTATL", "KXHIGHCHI", "KXHIGHTDAL", "KXHIGHPHIL",
    "KXHIGHTHOU", "KXHIGHTOKC", "KXHIGHDEN", "KXHIGHTDC",
]

# Trading in a daily-high ladder is meaningful from roughly three days out.
LOAD_HOURS_BEFORE_CLOSE = 72

SCHEMA = """
CREATE TABLE IF NOT EXISTS hist_markets (
    ticker         TEXT PRIMARY KEY,
    series_ticker  TEXT NOT NULL,
    event_ticker   TEXT NOT NULL,
    city           TEXT,
    nws_station    TEXT,
    target_date    TEXT,
    strike_type    TEXT,
    bucket_low_f   REAL,
    bucket_high_f  REAL,
    result         TEXT,              -- yes | no
    close_time     TEXT,
    volume         REAL,
    open_interest  REAL,
    tier           TEXT,              -- live | historical (which route served it)
    loaded_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_hm_event ON hist_markets(event_ticker);
CREATE INDEX IF NOT EXISTS ix_hm_date  ON hist_markets(target_date);

CREATE TABLE IF NOT EXISTS hist_candles (
    ticker         TEXT NOT NULL,
    period_ts      INTEGER NOT NULL,   -- end of the candle period, unix seconds
    interval_min   INTEGER NOT NULL,
    yes_bid_close  INTEGER,            -- cents
    yes_ask_close  INTEGER,
    yes_bid_low    INTEGER,
    yes_ask_high   INTEGER,
    price_open     INTEGER,            -- traded price OHLC (null if no trades)
    price_high     INTEGER,
    price_low      INTEGER,
    price_close    INTEGER,
    volume         REAL,
    open_interest  REAL,
    PRIMARY KEY (ticker, period_ts, interval_min)
);
CREATE INDEX IF NOT EXISTS ix_hc_ticker ON hist_candles(ticker, period_ts);

CREATE TABLE IF NOT EXISTS hist_trades (
    trade_id       TEXT PRIMARY KEY,
    ticker         TEXT NOT NULL,
    created_time   TEXT NOT NULL,
    yes_price      INTEGER,
    count          REAL,
    taker_side     TEXT,
    taker_book_side TEXT
);
CREATE INDEX IF NOT EXISTS ix_ht_ticker ON hist_trades(ticker, created_time);

CREATE TABLE IF NOT EXISTS load_log (
    series_ticker TEXT NOT NULL,
    event_ticker  TEXT NOT NULL,
    loaded_at     TEXT NOT NULL,
    n_markets     INTEGER,
    n_candles     INTEGER,
    n_trades      INTEGER,
    note          TEXT,
    PRIMARY KEY (event_ticker)
);
"""


def get(path, retries=4):
    delay = 1.5
    for attempt in range(retries):
        try:
            req = urllib.request.Request(BASE + path, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as f:
                return json.loads(f.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            if attempt == retries - 1:
                raise
        except Exception:
            if attempt == retries - 1:
                raise
        time.sleep(delay)
        delay *= 2
    return None


def _num(d, *names):
    """Read a value that may carry a `_dollars`/`_fp` suffix or none at all."""
    if not isinstance(d, dict):
        return None
    for n in names:
        for key in (n, n + "_dollars", n + "_fp"):
            if key in d and d[key] not in (None, ""):
                return d[key]
    return None


def _cents(v):
    return None if v in (None, "") else int(round(float(v) * 100))


_cutoff_cache = {}


def cutoff_ts():
    """Unix seconds for `market_settled_ts`; markets older than this are historical."""
    if "ts" not in _cutoff_cache:
        c = get("/historical/cutoff") or {}
        raw = c.get("market_settled_ts")
        _cutoff_cache["ts"] = (
            int(datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp())
            if raw else 0
        )
        _cutoff_cache["raw"] = raw
    return _cutoff_cache["ts"]


def settled_events(series_ticker):
    out, cur = [], None
    for _ in range(30):
        r = get(f"/events?series_ticker={series_ticker}&limit=200&status=settled"
                + (f"&cursor={cur}" if cur else ""))
        if not r:
            break
        out += [e["event_ticker"] for e in r.get("events", [])]
        cur = r.get("cursor")
        if not cur:
            break
    # Only the KX-era series; the legacy HIGH* predecessors are delisted.
    return sorted({e for e in out if e.startswith(series_ticker + "-")})


def markets_for_event(event_ticker):
    """Route by cutoff. Try historical first, fall back to live."""
    for route, tier in (("/historical/markets", "historical"), ("/markets", "live")):
        r = get(f"{route}?event_ticker={event_ticker}")
        ms = (r or {}).get("markets", [])
        if ms:
            return ms, tier
    return [], None


def candles(series_ticker, ticker, start_ts, end_ts, interval_min, tier):
    """Candlesticks, routed by tier, with both field spellings normalized."""
    paths = ([f"/historical/markets/{ticker}/candlesticks"]
             if tier == "historical" else
             [f"/series/{series_ticker}/markets/{ticker}/candlesticks"])
    for p in paths:
        r = get(f"{p}?start_ts={start_ts}&end_ts={end_ts}&period_interval={interval_min}")
        if r and r.get("candlesticks"):
            return r["candlesticks"]
    return []


def normalize_candle(c):
    bid, ask, price = c.get("yes_bid") or {}, c.get("yes_ask") or {}, c.get("price") or {}
    return dict(
        period_ts=c.get("end_period_ts"),
        yes_bid_close=_cents(_num(bid, "close")),
        yes_ask_close=_cents(_num(ask, "close")),
        yes_bid_low=_cents(_num(bid, "low")),
        yes_ask_high=_cents(_num(ask, "high")),
        price_open=_cents(_num(price, "open")),
        price_high=_cents(_num(price, "high")),
        price_low=_cents(_num(price, "low")),
        price_close=_cents(_num(price, "close")),
        volume=float(_num(c, "volume") or 0),
        open_interest=float(_num(c, "open_interest") or 0),
    )


def trades_for(ticker, limit=1000):
    """Trade prints. Post-cutoff only -- see module docstring."""
    out, cur = [], None
    for _ in range(10):
        r = get(f"/markets/trades?ticker={ticker}&limit={limit}"
                + (f"&cursor={cur}" if cur else ""))
        if not r:
            break
        out += r.get("trades", [])
        cur = r.get("cursor")
        if not cur:
            break
    return out


def load_series(conn, series_ticker, meta, max_events, interval_min,
                with_trades=False, verbose=True):
    events = settled_events(series_ticker)[-max_events:]
    if not events:
        print(f"  {series_ticker:<13} no settled events", file=sys.stderr)
        return 0, 0, 0
    n_mk = n_cd = n_tr = 0
    skipped = 0

    for ev in events:
        if conn.execute("SELECT 1 FROM load_log WHERE event_ticker=?", (ev,)).fetchone():
            skipped += 1
            continue
        ms, tier = markets_for_event(ev)
        if not ms:
            conn.execute("INSERT OR REPLACE INTO load_log VALUES (?,?,?,?,?,?,?)",
                         (series_ticker, ev, db.utcnow(), 0, 0, 0, "no markets"))
            continue

        target = kalshi.parse_event_date(ev)
        ev_c = ev_t = 0
        for m in ms:
            t = m["ticker"]
            lo, hi = kalshi.bucket_bounds(m)
            ct = m.get("close_time")
            conn.execute(
                "INSERT OR REPLACE INTO hist_markets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (t, series_ticker, ev, meta["city"], meta["nws_station"],
                 target.isoformat() if target else None, m.get("strike_type"), lo, hi,
                 m.get("result", ""), ct,
                 float(_num(m, "volume") or 0), float(_num(m, "open_interest") or 0),
                 tier, db.utcnow()))
            n_mk += 1
            if not ct:
                continue
            end = int(datetime.fromisoformat(ct.replace("Z", "+00:00")).timestamp())
            start = end - LOAD_HOURS_BEFORE_CLOSE * 3600
            for c in candles(series_ticker, t, start, end, interval_min, tier):
                n = normalize_candle(c)
                if n["period_ts"] is None:
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO hist_candles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (t, n["period_ts"], interval_min, n["yes_bid_close"], n["yes_ask_close"],
                     n["yes_bid_low"], n["yes_ask_high"], n["price_open"], n["price_high"],
                     n["price_low"], n["price_close"], n["volume"], n["open_interest"]))
                ev_c += 1
            # Trades exist only post-cutoff and run ~8k per market, so they are
            # opt-in: pulled for a subset to validate the fill model against real
            # prints (src/fillsim.py), not for the bulk load.
            if with_trades and tier == "live":
                for tr in trades_for(t):
                    conn.execute(
                        "INSERT OR REPLACE INTO hist_trades VALUES (?,?,?,?,?,?,?)",
                        (tr.get("trade_id"), t, tr.get("created_time"),
                         _cents(_num(tr, "yes_price")), float(_num(tr, "count") or 0),
                         tr.get("taker_side"), tr.get("taker_book_side")))
                    ev_t += 1
            time.sleep(0.08)

        n_cd += ev_c
        n_tr += ev_t
        conn.execute("INSERT OR REPLACE INTO load_log VALUES (?,?,?,?,?,?,?)",
                     (series_ticker, ev, db.utcnow(), len(ms), ev_c, ev_t, tier))
        conn.commit()

    if verbose:
        print(f"  {series_ticker:<13} {len(events):>4} events "
              f"({skipped} cached) -> {n_mk:>5} mkts {n_cd:>7} candles {n_tr:>6} trades")
    return n_mk, n_cd, n_tr


def status(conn):
    print(f"\ncutoff (market_settled_ts): {_cutoff_cache.get('raw', '?')}\n")
    print(f"{'series':<14}{'events':>8}{'markets':>9}{'candles':>10}{'trades':>9}"
          f"{'earliest':>13}{'latest':>13}")
    print("-" * 76)
    for r in conn.execute(
        """SELECT m.series_ticker, COUNT(DISTINCT m.event_ticker) ev, COUNT(DISTINCT m.ticker) mk,
                  MIN(m.target_date) d0, MAX(m.target_date) d1
           FROM hist_markets m GROUP BY m.series_ticker ORDER BY m.series_ticker"""):
        cd = conn.execute(
            "SELECT COUNT(*) FROM hist_candles WHERE ticker IN "
            "(SELECT ticker FROM hist_markets WHERE series_ticker=?)", (r[0],)).fetchone()[0]
        tr = conn.execute(
            "SELECT COUNT(*) FROM hist_trades WHERE ticker IN "
            "(SELECT ticker FROM hist_markets WHERE series_ticker=?)", (r[0],)).fetchone()[0]
        print(f"{r[0]:<14}{r[1]:>8}{r[2]:>9}{cd:>10}{tr:>9}{r[3] or '-':>13}{r[4] or '-':>13}")
    print("-" * 76)
    tot = conn.execute("SELECT COUNT(*) FROM hist_markets").fetchone()[0]
    tc = conn.execute("SELECT COUNT(*) FROM hist_candles").fetchone()[0]
    tt = conn.execute("SELECT COUNT(*) FROM hist_trades").fetchone()[0]
    print(f"{'TOTAL':<14}{'':>8}{tot:>9}{tc:>10}{tt:>9}")
    by_tier = dict(conn.execute("SELECT tier, COUNT(*) FROM hist_markets GROUP BY tier"))
    print(f"\nby route: {by_tier}")
    print("Trade prints exist only for post-cutoff markets; see module docstring.\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["load", "status"])
    ap.add_argument("--series", help="one series ticker (default: whole watchlist)")
    ap.add_argument("--days", type=int, default=200, help="most recent N settled events")
    ap.add_argument("--interval", type=int, default=60, choices=[1, 60, 1440],
                    help="candle period in minutes (1 = finest, much slower)")
    ap.add_argument("--trades", action="store_true",
                    help="also pull trade prints (post-cutoff only, ~8k/market)")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    import sqlite3
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.executescript(SCHEMA)

    if args.cmd == "status":
        cutoff_ts()
        status(conn)
        return

    wl = {s["series_ticker"]: s for s in json.load(open(WATCHLIST))["series"]}
    targets = [args.series] if args.series else WATCH_SERIES
    cutoff_ts()
    print(f"Loading history: {len(targets)} series, last {args.days} events each, "
          f"{args.interval}-min candles")
    print(f"cutoff={_cutoff_cache.get('raw')}  (older -> /historical, newer -> live)\n")
    for st in targets:
        meta = wl.get(st)
        if not meta:
            print(f"  {st}: not in watchlist", file=sys.stderr)
            continue
        try:
            load_series(conn, st, meta, args.days, args.interval, args.trades)
        except Exception as e:
            print(f"  {st}: ERROR {e}", file=sys.stderr)
    status(conn)
    conn.close()


if __name__ == "__main__":
    main()
