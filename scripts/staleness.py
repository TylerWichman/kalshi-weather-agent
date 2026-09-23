"""Hypothesis B, step 1: do stale-quote windows last long enough to trade?

Phase 2b section 3 says answer the cheap measurement question first, because it can
rule the whole hypothesis out before any trading logic is written: **if these windows
close faster than the 15-minute polling cadence, there is nothing to build.**

Phase 2b section 2.4 names this explicitly -- polling cadence, not modelling, may be
the binding constraint.

## What is measured

The hourly dataset found 16,374 ladder-coherence gaps across 2,340 events, of which
294 events carry a *deep* gap (sum of asks < 95c or sum of bids > 105c). Hourly
candles cannot resolve how long a gap persists -- a gap seen in one hourly bar might
have lasted 40 seconds or 40 minutes.

So this reloads **1-minute** candles in a tight window around each deep gap and
reconstructs the ladder minute by minute, giving the distribution of:

    persistence = contiguous minutes for which the ladder stayed incoherent

The pre-registered decision (Phase 2b section 2.3/2.4): windows shorter than the
15-minute polling interval are not reachable by this system at all. A strategy that
needs sub-minute reaction is a different project with different infrastructure.

**Note this measurement is biased IN FAVOUR of the hypothesis**, deliberately:
starting only from gaps already visible in hourly bars oversamples long-lived ones,
since a gap lasting 40 minutes is far likelier to be caught by an hourly snapshot
than one lasting 40 seconds. If persistence looks short even here, it is shorter in
truth.

Usage:  python scripts/staleness.py [--events 294] [--window-hours 2]
"""

import argparse
import os
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import history  # noqa: E402

