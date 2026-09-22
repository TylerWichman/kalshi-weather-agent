"""
Phase 0.5 -- NWS <-> TWC settlement basis logger (spec v3 section 2.7).

These contracts settle on The Weather Company, but we forecast off NWS. Nobody has
measured the gap. Bucket edges are 2 degrees apart, so a 1 degree systematic basis
flips contracts outright, which makes this the number that decides whether a
Phase 2 backtest calibrated on NWS observations means anything.

TWC is not readable programmatically yet (weather.com/kalshi is a JS shell), so we
infer it from Kalshi's own settled outcomes: the winning bucket bounds the TWC
value to a range. Coarse, free, and honest. It sharpens with history.

NWS side: the *final* CLI climatological product, not raw METAR observations.
Kalshi's station ids literally are CLI product ids -- their rules text says
"New York City (CLINYC)", and CLINYC is the NWS climate report for Central Park.
This matters: CLI carries the official daily max/min, whereas a max over sampled
observations systematically understates the true high. Measured on NYC 2026-09-20,
the preliminary afternoon product said 67 and the final said 69 -- a 2 degree gap,
one full bucket, from methodology alone.

Each location issues a preliminary product each afternoon ("VALID TODAY AS OF...")
and a final one early the next morning covering the previous day. Only the final
one is used.

Writes to data/basis.sqlite. Idempotent -- safe to re-run for any date.

History limit: the CLI products endpoint retains roughly 15 products per location,
about 7 days. Backfill beyond that needs NCEI, not this script. Which is the whole
reason this runs daily starting now rather than being deferred to Phase 2.

Usage:
    python scripts/basis_logger.py              # last 7 days
    python scripts/basis_logger.py --date 2026-09-21
    python scripts/basis_logger.py --report
"""

import argparse
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHLIST = os.path.join(ROOT, "config", "watchlist.json")
DB_PATH = os.path.join(ROOT, "data", "basis.sqlite")

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
NWS = "https://api.weather.gov"
UA = {"User-Agent": "kalshi-weather-agent basis-logger (tylerwichman13@gmail.com)"}

