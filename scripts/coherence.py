"""Ladder-coherence check (spec v3 section 2.6).

The one edge source in the spec that does not depend on the weather model. Each
Kalshi event is a mutually exclusive, exhaustive 6-bucket ladder, so the true
probabilities sum to exactly 1. The quoted prices need not.

    sum of ASKS  < 100c  ->  buy every bucket for less than the guaranteed $1 payout
    sum of BIDS  > 100c  ->  sell every bucket for more than the $1 you must pay out

Only those two are tradeable. **The sum of mids is a monitoring signal, not an
opportunity** -- a mid is not a price anyone will trade at, and the usual reason a
mid-sum sits below 1 is ordinary bid/ask friction. Conflating the two is the easy
way to invent an edge that is not there.

Any gap must still clear **six legs of fees** (section 2.3). Maker is $0 for weather,
but an arbitrage captured by resting six orders risks partial fills -- ending up long
four of six buckets is not an arbitrage, it is a position nobody chose. So the
headline test is the **taker** capture, where the fee is quadratic per leg and the
mid-priced legs are the expensive ones.

## Known limitation

Candles carry top-of-book only. A real capture needs size at all six levels at the
same instant, and depth is not in this data (same gap as `src/fillsim.py`). So a flag
here is an upper bound on opportunity, not a fill. The live pipeline records full
depth and is the way to confirm any signal this finds.

Usage:  python scripts/coherence.py
"""

import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import fees  # noqa: E402

LADDER_SIZE = 6
CONTRACTS = 100        # per leg, for the fee arithmetic


def load():
    conn = sqlite3.connect(":memory:", uri=True)
    conn.execute("ATTACH DATABASE '"
                 + Path(os.path.join(ROOT, "data", "history.sqlite")).as_uri()
                 + "?mode=ro' AS h")
    conn.row_factory = sqlite3.Row

    ev_of, city_of = {}, {}
    for r in conn.execute("SELECT ticker, event_ticker, city FROM h.hist_markets"):
        ev_of[r["ticker"]] = r["event_ticker"]
        city_of[r["event_ticker"]] = r["city"]

    # (event, timestamp) -> list of (bid, ask) across buckets
    snaps = defaultdict(list)
    for r in conn.execute(
            "SELECT ticker, period_ts, yes_bid_close b, yes_ask_close a, volume v "
            "FROM h.hist_candles WHERE b IS NOT NULL AND a IS NOT NULL"):
        ev = ev_of.get(r["ticker"])
        if ev:
            snaps[(ev, r["period_ts"])].append((r["b"], r["a"], r["v"]))
    conn.close()
    return snaps, city_of


def buy_ladder_profit(asks, contracts):
    """Profit from buying all six buckets as a taker.

    Cost is the sum of the six asks; payout is a guaranteed 100c per ladder unit
    (exactly one bucket settles yes). Fees are six taker legs.
    """
    cost = sum(asks) * contracts
    fee = sum(fees.trade_fee_cents(contracts, p, is_maker=False) for p in asks)
    return contracts * 100 - cost - fee, fee


def sell_ladder_profit(bids, contracts):
    """Profit from selling all six buckets as a taker.

    You receive the sum of the six bids and must pay out 100c per ladder unit.
    Equivalently you buy six NO contracts at (100 - bid) and five of them pay out.
    Profit is therefore sum(bids) - 100, NOT 100 - sum(no_prices): the NO basket
    pays 500c, not 100c, and treating it as 100c understates it by ~400c per
    ladder -- which is exactly the constant -402c artifact the first version of
    this script produced.
    """
    proceeds = sum(bids) * contracts
    no_prices = [100 - b for b in bids]
    fee = sum(fees.trade_fee_cents(contracts, p, is_maker=False) for p in no_prices)
    return proceeds - contracts * 100 - fee, fee


def tradeable_size(vols, cap):
    """Size the arb to its thinnest leg.

    A six-leg capture is limited by the leg with the least available size. Candles
    give period volume rather than resting depth, so this is an optimistic proxy --
    but assuming a fixed 100 lots when the thinnest leg printed 2 contracts is not
    a proxy, it is fiction.
    """
    return max(int(min(min(vols), cap)), 0)