POLL_MINUTES = 15          # current collector cadence
DEEP_ASK = 95              # sum of asks below this = deep gap
DEEP_BID = 105             # sum of bids above this = deep gap
DB_OUT = os.path.join(ROOT, "data", "staleness.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS minute_ladders (
    event_ticker TEXT NOT NULL,
    period_ts    INTEGER NOT NULL,
    n_legs       INTEGER,
    sum_bid      INTEGER,
    sum_ask      INTEGER,
    min_vol      REAL,
    PRIMARY KEY (event_ticker, period_ts)
);
CREATE TABLE IF NOT EXISTS fetched_events (
    event_ticker TEXT PRIMARY KEY,
    fetched_at   TEXT
);
"""


def deep_gap_events(limit):
    """Events with at least one deep gap in the hourly data, plus the gap hours."""
    conn = sqlite3.connect(":memory:", uri=True)
    conn.execute("ATTACH DATABASE '"
                 + Path(os.path.join(ROOT, "data", "history.sqlite")).as_uri()
                 + "?mode=ro' AS h")
    ev_of = {}
    for t, e in conn.execute("SELECT ticker, event_ticker FROM h.hist_markets"):
        ev_of[t] = e
    snaps = defaultdict(list)
    for t, ts, b, a in conn.execute(
            "SELECT ticker, period_ts, yes_bid_close, yes_ask_close FROM h.hist_candles "
            "WHERE yes_bid_close IS NOT NULL AND yes_ask_close IS NOT NULL"):
        snaps[(ev_of[t], ts)].append((b, a))
    conn.close()

    hits = defaultdict(list)
    for (ev, ts), legs in snaps.items():
        if len(legs) != 6:
            continue
        sa = sum(a for b, a in legs)
        sb = sum(b for b, a in legs)
        if sa < DEEP_ASK or sb > DEEP_BID:
            hits[ev].append(ts)
    out = sorted(hits.items())[:limit]
    return out


def fetch_minutes(conn, event, gap_hours, window_h):
    """Load 1-minute candles for all six legs around each gap hour."""
    if conn.execute("SELECT 1 FROM fetched_events WHERE event_ticker=?",
                    (event,)).fetchone():
        return 0
    ms, tier = history.markets_for_event(event)
    if len(ms) != 6:
        conn.execute("INSERT OR REPLACE INTO fetched_events VALUES (?,datetime('now'))",
                     (event,))
        return 0
    series = ms[0]["ticker"].split("-")[0]

    per_ts = defaultdict(dict)
    for m in ms:
        t = m["ticker"]
        for g in gap_hours:
            lo, hi = g - window_h * 3600, g + window_h * 3600
            for c in history.candles(series, t, lo, hi, 1, tier):
                n = history.normalize_candle(c)
                if n["period_ts"] is None:
                    continue
                if n["yes_bid_close"] is None or n["yes_ask_close"] is None:
                    continue
                per_ts[n["period_ts"]][t] = (n["yes_bid_close"], n["yes_ask_close"],
                                             n["volume"])
            time.sleep(0.05)

    n_rows = 0
    for ts, legs in per_ts.items():
        if len(legs) != 6:
            continue
        bids = [v[0] for v in legs.values()]
        asks = [v[1] for v in legs.values()]
        vols = [v[2] for v in legs.values()]
        conn.execute("INSERT OR REPLACE INTO minute_ladders VALUES (?,?,?,?,?,?)",
                     (event, ts, 6, sum(bids), sum(asks), min(vols)))
        n_rows += 1
    conn.execute("INSERT OR REPLACE INTO fetched_events VALUES (?,datetime('now'))",
                 (event,))
    conn.commit()
    return n_rows


def runs_of_incoherence(rows):
    """Contiguous minute runs where the ladder was incoherent.

    Rows: (ts, sum_bid, sum_ask) sorted. A break of more than 2 minutes in the
    data ends a run, so missing candles do not silently fuse two windows.
    """
    out = []
    cur = None
    for ts, sb, sa in rows:
        bad = sa < 100 or sb > 100
        if bad:
            if cur and ts - cur[-1] <= 120:
                cur.append(ts)
            else:
                if cur:
                    out.append(cur)
                cur = [ts]
        else:
            if cur:
                out.append(cur)
            cur = None
    if cur:
        out.append(cur)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", type=int, default=294)
    ap.add_argument("--window-hours", type=int, default=2)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(DB_OUT), exist_ok=True)
    conn = sqlite3.connect(DB_OUT)
    conn.executescript(SCHEMA)

    targets = deep_gap_events(args.events)
    print(f"Hypothesis B, step 1 -- stale-quote persistence\n")
    print(f"  deep-gap events to sample : {len(targets)}")
    print(f"  window around each gap    : +/-{args.window_hours}h at 1-minute resolution")
    print(f"  current polling cadence   : {POLL_MINUTES} min\n")

    history.cutoff_ts()
    done = 0
    for ev, gaps in targets:
        try:
            n = fetch_minutes(conn, ev, gaps, args.window_hours)
            done += 1
            if done % 25 == 0:
                tot = conn.execute("SELECT COUNT(*) FROM minute_ladders").fetchone()[0]
                print(f"    {done}/{len(targets)} events, {tot:,} minute-ladders")
        except Exception as e:
            print(f"    {ev}: {e}", file=sys.stderr)

    analyse(conn)
    conn.close()


def analyse(conn):
    by_ev = defaultdict(list)
    for ev, ts, sb, sa in conn.execute(
            "SELECT event_ticker, period_ts, sum_bid, sum_ask FROM minute_ladders "
            "ORDER BY event_ticker, period_ts"):
        by_ev[ev].append((ts, sb, sa))

    durations = []
    for ev, rows in by_ev.items():
        for run in runs_of_incoherence(rows):
            durations.append((run[-1] - run[0]) / 60.0 + 1)

    print("\n" + "=" * 70)
    print("RESULT -- how long do incoherent windows last?")
    print("=" * 70)
    tot_min = sum(len(v) for v in by_ev.values())
    print(f"\n  events sampled        {len(by_ev):,}")
    print(f"  minute-ladders built  {tot_min:,}")
    print(f"  incoherent windows    {len(durations):,}")
    if not durations:
        print("\n  none found -- nothing to measure.")
        return

    d = np.array(durations)
    print(f"\n  persistence (minutes):")
    print(f"    median   {np.median(d):>8.1f}")
    print(f"    mean     {d.mean():>8.1f}")
    print(f"    p75      {np.percentile(d,75):>8.1f}")
    print(f"    p90      {np.percentile(d,90):>8.1f}")
    print(f"    max      {d.max():>8.1f}")
    print(f"\n  {'bucket':<18}{'windows':>9}{'share':>8}")
    print("  " + "-" * 35)
    for lo, hi, lab in [(0, 1, "<= 1 min"), (1, 5, "1-5 min"), (5, 15, "5-15 min"),
                        (15, 60, "15-60 min"), (60, 1e9, "> 60 min")]:
        n = int(((d > lo) & (d <= hi)).sum())
        print(f"  {lab:<18}{n:>9,}{100*n/len(d):>7.1f}%")

    reachable = int((d >= POLL_MINUTES).sum())
    print(f"\n  windows >= {POLL_MINUTES}min polling cadence: {reachable:,} of "
          f"{len(d):,} ({100*reachable/len(d):.1f}%)")

    print("\n" + "=" * 70)
    print("PRE-REGISTERED DECISION (Phase 2b section 2.3/2.4)")
    print("=" * 70)
    if reachable == 0:
        print("\n  NO-GO: no window survives one polling interval. Cadence, not")
        print("  modelling, is the binding constraint, exactly as 2.4 anticipated.")
    elif 100 * reachable / len(d) < 20:
        print(f"\n  NO-GO on current infrastructure: only {100*reachable/len(d):.1f}% of")
        print("  windows outlive a single poll, and this sample is biased toward long")
        print("  windows (it starts from gaps visible in hourly bars). Catching these")
        print("  needs sub-minute polling -- different infrastructure, not a tweak.")
    else:
        print(f"\n  Cadence is not disqualifying: {100*reachable/len(d):.1f}% of windows")
        print(f"  outlive a {POLL_MINUTES}-minute poll. Proceed to profitability, but")
        print("  remember windows must also be DEEP and LIQUID enough to pay the")
        print("  taker fee -- persistence alone is necessary, not sufficient.")
    print()


if __name__ == "__main__":
    main()
