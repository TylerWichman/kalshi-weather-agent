"""Read-only progress check for the historical load.

Safe to run at any time while the loader is working. Opens the database in
SQLite read-only URI mode (`mode=ro`) and never creates tables, so it cannot
block or corrupt the writer. The loader itself uses WAL, so reads do not wait
on writes either.

    python scripts/load_progress.py
    python scripts/load_progress.py --watch     # refresh every 30s, Ctrl-C to stop
"""

import argparse
import datetime
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "history.sqlite")
TARGET_SERIES = 12
EXPECTED_PER_SERIES = 200        # --days default on the loader
ACTIVITY_SAMPLE_SECONDS = 4


def snapshot():
    if not os.path.exists(DB):
        return None
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
    try:
        ev = conn.execute("SELECT COUNT(*) FROM load_log").fetchone()[0]
        mk = conn.execute("SELECT COUNT(*) FROM hist_markets").fetchone()[0]
        cd = conn.execute("SELECT COUNT(*) FROM hist_candles").fetchone()[0]
        per = conn.execute(
            "SELECT series_ticker, COUNT(*) FROM load_log "
            "GROUP BY series_ticker ORDER BY series_ticker").fetchall()
        ts = conn.execute(
            "SELECT MIN(loaded_at), MAX(loaded_at) FROM load_log").fetchone()
        last = conn.execute(
            "SELECT event_ticker FROM load_log ORDER BY loaded_at DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    return dict(ev=ev, mk=mk, cd=cd, per=per, ts=ts,
                last=last[0] if last else "-",
                size=os.path.getsize(DB) / 1e6)


def is_active(seconds=None):
    """True if load_log is still growing -- the only honest completion signal."""
    seconds = seconds or ACTIVITY_SAMPLE_SECONDS
    a = snapshot()
    if not a:
        return False
    time.sleep(seconds)
    b = snapshot()
    return bool(b and b["ev"] > a["ev"])


def render(s):
    if not s:
        print("Database not created yet -- loader may still be starting.")
        return
    t0 = datetime.datetime.fromisoformat(s["ts"][0])
    t1 = datetime.datetime.fromisoformat(s["ts"][1])
    el = max((t1 - t0).total_seconds(), 1e-9)
    rate = s["ev"] / el * 60

    print(f"Historical load progress   ({datetime.datetime.now():%H:%M:%S})")
    print("-" * 52)
    print(f"  events loaded   {s['ev']:>8,}")
    print(f"  markets         {s['mk']:>8,}")
    print(f"  candles         {s['cd']:>8,}")
    print(f"  db size         {s['size']:>8.1f} MB")
    print(f"  rate            {rate:>8.1f} events/min")
    print(f"  last event      {s['last']}")
    print(f"\n  series done: {len(s['per'])}/{TARGET_SERIES}")
    for name, n in s["per"]:
        print(f"    {name:<14}{n:>5} events")
    done_series = len(s["per"])
    # Presence of all 12 series does NOT mean finished -- the last one is normally
    # still filling. Only a growing event count is an honest completion signal.
    active = is_active()
    short = [(n, c) for n, c in s["per"] if c < EXPECTED_PER_SERIES]
    if active:
        print("\n  STATUS: RUNNING -- event count still growing")
    elif short or done_series < TARGET_SERIES:
        print("\n  STATUS: STOPPED, INCOMPLETE -- no new events in the sample window")
        print("          Re-run the loader; it resumes from load_log.")
    else:
        print("\n  STATUS: COMPLETE -- all series at full count, no activity")

    remaining = max(TARGET_SERIES - done_series, 0) * EXPECTED_PER_SERIES
    remaining += sum(EXPECTED_PER_SERIES - c for _, c in short)
    if short:
        print("\n  series below expected count:")
        for n, c in short:
            print(f"    {n:<14}{c:>5} / {EXPECTED_PER_SERIES}")
    if remaining > 0 and rate > 0 and active:
        print(f"\n  rough ETA: ~{remaining / rate:.1f} min "
              f"({remaining:,} events to go at the current rate)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true", help="refresh every 30s")
    args = ap.parse_args()
    if not args.watch:
        render(snapshot())
        return
    try:
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            render(snapshot())
            print("\n  (Ctrl-C to stop watching; the loader keeps running)")
            time.sleep(30)
    except KeyboardInterrupt:
        print("\nstopped watching -- loader unaffected")


if __name__ == "__main__":
    main()