def main():
    snaps, city_of = load()
    full = {k: v for k, v in snaps.items() if len(v) == LADDER_SIZE}

    print("=" * 78)
    print("LADDER-COHERENCE CHECK (spec v3 section 2.6)")
    print("=" * 78)
    print(f"\n  ladder snapshots seen      {len(snaps):,}")
    print(f"  complete 6-bucket snapshots {len(full):,}")
    if not full:
        sys.exit("no complete ladders")

    sum_bid, sum_ask, sum_mid = [], [], []
    buy_arbs, sell_arbs = [], []

    for (ev, ts), legs in full.items():
        bids = [b for b, a, v in legs]
        asks = [a for b, a, v in legs]
        vols = [v for b, a, v in legs]
        sb, sa = sum(bids), sum(asks)
        sm = sum((b + a) / 2 for b, a, v in legs)
        sum_bid.append(sb)
        sum_ask.append(sa)
        sum_mid.append(sm)

        size = tradeable_size(vols, CONTRACTS)
        if sa < 100 and size > 0:
            gt, ft = buy_ladder_profit(asks, size)
            buy_arbs.append(dict(ev=ev, ts=ts, gap=100 - sa, taker=gt,
                                 fee=ft, size=size, minvol=min(vols)))
        if sb > 100 and size > 0:
            gt, ft = sell_ladder_profit(bids, size)
            sell_arbs.append(dict(ev=ev, ts=ts, gap=sb - 100, taker=gt,
                                  fee=ft, size=size, minvol=min(vols)))

    sum_bid, sum_ask, sum_mid = map(np.array, (sum_bid, sum_ask, sum_mid))

    print("\n" + "=" * 78)
    print("1. HOW COHERENT ARE THE LADDERS?")
    print("=" * 78)
    print(f"\n  {'':<12}{'mean':>9}{'median':>9}{'p1':>8}{'p99':>8}{'min':>8}{'max':>8}")
    for name, arr in (("sum of bids", sum_bid), ("sum of mids", sum_mid),
                      ("sum of asks", sum_ask)):
        print(f"  {name:<12}{arr.mean():>9.2f}{np.median(arr):>9.2f}"
              f"{np.percentile(arr,1):>8.2f}{np.percentile(arr,99):>8.2f}"
              f"{arr.min():>8.2f}{arr.max():>8.2f}")
    print("\n  A coherent, frictionless ladder would sum to 100c on every line.")
    print("  bids below and asks above 100 is just the bid/ask spread, six times over.")

    print("\n" + "=" * 78)
    print("2. EXECUTABLE MISPRICINGS")
    print("=" * 78)
    n = len(full)
    print(f"\n  sum of asks < 100c (buy the ladder) : {len(buy_arbs):,} "
          f"({100*len(buy_arbs)/n:.3f}% of snapshots)")
    print(f"  sum of bids > 100c (sell the ladder): {len(sell_arbs):,} "
          f"({100*len(sell_arbs)/n:.3f}% of snapshots)")

    for label, arbs in (("BUY-SIDE", buy_arbs), ("SELL-SIDE", sell_arbs)):
        if not arbs:
            print(f"\n  {label}: none found.")
            continue
        gaps = np.array([a["gap"] for a in arbs])
        tak = np.array([a["taker"] for a in arbs])
        vols = np.array([a["minvol"] for a in arbs])
        print(f"\n  {label}  n={len(arbs):,}")
        print(f"    raw gap (cents/ladder)     mean {gaps.mean():.2f}  "
              f"median {np.median(gaps):.2f}  max {gaps.max():.2f}")
        sz = np.array([a["size"] for a in arbs])
        print(f"    tradeable size (thin leg)  median {np.median(sz):.0f} contracts  "
              f"max {sz.max():.0f}")
        print(f"    net after 6 taker legs     mean ${tak.mean()/100:+.2f}  "
              f"median ${np.median(tak)/100:+.2f}  max ${tak.max()/100:+.2f}")
        surv = int((tak > 0).sum())
        print(f"    survives taker fees        {surv:,} of {len(arbs):,} "
              f"({100*surv/len(arbs):.1f}%)")
        print(f"    thinnest leg volume        median {np.median(vols):.0f} contracts")
        if surv:
            tot = tak[tak > 0].sum()
            print(f"    TOTAL if every fee-surviving taker arb were captured: "
                  f"${tot/100:,.2f}")

    print("\n" + "=" * 78)
    print("3. VERDICT")
    print("=" * 78)
    surviving = [a for a in buy_arbs if a["taker"] > 0] + \
                [a for a in sell_arbs if a["taker"] > 0]
    print(f"\n  complete snapshots            {n:,}")
    print(f"  executable gaps before fees   {len(buy_arbs)+len(sell_arbs):,}")
    print(f"  still profitable after fees   {len(surviving):,}")
    if surviving:
        tot = sum(a["taker"] for a in surviving) / 100
        print(f"  gross opportunity (upper bd)  ${tot:,.2f} over "
              f"{n:,} snapshots")
        print("\n  Upper bound only: top-of-book, no depth, assumes all six legs fill")
        print("  at the quote simultaneously. Confirm against live depth before acting.")
    else:
        print("\n  No fee-surviving mispricings. The ladders are coherently priced:")
        print("  quoted sums sit where bid/ask friction alone predicts, and nothing")
        print("  is left after six legs of fees.")
    print()


if __name__ == "__main__":
    main()
