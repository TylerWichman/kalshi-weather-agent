"""Data collector for the non-weather day-trading candidates.

The site-wide survey (scripts/site_liquidity.py) ranked series from a single 24h
snapshot. This module collects what a pre-registered test of any candidate would
need, from Kalshi's own API, into data/candidates.sqlite:

    volume    settled-market volume per series per day over N days -- turns the
              one-day snapshot into a distribution (cheap, any series)
    history   every settled market of each candidate series (strikes, result,
              expiration value, volume), candles over each market's life, and
              trade prints where the API serves them
    books     forward order-book snapshots of near-expiry open markets. Kalshi
              serves no historical book, so this is the only data that cannot be
              backfilled; every missed run is lost for good

## API behaviour this relies on (verified 2026-09-24)

- Live/historical split at `/historical/cutoff` (2026-07-25). Markets settled
  before it come only from `/historical/markets`, after it only from `/markets`.
  Both list newest-first by close_time, which is what lets the sweep stop early.
  `/historical/markets` ignores `min_close_ts`, so the date bound is applied
  client-side.
- Event-level candles (`/series/{s}/events/{e}/candlesticks`) return every
  market in one call but cap the response at ~5,000 candles and signal it only
  through `adjusted_end_ts`. Windows are chunked so each call fits; a chunk that
  still comes back truncated is re-requested from `adjusted_end_ts`.
  There is no historical event-candle route, so historical markets are fetched
  per market, skipping zero-volume strikes.
- `/markets/trades?ticker=` works only post-cutoff (see src/history.py).
- Contract volume overstates money traded on deep out-of-the-money strikes:
  in KXBTCD-26SEP2408 the busiest strike (244k contracts) traded at 1c. Candles
  carry a mean traded price, so dollar volume is stored alongside contracts.

Usage:
    python -m src.candidates volume  [--days 30] [--series A,B]
    python -m src.candidates history [--series A,B] [--days N] [--no-trades]
    python -m src.candidates books
    python -m src.candidates status
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

from .history import get, _num, _cents, cutoff_ts, _cutoff_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "candidates.sqlite")
SURVEY = os.path.join(ROOT, "data", "site_liquidity.json")

# Per-series collection settings. `days` bounds the history sweep; `interval`
# is the candle period in minutes; `trade_days` bounds trade prints.
#
# Crypto (KXBTCD, KXETHD, KXETH) is deliberately excluded despite being the
# largest short-dated volume on the site: it settles on a live, heavily arbitraged
# spot index, the most researched market there is, and a forecasting edge there
# is the least plausible of any candidate.
CANDIDATES = {
    "KXRAIN":    dict(days=400, interval=60, trade_days=400),
    "KXWTI":     dict(days=120, interval=60, trade_days=120),
    "KXNATGASW": dict(days=400, interval=60, trade_days=400),
}

# Books: only markets expiring within this many hours, and only strikes with a
# live two-sided-ish quote. Dead 1c/99c strikes carry no information.
BOOK_HORIZON_H = 30
BOOK_HORIZON_OVERRIDE = {"KXNATGASW": 7 * 24}   # weekly contract, traded all week
BOOK_DEPTH = 10
BOOK_QUOTE_BAND = (0.03, 0.97)   # on the quote midpoint

EVENT_CANDLE_CAP = 4500   # stay under the ~5,000-candle response cap
PAUSE = 0.06              # ~15 req/s, under the basic-tier read limit

SCHEMA = """
CREATE TABLE IF NOT EXISTS markets (
    ticker          TEXT PRIMARY KEY,
    series_ticker   TEXT NOT NULL,
    event_ticker    TEXT NOT NULL,
    strike_type     TEXT,
    floor_strike    REAL,
    cap_strike      REAL,
    open_time       TEXT,
    close_time      TEXT,
    result          TEXT,
    expiration_value TEXT,            -- the settled underlying (e.g. BRTI average)
    volume          REAL,
    open_interest   REAL,
    last_price      INTEGER,          -- cents
    tier            TEXT,             -- live | historical
    loaded_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_m_event ON markets(event_ticker);
CREATE INDEX IF NOT EXISTS ix_m_series_close ON markets(series_ticker, close_time);

CREATE TABLE IF NOT EXISTS candles (
    ticker          TEXT NOT NULL,
    period_ts       INTEGER NOT NULL,
    interval_min    INTEGER NOT NULL,
    yes_bid_open    INTEGER, yes_bid_close INTEGER, yes_bid_low INTEGER,
    yes_ask_open    INTEGER, yes_ask_close INTEGER, yes_ask_high INTEGER,
    price_open      INTEGER, price_high INTEGER, price_low INTEGER,
    price_close     INTEGER, price_mean REAL,
    volume          REAL,
    open_interest   REAL,
    PRIMARY KEY (ticker, period_ts, interval_min)
);

CREATE TABLE IF NOT EXISTS trades (
    trade_id        TEXT PRIMARY KEY,
    ticker          TEXT NOT NULL,
    created_time    TEXT NOT NULL,
    yes_price       INTEGER,
    count           REAL,
    taker_side      TEXT,
    taker_book_side TEXT,
    is_block        INTEGER
);
CREATE INDEX IF NOT EXISTS ix_t_ticker ON trades(ticker, created_time);

CREATE TABLE IF NOT EXISTS books (
    ticker          TEXT NOT NULL,
    series_ticker   TEXT NOT NULL,
    snap_ts         INTEGER NOT NULL,
    close_time      TEXT,
    yes_bid         INTEGER, yes_ask INTEGER,
    yes_levels      TEXT,             -- JSON [[price_cents, size], ...] best first
    no_levels       TEXT,
    PRIMARY KEY (ticker, snap_ts)
);
CREATE INDEX IF NOT EXISTS ix_b_series ON books(series_ticker, snap_ts);

CREATE TABLE IF NOT EXISTS daily_volume (
    series_ticker   TEXT NOT NULL,
    day             TEXT NOT NULL,    -- UTC date of close
    n_markets       INTEGER,
    volume          REAL,
    PRIMARY KEY (series_ticker, day)
);

CREATE TABLE IF NOT EXISTS load_log (
    event_ticker    TEXT PRIMARY KEY,
    series_ticker   TEXT NOT NULL,
    loaded_at       TEXT NOT NULL,
    n_markets       INTEGER,
    n_candles       INTEGER,
    n_trades        INTEGER,
    tier            TEXT
);
"""


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts(iso):
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()) if iso else None


def fnum(d, *names):
    v = _num(d, *names)
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=120)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


# --------------------------------------------------------------------------- #
# Market enumeration

def settled_markets(series_ticker, since_ts):
    """Every settled market of a series closing at or after since_ts, both tiers.

    Both routes list newest-first, so pagination stops at the first page that
    reaches past since_ts.
    """
    out = []
    routes = [(f"/markets?series_ticker={series_ticker}&status=settled&limit=1000"
               f"&min_close_ts={since_ts}", "live")]
    if since_ts < cutoff_ts():
        routes.append((f"/historical/markets?series_ticker={series_ticker}&limit=1000",
                       "historical"))
    for base, tier in routes:
        cur = None
        while True:
            r = get(base + (f"&cursor={cur}" if cur else ""))
            batch = (r or {}).get("markets", [])
            done = False
            for m in batch:
                ct = ts(m.get("close_time"))
                if ct is None or ct < since_ts:
                    done = True
                    continue
                out.append((m, tier))
            cur = (r or {}).get("cursor")
            if done or not cur or not batch:
                break
            time.sleep(PAUSE)
    # A market can straddle the cutoff listing briefly; keep one copy.
    seen, uniq = set(), []
    for m, tier in out:
        if m["ticker"] not in seen:
            seen.add(m["ticker"])
            uniq.append((m, tier))
    return uniq


def market_row(m, series_ticker, tier):
    return (m["ticker"], series_ticker, m.get("event_ticker"), m.get("strike_type"),
            fnum(m, "floor_strike"), fnum(m, "cap_strike"),
            m.get("open_time"), m.get("close_time"), m.get("result"),
            m.get("expiration_value"),
            fnum(m, "volume") or 0.0, fnum(m, "open_interest") or 0.0,
            _cents(_num(m, "last_price")), tier, utcnow())


# --------------------------------------------------------------------------- #
# Candles

def candle_row(ticker, interval, c):
    bid, ask, px = c.get("yes_bid") or {}, c.get("yes_ask") or {}, c.get("price") or {}
    return (ticker, c.get("end_period_ts"), interval,
            _cents(_num(bid, "open")), _cents(_num(bid, "close")), _cents(_num(bid, "low")),
            _cents(_num(ask, "open")), _cents(_num(ask, "close")), _cents(_num(ask, "high")),
            _cents(_num(px, "open")), _cents(_num(px, "high")), _cents(_num(px, "low")),
            _cents(_num(px, "close")),
            (fnum(px, "mean") * 100) if fnum(px, "mean") is not None else None,
            fnum(c, "volume") or 0.0, fnum(c, "open_interest") or 0.0)


def event_candles_live(series_ticker, event_ticker, n_markets, start, end, interval):
    """All markets of one live event, chunked under the response cap."""
    span = max(interval * 60, (EVENT_CANDLE_CAP // max(n_markets, 1)) * interval * 60)
    rows, t0 = [], start
    while t0 < end:
        t1 = min(end, t0 + span)
        r = get(f"/series/{series_ticker}/events/{event_ticker}/candlesticks"
                f"?start_ts={t0}&end_ts={t1}&period_interval={interval}")
        if not r:
            break
        for tk, cs in zip(r.get("market_tickers", []), r.get("market_candlesticks", [])):
            rows += [candle_row(tk, interval, c) for c in cs or []]
        adj = r.get("adjusted_end_ts")
        # Truncated: resume from where the server stopped, not where we asked.
        t0 = adj if adj and t0 < adj < t1 else t1
        time.sleep(PAUSE)
    return rows


def market_candles_hist(ticker, start, end, interval):
    r = get(f"/historical/markets/{ticker}/candlesticks"
            f"?start_ts={start}&end_ts={end}&period_interval={interval}")
    return [candle_row(ticker, interval, c) for c in (r or {}).get("candlesticks", [])]


# --------------------------------------------------------------------------- #
# Trades

def trade_prints(ticker, max_pages=200):
    out, cur = [], None
    for _ in range(max_pages):
        r = get(f"/markets/trades?ticker={ticker}&limit=1000"
                + (f"&cursor={cur}" if cur else ""))
        batch = (r or {}).get("trades", [])
        out += batch
        cur = (r or {}).get("cursor")
        if not cur or not batch:
            break
        time.sleep(PAUSE)
    return out


def trade_row(t):
    return (t.get("trade_id"), t.get("ticker"), t.get("created_time"),
            _cents(_num(t, "yes_price")), fnum(t, "count") or 0.0,
            t.get("taker_side"), t.get("taker_book_side"),
            1 if t.get("is_block_trade") else 0)


# --------------------------------------------------------------------------- #
# Commands

def cmd_history(conn, series_list, days_override, with_trades):
    cutoff_ts()
    now = int(time.time())
    print(f"cutoff={_cutoff_cache.get('raw')}  (older -> /historical, newer -> live)\n")
    for st in series_list:
        cfg = CANDIDATES.get(st, dict(days=30, interval=60, trade_days=30))
        days = days_override or cfg["days"]
        interval = cfg["interval"]
        since = now - days * 86400
        trade_since = now - cfg["trade_days"] * 86400
        t_start = time.time()

        mk = settled_markets(st, since)
        by_event = defaultdict(list)
        for m, tier in mk:
            by_event[m.get("event_ticker")].append((m, tier))
        conn.executemany("INSERT OR REPLACE INTO markets VALUES "
                         "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         [market_row(m, st, tier) for m, tier in mk])
        conn.commit()

        done = {r[0] for r in conn.execute(
            "SELECT event_ticker FROM load_log WHERE series_ticker=?", (st,))}
        todo = sorted(e for e in by_event if e not in done)
        print(f"{st:<11} {len(mk):>7,} settled markets in {len(by_event):,} events "
              f"over {days}d; {len(todo):,} events to load ({interval}m candles)", flush=True)

        n_cd = n_tr = 0
        for i, ev in enumerate(todo, 1):
            ms = by_event[ev]
            tier = ms[0][1]
            opens = [ts(m.get("open_time")) for m, _ in ms if m.get("open_time")]
            closes = [ts(m.get("close_time")) for m, _ in ms if m.get("close_time")]
            if not closes:
                continue
            end = max(closes)
            start = max(min(opens) if opens else end - 86400, end - 7 * 86400)
            traded = [m for m, _ in ms if (fnum(m, "volume") or 0) > 0]

            if tier == "live":
                rows = event_candles_live(st, ev, len(ms), start, end, interval)
            else:
                rows = []
                for m in traded:
                    rows += market_candles_hist(m["ticker"], start, end, interval)
                    time.sleep(PAUSE)
            conn.executemany("INSERT OR REPLACE INTO candles VALUES "
                             "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)

            trows = []
            if with_trades and tier == "live" and end >= trade_since:
                for m in traded:
                    trows += [trade_row(t) for t in trade_prints(m["ticker"])]
                conn.executemany("INSERT OR REPLACE INTO trades VALUES (?,?,?,?,?,?,?,?)",
                                 trows)

            conn.execute("INSERT OR REPLACE INTO load_log VALUES (?,?,?,?,?,?,?)",
                         (ev, st, utcnow(), len(ms), len(rows), len(trows), tier))
            conn.commit()
            n_cd += len(rows)
            n_tr += len(trows)
            if i % 50 == 0 or i == len(todo):
                el = time.time() - t_start
                print(f"    {i:>5}/{len(todo)} events  {n_cd:>9,} candles  "
                      f"{n_tr:>9,} trades  {el/60:5.1f} min", flush=True)


def cmd_volume(conn, series_list, days):
    """Settled volume per series per UTC day -- the multi-day view of the survey."""
    since = int(time.time()) - days * 86400
    cutoff_ts()
    for st in series_list:
        per = defaultdict(lambda: [0, 0.0])
        for m, _ in settled_markets(st, since):
            d = (m.get("close_time") or "")[:10]
            per[d][0] += 1
            per[d][1] += fnum(m, "volume") or 0.0
        conn.executemany("INSERT OR REPLACE INTO daily_volume VALUES (?,?,?,?)",
                         [(st, d, n, v) for d, (n, v) in per.items()])
        conn.commit()
        vols = sorted(v for _, v in per.values())
        med = vols[len(vols) // 2] if vols else 0
        print(f"  {st:<24}{len(per):>4} days   median {med:>12,.0f}   "
              f"min {vols[0] if vols else 0:>12,.0f}   max {vols[-1] if vols else 0:>12,.0f}",
              flush=True)


def book_levels(side):
    """Kalshi books list bids ascending; return best-first [[cents, size], ...]."""
    lv = []
    for p, q in side or []:
        lv.append([_cents(p), float(q)])
    lv.sort(key=lambda x: -x[0])
    return lv[:BOOK_DEPTH]


def cmd_books(conn, series_list):
    now = int(time.time())
    n_snap = 0
    for st in series_list:
        hours = BOOK_HORIZON_OVERRIDE.get(st, BOOK_HORIZON_H)
        horizon = now + hours * 3600
        cur, mk = None, []
        while True:
            r = get(f"/markets?series_ticker={st}&status=open&limit=1000&max_close_ts={horizon}"
                    + (f"&cursor={cur}" if cur else ""))
            batch = (r or {}).get("markets", [])
            mk += batch
            cur = (r or {}).get("cursor")
            if not cur or not batch:
                break
        lo, hi = BOOK_QUOTE_BAND
        live = [m for m in mk
                if lo <= ((fnum(m, "yes_bid") or 0) + (fnum(m, "yes_ask") or 1)) / 2 <= hi]
        rows = []
        for m in live:
            r = get(f"/markets/{m['ticker']}/orderbook?depth={BOOK_DEPTH}")
            ob = (r or {}).get("orderbook_fp") or (r or {}).get("orderbook") or {}
            yes = book_levels(ob.get("yes_dollars") or ob.get("yes"))
            no = book_levels(ob.get("no_dollars") or ob.get("no"))
            rows.append((m["ticker"], st, now, m.get("close_time"),
                         yes[0][0] if yes else None,
                         (100 - no[0][0]) if no else None,
                         json.dumps(yes), json.dumps(no)))
            time.sleep(PAUSE)
        conn.executemany("INSERT OR REPLACE INTO books VALUES (?,?,?,?,?,?,?,?)", rows)
        conn.commit()
        n_snap += len(rows)
        print(f"  {st:<11} {len(mk):>4} open <= {hours}h, {len(rows):>4} quoted -> snapped")
    print(f"{utcnow()}  {n_snap} books")


def cmd_status(conn):
    print(f"\n{'series':<12}{'markets':>9}{'events':>8}{'loaded':>8}{'candles':>11}"
          f"{'trades':>10}{'books':>9}{'first close':>13}{'last close':>13}")
    print("-" * 93)
    for st in sorted({r[0] for r in conn.execute("SELECT DISTINCT series_ticker FROM markets")}
                     | {r[0] for r in conn.execute("SELECT DISTINCT series_ticker FROM books")}):
        mk, ev, d0, d1 = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT event_ticker), MIN(close_time), MAX(close_time) "
            "FROM markets WHERE series_ticker=?", (st,)).fetchone()
        ld, cd, tr = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(n_candles),0), COALESCE(SUM(n_trades),0) "
            "FROM load_log WHERE series_ticker=?", (st,)).fetchone()
        bk = conn.execute("SELECT COUNT(*) FROM books WHERE series_ticker=?", (st,)).fetchone()[0]
        print(f"{st:<12}{mk:>9,}{ev:>8,}{ld:>8,}{cd:>11,}{tr:>10,}{bk:>9,}"
              f"{(d0 or '-')[:10]:>13}{(d1 or '-')[:10]:>13}")
    print()


def survey_series(top):
    """Top non-sports series from the site survey, for the volume sweep."""
    d = json.load(open(SURVEY))
    meta = d["meta"]
    agg = defaultdict(float)
    for r in d["rows"]:
        if meta.get(r["series"], {}).get("category") != "Sports":
            agg[r["series"]] += r["v24"]
    return [s for s, _ in sorted(agg.items(), key=lambda x: -x[1])[:top]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["history", "volume", "books", "status"])
    ap.add_argument("--series", help="comma-separated series (default: the candidates)")
    ap.add_argument("--days", type=int, help="override the per-series history window")
    ap.add_argument("--top", type=int, default=30,
                    help="volume: take the top N non-sports series from the survey")
    ap.add_argument("--no-trades", action="store_true")
    args = ap.parse_args()

    conn = connect()
    series = args.series.split(",") if args.series else list(CANDIDATES)
    if args.cmd == "history":
        cmd_history(conn, series, args.days, not args.no_trades)
        cmd_status(conn)
    elif args.cmd == "volume":
        if not args.series:
            series = survey_series(args.top)
        print(f"Settled volume per UTC day, last {args.days or 30} days:\n")
        cmd_volume(conn, series, args.days or 30)
    elif args.cmd == "books":
        cmd_books(conn, series)
    else:
        cmd_status(conn)
    conn.close()


if __name__ == "__main__":
    main()