MONTHS = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY",
          "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS basis_observations (
    obs_date          TEXT NOT NULL,
    series_ticker     TEXT NOT NULL,
    event_ticker      TEXT NOT NULL,
    city              TEXT,
    kind              TEXT,              -- high | low
    kalshi_station_id TEXT,
    nws_station       TEXT,
    cli_location      TEXT,
    nws_value_f       REAL,              -- official daily max/min from the final CLI product
    nws_source        TEXT,              -- cli_final | missing
    settled_bucket    TEXT,              -- ticker of the market that resolved yes
    twc_low_f         REAL,              -- TWC value implied >= this (null = open tail)
    twc_high_f        REAL,              -- TWC value implied <= this (null = open tail)
    nws_in_bucket     INTEGER,           -- 1/0: would NWS have picked the settled bucket
    basis_low_f       REAL,              -- twc - nws, lower bound
    basis_high_f      REAL,              -- twc - nws, upper bound
    recorded_at       TEXT NOT NULL,
    PRIMARY KEY (obs_date, series_ticker)
);
CREATE TABLE IF NOT EXISTS run_log (
    run_at      TEXT NOT NULL,
    obs_date    TEXT NOT NULL,
    n_written   INTEGER,
    n_skipped   INTEGER,
    note        TEXT
);
"""


def get_json(url, retries=4):
    """GET with backoff. NWS and Kalshi both rate-limit; neither is urgent here."""
    delay = 1.0
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as f:
                return json.load(f)
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


# ---------------------------------------------------------------- NWS CLI side

_cli_cache = {}


def cli_products(location):
    """All retained CLI products for a location, parsed. Cached per run."""
    if location in _cli_cache:
        return _cli_cache[location]
    listing = get_json(f"{NWS}/products/types/CLI/locations/{location}")
    out = []
    for item in (listing or {}).get("@graph", []):
        prod = get_json(f"{NWS}/products/{item['id']}")
        if not prod:
            continue
        text = prod.get("productText", "")
        parsed = parse_cli(text)
        if parsed:
            parsed["issued"] = item.get("issuanceTime")
            out.append(parsed)
        time.sleep(0.12)
    _cli_cache[location] = out
    return out


def parse_cli(text):
    """Pull the covered date, finality, and daily max/min out of a CLI product."""
    m = re.search(r"CLIMATE SUMMARY FOR ([A-Z]+)\s+(\d+)\s+(\d{4})", text)
    if not m:
        return None
    month, day, year = m.group(1), int(m.group(2)), int(m.group(3))
    if month not in MONTHS:
        return None
    covered = date(year, MONTHS.index(month) + 1, day)

    # The afternoon product is preliminary and undercounts the day's extremes.
    # The early-morning product covering the previous day carries no such marker.
    preliminary = bool(re.search(r"VALID TODAY AS OF", text))

    def field(label):
        m2 = re.search(rf"^\s*{label}\s+(-?\d+)", text, re.MULTILINE)
        return float(m2.group(1)) if m2 else None

    return {
        "date": covered,
        "preliminary": preliminary,
        "high": field("MAXIMUM"),
        "low": field("MINIMUM"),
    }


def nws_official(location, day, kind):
    """Official daily extreme for `day`, from the final CLI product only."""
    for p in cli_products(location):
        if p["date"] == day and not p["preliminary"]:
            return p["high"] if kind == "high" else p["low"]
    return None


# ------------------------------------------------------------- Kalshi side

def bucket_bounds(market):
    """Temperature range implied by a settled bucket, in Fahrenheit.

    Kalshi ladders are one `less` tail, four 2-degree `between` buckets, and one
    `greater` tail. Tails return None on their open side.

    BOTH tails are strict against their strike, per Kalshi's own subtitles:
        less    cap=80   -> "79 or below"  -> (None, 79)
        greater floor=87 -> "88 or above"  -> (88, None)
    Treating `less` as <= cap makes the bucket one degree too wide and inflates
    the measured agreement rate, since an NWS value landing exactly on cap would
    be counted as in-bucket when it is not.
    """
    st = market.get("strike_type")
    floor = market.get("floor_strike")
    cap = market.get("cap_strike")
    floor = float(floor) if floor is not None else None
    cap = float(cap) if cap is not None else None
    if st == "less":
        return None, (cap - 1.0) if cap is not None else None
    if st == "greater":
        return (floor + 1.0) if floor is not None else None, None
    if st == "between":
        return floor, cap
    return None, None


def in_bucket(value, lo, hi):
    if value is None:
        return None
    if lo is not None and value < lo - 1e-9:
        return 0
    if hi is not None and value > hi + 1e-9:
        return 0
    return 1


def settled_winner(series_ticker, day):
    """The market that resolved yes for `day`'s event, if it has settled."""
    j = get_json(f"{KALSHI}/markets?series_ticker={series_ticker}&status=settled&limit=200")
    if not j:
        return None, None
    stamp = f"{day.strftime('%y')}{day.strftime('%b').upper()}{day.day:02d}"
    markets = [m for m in j.get("markets", []) if m.get("event_ticker", "").endswith(stamp)]
    if not markets:
        return None, None
    winner = next((m for m in markets if (m.get("result") or "").lower() == "yes"), None)
    return markets[0]["event_ticker"], winner


# ------------------------------------------------------------------- driver

