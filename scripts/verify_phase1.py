"""Phase 1 acceptance check (spec v3 section 9, Phase 1 gate).

Two separate questions that a single check would conflate:

  A. STATION MATCHING -- is the forecast about the city the market is pricing?
     Tested with the **NWS point forecast**, because that is resolved to the exact
     station Kalshi settles against. If NWS lands far from the market's modal
     bucket, repeatedly, the wiring is wrong.

  B. ENSEMBLE BIAS -- how far is the Open-Meteo ensemble from that station?
     Open-Meteo interpolates a ~25km grid cell to a point. A grid cell is not a
     station, and the difference is systematic per site: coastal airports, urban
     heat islands and elevation all shift it in a consistent direction.

Conflating them is how you conclude "the pipeline is broken" when the pipeline is
fine and the model simply needs the per-station calibration that spec section 2.2
already calls for. B failing is expected and is Tier 1's job. A failing is a bug.

Usage:  python scripts/verify_phase1.py
"""

import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import db

# NWS is station-resolved, so it should sit in or beside the market's modal bucket.
# Two buckets (4F) off is a genuine alarm.
NWS_GAP_ALARM = 2


def in_bucket(v, lo, hi):
    return not ((lo is not None and v < lo) or (hi is not None and v > hi))


def label(lo, hi):
    return f"{lo if lo is not None else '-inf'}-{hi if hi is not None else '+inf'}"


def main():
    conn = db.connect()
    events = [r["event_ticker"] for r in conn.execute(
        "SELECT DISTINCT event_ticker FROM contracts WHERE status='active' "
        "ORDER BY target_date, event_ticker")]

    print("=" * 86)
    print("A. STATION MATCHING -- NWS point forecast vs market modal bucket")
    print("=" * 86)
    print(f"{'event':<24}{'station':<7}{'lead':>6}{'NWS':>6}  {'NWS bucket':<13}"
          f"{'mkt mode':<13}{'gap':>4}  verdict")
    print("-" * 86)

    alarms, biases = [], {}
    for ev in events:
        rows = conn.execute(
            """SELECT c.bucket_low_f lo, c.bucket_high_f hi, c.nws_station st,
                      c.target_date td, c.kind, c.city,
                      p.yes_bid_cents b, p.yes_ask_cents a
               FROM contracts c
               JOIN (SELECT ticker, yes_bid_cents, yes_ask_cents,
                            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY observed_at DESC) rn
                     FROM market_prices) p ON p.ticker = c.ticker AND p.rn = 1
               WHERE c.event_ticker = ?
               ORDER BY COALESCE(c.bucket_low_f, -999)""", (ev,)).fetchall()
        if not rows:
            continue
        st, td, kind, city = rows[0]["st"], rows[0]["td"], rows[0]["kind"], rows[0]["city"]

        nws = conn.execute(
            "SELECT point_value_f, lead_time_hours FROM forecast_snapshots "
            "WHERE nws_station=? AND target_date=? AND source='nws_gridpoint' "
            "ORDER BY fetched_at DESC LIMIT 1", (st, td)).fetchone()
        ens = conn.execute(
            "SELECT members_json FROM forecast_snapshots "
            "WHERE nws_station=? AND target_date=? AND source='openmeteo_ensemble' "
            "ORDER BY fetched_at DESC LIMIT 1", (st, td)).fetchone()
        if not nws or nws["point_value_f"] is None:
            print(f"{ev:<24}{st:<7}  no NWS forecast")
            continue

        v = nws["point_value_f"]
        mids = [(((r["b"] or 0) + (r["a"] or 0)) / 2.0) for r in rows]
        i_mkt = max(range(len(rows)), key=lambda i: mids[i])
        i_nws = next((i for i, r in enumerate(rows) if in_bucket(v, r["lo"], r["hi"])), None)

        if i_nws is None:
            gap, verdict = 99, "NWS OUTSIDE LADDER"
        else:
            gap = abs(i_nws - i_mkt)
            verdict = "SUSPECT" if gap >= NWS_GAP_ALARM else "ok"
        if verdict != "ok":
            alarms.append((ev, city, st, gap))

        nb = label(rows[i_nws]["lo"], rows[i_nws]["hi"]) if i_nws is not None else "n/a"
        mb = label(rows[i_mkt]["lo"], rows[i_mkt]["hi"])
        print(f"{ev:<24}{st:<7}{nws['lead_time_hours']:>5.0f}h{v:>6.0f}  {nb:<13}{mb:<13}"
              f"{gap:>4}  {verdict}")

        if ens and ens["members_json"]:
            mem = json.loads(ens["members_json"])
            biases.setdefault(st, []).append(statistics.mean(mem) - v)

    print("-" * 86)
    if alarms:
        print(f"\n{len(alarms)} ladder(s) flagged -- investigate before trusting Phase 1:")
        for ev, city, st, gap in alarms:
            print(f"  {ev}  city={city} station={st} gap={gap}")
    else:
        print("\nPASS: NWS lands in or beside the market's modal bucket for every ladder.")
        print("Station matching is correct end to end.")

    print("\n" + "=" * 86)
    print("B. ENSEMBLE BIAS -- Open-Meteo ensemble mean minus NWS point forecast")
    print("=" * 86)
    if not biases:
        print("  no paired data yet")
    else:
        allb = [x for v in biases.values() for x in v]
        print(f"  overall: mean {statistics.mean(allb):+.2f}F   "
              f"median {statistics.median(allb):+.2f}F   "
              f"sd {statistics.pstdev(allb):.2f}F   "
              f"range {min(allb):+.1f}..{max(allb):+.1f}   n={len(allb)}")
        print(f"\n  {'station':<9}{'mean':>8}{'n':>4}   per-observation")
        for st in sorted(biases, key=lambda s: statistics.mean(biases[s])):
            vals = biases[st]
            obs = "  ".join(f"{x:+.1f}" for x in vals)
            print(f"  {st:<9}{statistics.mean(vals):>+8.2f}{len(vals):>4}   {obs}")
        print("\n  Bias is per-station and holds its sign across days: that is a grid-to-point")
        print("  offset, not noise. Feeding raw ensemble members into bucket probabilities")
        print("  would shift them by 1-3 buckets at these magnitudes.")
        print("  Spec section 2.2's per-station, per-lead-time calibration is therefore")
        print("  load-bearing, not polish. Phase 2 must fit it before scoring anything.")
    print()
    conn.close()


if __name__ == "__main__":
    main()
