"""Data Collector Agent (spec v3 section 2.1).

Three jobs, deliberately separable because they run on different clocks:

    contracts    -- discover open ladders, verify station matching  (a few times/day)
    books        -- poll Kalshi order books                         (every 5-15 min)
    forecasts    -- NWS gridpoint + Open-Meteo ensemble             (on new model runs, ~6h)
    observations -- live station temps, the intraday truth          (every 15-30 min)

Section 2.1 says the schedule should be tied to information events rather than the
wall clock, so the scheduler (Phase 1 exit) drives these separately instead of one
monolithic pass.

Watchlist is highs-only across the top 12 cities (section 8). Lows are excluded:
7-11 cent spreads exceed any plausible edge once fees are added.

Usage:
    python -m src.collector contracts
    python -m src.collector books
    python -m src.collector forecasts
    python -m src.collector status
"""

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timezone

from . import db, kalshi, weather

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHLIST = os.path.join(ROOT, "config", "watchlist.json")

# Section 8: highs only, top 12 cities by 24h volume.
TRADING_WATCHLIST = [
    "KXHIGHLAX", "KXHIGHMIA", "KXHIGHNY", "KXHIGHAUS",
    "KXHIGHTATL", "KXHIGHCHI", "KXHIGHTDAL", "KXHIGHPHIL",
    "KXHIGHTHOU", "KXHIGHTOKC", "KXHIGHDEN", "KXHIGHTDC",
]


def load_watchlist(all_series=False):
    data = json.load(open(WATCHLIST))
    rows = data["series"]
    if not all_series:
        rows = [r for r in rows if r["series_ticker"] in TRADING_WATCHLIST]
    return rows


# ---------------------------------------------------------------- contracts

def collect_contracts(conn, watchlist, verbose=True):
    """Discover open ladders and upsert contract metadata.

    Every market is station-verified against the watchlist before it is stored.
    A mismatch is recorded as a risk event and the series is skipped rather than
    silently ingested -- section 9's station-mismatch failure is silent by nature,
    so it has to be made loud here.
    """
    run_id = db.start_run(conn, "contracts")
    n_ok = n_failed = 0
    now = db.utcnow()

    for s in watchlist:
        st = s["series_ticker"]
        try:
            meta = kalshi.series(st) or {}
            fee_type = meta.get("fee_type")
            fee_mult = meta.get("fee_multiplier")
            markets = kalshi.open_markets(st)
            if not markets:
                if verbose:
                    print(f"  {st:<13} no open markets")
                continue

            events = sorted(set(m["event_ticker"] for m in markets))
            for ev in events:
                ladder = kalshi.ladder_for_event(markets, ev)
                problems = kalshi.check_ladder_complete(ladder)
                if problems:
                    conn.execute(
                        "INSERT INTO risk_events (occurred_at, kind, ticker, reason, detail_json) "
                        "VALUES (?,?,?,?,?)",
                        (now, "blocked_trade", ev, "ladder structure invalid",
                         json.dumps(problems)),
                    )
                    if verbose:
                        print(f"  {ev:<22} LADDER PROBLEM: {problems}")

                target = kalshi.parse_event_date(ev)
                for m in ladder:
                    kalshi.verify_station(m, s["kalshi_station_id"], s["settlement_source"])
                    lo, hi = kalshi.bucket_bounds(m)
                    conn.execute(
                        """INSERT INTO contracts (
                               ticker, series_ticker, event_ticker, city, kind,
                               kalshi_station_id, nws_station, settlement_source,
                               target_date, strike_type, floor_strike, cap_strike,
                               bucket_low_f, bucket_high_f, fee_type, fee_multiplier,
                               open_time, close_time, expiration_time, status, result,
                               first_seen, last_seen)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(ticker) DO UPDATE SET
                               status=excluded.status, result=excluded.result,
                               close_time=excluded.close_time,
                               fee_type=excluded.fee_type,
                               fee_multiplier=excluded.fee_multiplier,
                               last_seen=excluded.last_seen""",
                        (m["ticker"], st, ev, s["city"], s["kind"],
                         s["kalshi_station_id"], s["nws_station"], s["settlement_source"],
                         target.isoformat() if target else None,
                         m.get("strike_type"),
                         m.get("floor_strike"), m.get("cap_strike"), lo, hi,
                         fee_type, fee_mult,
                         m.get("open_time"), m.get("close_time"), m.get("expiration_time"),
                         m.get("status"), m.get("result", ""), now, now),
                    )
                    n_ok += 1
            if verbose:
                print(f"  {st:<13} {len(events)} events, {len(markets)} markets"
                      f"  fee={fee_type}/{fee_mult}")
        except kalshi.StationMismatch as e:
            n_failed += 1
            conn.execute(
                "INSERT INTO risk_events (occurred_at, kind, ticker, reason) VALUES (?,?,?,?)",
                (now, "blocked_trade", st, f"STATION MISMATCH: {e}"),
            )
            print(f"  {st:<13} STATION MISMATCH: {e}", file=sys.stderr)
        except Exception as e:
            n_failed += 1
            print(f"  {st:<13} ERROR: {e}", file=sys.stderr)
        time.sleep(0.15)

    conn.commit()
    db.finish_run(conn, run_id, n_ok, n_failed)
    return n_ok, n_failed