def run_for_date(conn, series, day, verbose=True):
    written = skipped = 0
    for s in series:
        key = (day.isoformat(), s["series_ticker"])
        if conn.execute(
            "SELECT 1 FROM basis_observations WHERE obs_date=? AND series_ticker=? AND nws_value_f IS NOT NULL",
            key,
        ).fetchone():
            skipped += 1
            continue

        event, winner = settled_winner(s["series_ticker"], day)
        if not winner:
            skipped += 1
            continue

        cli_loc = s["kalshi_station_id"][3:]          # CLINYC -> NYC
        nws_val = nws_official(cli_loc, day, s["kind"])
        if nws_val is None:
            # Outside the ~7 day CLI retention window, or not yet finalized.
            skipped += 1
            if verbose:
                print(f"  {s['series_ticker']:<13} no final CLI product for {day}")
            continue

        lo, hi = bucket_bounds(winner)
        ok = in_bucket(nws_val, lo, hi)
        b_lo = (lo - nws_val) if lo is not None else None
        b_hi = (hi - nws_val) if hi is not None else None

        conn.execute(
            "INSERT OR REPLACE INTO basis_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                day.isoformat(), s["series_ticker"], event, s["city"], s["kind"],
                s["kalshi_station_id"], s["nws_station"], cli_loc,
                nws_val, "cli_final", winner["ticker"], lo, hi, ok, b_lo, b_hi,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        written += 1
        if verbose:
            rng = f"[{lo if lo is not None else '-inf'}, {hi if hi is not None else '+inf'}]"
            flag = "" if ok else "   <-- NWS OUTSIDE SETTLED BUCKET"
            print(f"  {s['series_ticker']:<13} nws={nws_val:6.1f}  settled={rng:<14}{flag}")
        time.sleep(0.15)

    conn.execute(
        "INSERT INTO run_log VALUES (?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), day.isoformat(), written, skipped, "cli_final"),
    )
    conn.commit()
    return written, skipped


def report(conn):
    n, n_ok, d0, d1 = conn.execute(
        "SELECT COUNT(*), SUM(nws_in_bucket), MIN(obs_date), MAX(obs_date) "
        "FROM basis_observations WHERE nws_value_f IS NOT NULL"
    ).fetchone()
    if not n:
        print("No usable observations logged yet.")
        return

    print(f"\nNWS(CLI final) <-> TWC basis   {d0} to {d1}   n={n}")
    print(f"  NWS selects the settled bucket: {n_ok}/{n} = {100.0 * n_ok / n:.1f}%")
    print(f"  Bucket-flip rate:               {100.0 * (n - n_ok) / n:.1f}%"
          f"   <-- the number that gates Phase 2")

    print("\n  Direction of miss (closed-bucket cases only):")
    for kind, tot, ok, low, high in conn.execute(
        """SELECT kind, COUNT(*), SUM(nws_in_bucket),
           SUM(CASE WHEN nws_in_bucket=0 AND twc_low_f  IS NOT NULL AND nws_value_f < twc_low_f  THEN 1 ELSE 0 END),
           SUM(CASE WHEN nws_in_bucket=0 AND twc_high_f IS NOT NULL AND nws_value_f > twc_high_f THEN 1 ELSE 0 END)
           FROM basis_observations WHERE nws_value_f IS NOT NULL GROUP BY kind"""
    ):
        print(f"    {kind:<5} n={tot:<4} in-bucket={ok:<4} NWS too low={low:<4} NWS too high={high}")

    print("\n  By city:")
    for city, tot, ok in conn.execute(
        "SELECT city, COUNT(*), SUM(nws_in_bucket) FROM basis_observations "
        "WHERE nws_value_f IS NOT NULL GROUP BY city ORDER BY 3.0/COUNT(*) ASC"
    ):
        print(f"    {city:<16} {tot:>4} obs   {100.0 * (tot - ok) / tot:5.1f}% flipped")

    print("\n  Open tails make the basis one-sided; bounds widen accordingly.")
    print("  Treat the flip rate as meaningful only past ~200 observations.\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD")
    ap.add_argument("--days", type=int, default=7, help="days back to attempt (default 7)")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    if args.report:
        report(conn)
        return

    series = json.load(open(WATCHLIST))["series"]
    days = ([date.fromisoformat(args.date)] if args.date
            else [date.today() - timedelta(days=i) for i in range(1, args.days + 1)])

    tw = ts = 0
    for day in days:
        print(f"\n=== {day.isoformat()} ===")
        w, s = run_for_date(conn, series, day)
        print(f"  -> wrote {w}, skipped {s}")
        tw += w
        ts += s

    print(f"\nTotal: {tw} written, {ts} skipped -> {DB_PATH}")
    report(conn)
    conn.close()


if __name__ == "__main__":
    main()
