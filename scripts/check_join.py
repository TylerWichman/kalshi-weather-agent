"""Sanity check: how much of the loaded price history joins to forecast data?

This is the real backtest sample size, and it is smaller than either dataset alone.
Also reports the tradeable/excluded split (spec v3 section 2.3 station gate), since
a headline P&L number is meaningless without knowing which universe produced it.
"""

import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUDED = {"KLAX", "KNYC"}


def attach(conn, alias, path):
    # pathlib builds the file:///C:/... form Windows needs; a bare drive letter
    # after "file:" is parsed as a URI scheme and fails to open.
    from pathlib import Path
    uri = Path(path).as_uri() + "?mode=ro"
    conn.execute(f"ATTACH DATABASE '{uri}' AS {alias}")


def main():
    # uri=True must be set on the connection, or ATTACH treats a file: URI as a
    # literal filename and fails regardless of how well-formed the URI is.
    conn = sqlite3.connect(":memory:", uri=True)
    attach(conn, "h", os.path.join(ROOT, "data", "history.sqlite"))
    attach(conn, "k", os.path.join(ROOT, "data", "calibration.sqlite"))

    base = ("FROM h.hist_markets m JOIN k.calibration_set c "
            "ON c.nws_station = m.nws_station AND c.target_date = m.target_date "
            "WHERE c.lead_days = 1 AND c.actual_f IS NOT NULL "
            "AND m.result IN ('yes','no')")

    n = conn.execute(
        f"SELECT COUNT(DISTINCT m.nws_station || m.target_date) {base}").fetchone()[0]
    print("Backtest join: price history x 24-48h forecast\n")
    print(f"  joinable station-days: {n:,}\n")

    trade = excl = 0
    print(f"  {'station':<9}{'days':>6}  universe")
    print("  " + "-" * 38)
    for st, d in conn.execute(
            f"SELECT m.nws_station, COUNT(DISTINCT m.target_date) {base} "
            f"GROUP BY m.nws_station ORDER BY m.nws_station"):
        is_ex = st in EXCLUDED
        trade += 0 if is_ex else d
        excl += d if is_ex else 0
        print(f"  {st:<9}{d:>6}  {'EXCLUDED (scored only)' if is_ex else 'tradeable'}")
    print("  " + "-" * 38)
    total = trade + excl
    print(f"  {'tradeable':<9}{trade:>6}  {100*trade/total:.0f}% of station-days")
    print(f"  {'excluded':<9}{excl:>6}  {100*excl/total:.0f}% of station-days")

    lo, hi = conn.execute(f"SELECT MIN(m.target_date), MAX(m.target_date) {base}").fetchone()
    print(f"\n  date overlap: {lo} .. {hi}")

    cd = conn.execute(
        f"SELECT COUNT(*) FROM h.hist_candles WHERE ticker IN "
        f"(SELECT m.ticker {base})").fetchone()[0]
    print(f"  candles on joinable markets: {cd:,}")
    conn.close()


if __name__ == "__main__":
    main()