# -------------------------------------------------------------------- books

def collect_books(conn, verbose=True):
    """Poll order books for every open contract. Append-only."""
    run_id = db.start_run(conn, "books")
    n_ok = n_failed = 0

    rows = conn.execute(
        "SELECT ticker FROM contracts WHERE status='active' ORDER BY event_ticker, bucket_low_f"
    ).fetchall()

    for row in rows:
        ticker = row["ticker"]
        try:
            m = kalshi.get(f"/markets/{ticker}")
            market = (m or {}).get("market", {})
            book = kalshi.orderbook(ticker)

            # Kalshi returns each side as [[price_dollars, size], ...] where the
            # `no` side is quoted in no-price. Both are stored as given, in cents.
            def side(key):
                return [[db.dollars_to_cents(p), float(sz)] for p, sz in (book.get(key) or [])]

            conn.execute(
                """INSERT INTO market_prices (
                       ticker, observed_at, yes_bid_cents, yes_ask_cents,
                       yes_bid_size, yes_ask_size, last_price_cents,
                       volume, volume_24h, open_interest, book_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (ticker, db.utcnow(),
                 db.dollars_to_cents(market.get("yes_bid_dollars")),
                 db.dollars_to_cents(market.get("yes_ask_dollars")),
                 float(market.get("yes_bid_size_fp") or 0),
                 float(market.get("yes_ask_size_fp") or 0),
                 db.dollars_to_cents(market.get("last_price_dollars")),
                 float(market.get("volume_fp") or 0),
                 float(market.get("volume_24h_fp") or 0),
                 float(market.get("open_interest_fp") or 0),
                 json.dumps({"yes": side("yes_dollars"), "no": side("no_dollars")})),
            )
            n_ok += 1
        except Exception as e:
            n_failed += 1
            print(f"  {ticker}: {e}", file=sys.stderr)
        time.sleep(0.1)

    conn.commit()
    db.finish_run(conn, run_id, n_ok, n_failed)
    if verbose:
        print(f"  polled {n_ok} books, {n_failed} failed")
    return n_ok, n_failed


# ---------------------------------------------------------------- forecasts

def collect_forecasts(conn, watchlist, verbose=True):
    """Pull NWS gridpoint and Open-Meteo ensemble forecasts for every open target date."""
    run_id = db.start_run(conn, "forecasts")
    n_ok = n_failed = 0
    fetched = db.utcnow()

    by_station = {}
    for s in watchlist:
        by_station.setdefault(s["nws_station"], s)

    targets = conn.execute(
        "SELECT DISTINCT nws_station, target_date, kind FROM contracts "
        "WHERE status='active' AND target_date IS NOT NULL"
    ).fetchall()

    for t in targets:
        s = by_station.get(t["nws_station"])
        if not s:
            continue
        target_date = date.fromisoformat(t["target_date"])
        kind = t["kind"]
        lead = weather.lead_time_hours(target_date, s["timezone"])

        # NWS point forecast
        try:
            g = s["nws_gridpoint"]
            val, updated = weather.nws_gridpoint_forecast(
                g["office"], g["x"], g["y"], target_date, kind)
            if val is not None:
                conn.execute(
                    """INSERT OR IGNORE INTO forecast_snapshots (
                           nws_station, target_date, kind, source, model, fetched_at,
                           run_time, lead_time_hours, point_value_f, members_json, n_members)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (t["nws_station"], t["target_date"], kind, "nws_gridpoint", None,
                     fetched, updated, lead, val, None, None),
                )
                n_ok += 1
        except Exception as e:
            n_failed += 1
            print(f"  NWS {t['nws_station']} {t['target_date']}: {e}", file=sys.stderr)

        # Open-Meteo ensemble
        try:
            ens = weather.openmeteo_ensemble(
                s["lat"], s["lon"], target_date, kind, s["timezone"])
            if ens:
                conn.execute(
                    """INSERT OR IGNORE INTO forecast_snapshots (
                           nws_station, target_date, kind, source, model, fetched_at,
                           run_time, lead_time_hours, point_value_f, members_json, n_members)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (t["nws_station"], t["target_date"], kind, "openmeteo_ensemble",
                     kalshi_models(ens), fetched, None, lead, None,
                     json.dumps(ens["members"]), ens["n"]),
                )
                n_ok += 1
                if verbose:
                    print(f"  {t['nws_station']} {t['target_date']} {kind}: "
                          f"nws={val if val is not None else 'n/a'}  "
                          f"ens n={ens['n']} {ens['by_model']}  lead={lead:.1f}h")
        except Exception as e:
            n_failed += 1
            print(f"  ENS {t['nws_station']} {t['target_date']}: {e}", file=sys.stderr)

        time.sleep(0.25)

    conn.commit()
    db.finish_run(conn, run_id, n_ok, n_failed)
    return n_ok, n_failed


def kalshi_models(ens):
    return ",".join(sorted(ens["by_model"]))


# ------------------------------------------------------------- observations

def collect_observations(conn, watchlist, verbose=True):
    """Pull live station observations for every open target date.

    Added after Phase 1 measurement showed the market prices same-day contracts
    off observed data while gridded forecasts lag it by 2-4F (docs/phase1-findings.md).
    Without this the system computes enormous phantom edges against markets that
    already know the answer -- the most dangerous failure mode found so far.
    """
    run_id = db.start_run(conn, "observations")
    n_ok = n_failed = 0
    fetched = db.utcnow()

    by_station = {}
    for s in watchlist:
        by_station.setdefault(s["nws_station"], s)

    targets = conn.execute(
        "SELECT DISTINCT nws_station, target_date FROM contracts "
        "WHERE status='active' AND target_date IS NOT NULL"
    ).fetchall()

    for t in targets:
        s = by_station.get(t["nws_station"])
        if not s:
            continue
        day = date.fromisoformat(t["target_date"])
        try:
            obs = weather.station_observations(s["nws_station"], s["timezone"], day)
            for ts, temp in obs:
                conn.execute(
                    """INSERT OR IGNORE INTO station_observations
                           (nws_station, local_date, observed_at, temp_f, fetched_at)
                       VALUES (?,?,?,?,?)""",
                    (s["nws_station"], t["target_date"], ts, temp, fetched),
                )
            n_ok += 1
            if verbose and obs:
                temps = [x[1] for x in obs]
                print(f"  {s['nws_station']} {t['target_date']}: {len(obs):>3} obs  "
                      f"max so far {max(temps):.1f}F  latest {obs[0][1]:.1f}F")
        except Exception as e:
            n_failed += 1
            print(f"  OBS {t['nws_station']} {t['target_date']}: {e}", file=sys.stderr)
        time.sleep(0.2)

    conn.commit()
    db.finish_run(conn, run_id, n_ok, n_failed)
    return n_ok, n_failed


# ------------------------------------------------------------------- status

def status(conn):
    print("\n=== contracts ===")
    for r in conn.execute(
        "SELECT series_ticker, city, COUNT(DISTINCT event_ticker) ev, COUNT(*) n, "
        "MIN(target_date) d0, MAX(target_date) d1, fee_type, fee_multiplier "
        "FROM contracts WHERE status='active' GROUP BY series_ticker ORDER BY city"
    ):
        print(f"  {r['series_ticker']:<13} {r['city']:<15} {r['ev']} events "
              f"{r['n']:>3} mkts  {r['d0']}..{r['d1']}  fee={r['fee_type']}/{r['fee_multiplier']}")

    print("\n=== market_prices (append-only) ===")
    r = conn.execute(
        "SELECT COUNT(*) n, COUNT(DISTINCT ticker) t, MIN(observed_at) a, MAX(observed_at) b "
        "FROM market_prices").fetchone()
    print(f"  {r['n']} snapshots across {r['t']} tickers   {r['a']} .. {r['b']}")

    print("\n=== forecast_snapshots (append-only) ===")
    for r in conn.execute(
        "SELECT source, COUNT(*) n, COUNT(DISTINCT nws_station) st, "
        "AVG(n_members) avgm, MIN(fetched_at) a, MAX(fetched_at) b "
        "FROM forecast_snapshots GROUP BY source"
    ):
        avgm = f"{r['avgm']:.0f} members" if r["avgm"] else "point"
        print(f"  {r['source']:<20} {r['n']:>4} rows  {r['st']} stations  {avgm}")

    print("\n=== risk_events ===")
    rows = conn.execute(
        "SELECT occurred_at, kind, ticker, reason FROM risk_events "
        "ORDER BY id DESC LIMIT 10").fetchall()
    if not rows:
        print("  none")
    for r in rows:
        print(f"  {r['occurred_at'][:19]} {r['kind']:<14} {r['ticker']}: {r['reason'][:70]}")

    print("\n=== collection_runs ===")
    for r in conn.execute(
        "SELECT kind, COUNT(*) n, SUM(n_ok) ok, SUM(n_failed) failed, MAX(started_at) last "
        "FROM collection_runs GROUP BY kind"
    ):
        print(f"  {r['kind']:<10} {r['n']:>3} runs  ok={r['ok']} failed={r['failed']}  "
              f"last={r['last'][:19]}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job", choices=["contracts", "books", "forecasts",
                                    "observations", "status", "all"])
    ap.add_argument("--all-series", action="store_true",
                    help="all 48 series instead of the 12-city trading watchlist")
    args = ap.parse_args()

    conn = db.connect()
    wl = load_watchlist(all_series=args.all_series)

    if args.job in ("contracts", "all"):
        print("=== contracts ===")
        collect_contracts(conn, wl)
    if args.job in ("forecasts", "all"):
        print("=== forecasts ===")
        collect_forecasts(conn, wl)
    if args.job in ("observations", "all"):
        print("=== observations ===")
        collect_observations(conn, wl)
    if args.job in ("books", "all"):
        print("=== books ===")
        collect_books(conn)
    if args.job == "status":
        status(conn)
    conn.close()


if __name__ == "__main__":
    main()
