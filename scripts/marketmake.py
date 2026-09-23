"""Hypothesis A: spread capture via two-sided market making (Phase 2b section 1).

Structurally different from both failed mechanisms. It does not ask "do we know the
true probability better than the market" -- the assumption that failed twice. It asks
whether resting quotes on both sides of every bucket earns the bid/ask spread on
volume that crosses them. Maker fees are $0 on weather, so that spread is gross
margin before inventory risk.

## Strategy

At each period, for each bucket, rest a bid at the best bid and an ask at the best
ask (joining the touch -- the median spread is 1.8c and many are 1c, so quoting
*inside* is usually impossible). Fills come from `src/fillsim.py` under its stated
conservative rules: trade-through required, 10% participation cap, no queue credit.

`p_model` is deliberately NOT the trade trigger. Per section 1.2 it only **skews**
quotes: the side the model thinks is likely to be picked off is withdrawn, rather
than used to decide whether to trade at all.

## Inventory is the risk control, not a probability threshold (section 1.2)

Three hard limits, pre-registered and not swept (section 4):

- `INVENTORY_CAP_BUCKET` contracts net per bucket
- `INVENTORY_CAP_EVENT` contracts net across a ladder
- quoting on a side **stops** once inventory past `SKEW_THRESHOLD` of the cap would
  be increased by it

Residual inventory is settled at resolution (100c if the bucket settled yes, else 0),
so one-sided inventory shows up as real P&L rather than being quietly dropped.

## Reporting (section 1.3)

Mean P&L alone is not the answer. A strategy that earns steadily and occasionally
takes a large one-sided hit during a fast-moving event is a different risk profile
from steady spread capture, so this reports the **per-event P&L distribution, worst
events, and maximum one-sided inventory** alongside the mean -- tail visible, not
averaged away.

It also measures **adverse selection directly**: after each maker fill, where did the
mid go next? That is the cost section 2.3 flagged and `src/fillsim.py` cannot model.
Historical candles can measure it even though queue position is unknowable, so it
does not have to wait for Phase 5.5.

## Pre-registered go/no-go (section 1.3)

- **Go:** net P&L positive with a 95% CI excluding zero, across the same walk-forward
  folds as Phase 2.
- **No-go:** CI includes zero, or the point estimate is negative.

Not loosened if the result is negative (section 4).

Usage:  python scripts/marketmake.py
"""

import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from src import fees, fillsim, risk           # noqa: E402
from calibrate import walk_forward_folds      # noqa: E402

# Pre-registered. Not swept (Phase 2b section 4).
QUOTE_SIZE = 50               # contracts offered per side per period
INVENTORY_CAP_BUCKET = 200    # net contracts in one bucket
INVENTORY_CAP_EVENT = 500     # net contracts across a ladder
SKEW_THRESHOLD = 0.5          # stop adding past this fraction of a cap


def load():
    conn = sqlite3.connect(":memory:", uri=True)
    conn.execute("ATTACH DATABASE '"
                 + Path(os.path.join(ROOT, "data", "history.sqlite")).as_uri()
                 + "?mode=ro' AS h")
    conn.row_factory = sqlite3.Row

    meta = {}
    for r in conn.execute(
            "SELECT ticker, event_ticker, nws_station, city, target_date, result "
            "FROM h.hist_markets WHERE result IN ('yes','no')"):
        meta[r["ticker"]] = dict(r)

    series = defaultdict(list)
    for r in conn.execute(
            "SELECT ticker, period_ts, yes_bid_close, yes_ask_close, "
            "price_low, price_high, volume FROM h.hist_candles "
            "WHERE yes_bid_close IS NOT NULL AND yes_ask_close IS NOT NULL "
            "ORDER BY ticker, period_ts"):
        if r["ticker"] in meta:
            series[r["ticker"]].append(dict(r))
    conn.close()
    return meta, series


def run_event(event, tickers, meta, series):
    """Simulate two-sided quoting across one ladder. Returns a result dict."""
    inv = defaultdict(int)          # ticker -> net contracts (positive = long yes)
    cash = 0                        # cents
    fills = []
    adverse = []                    # (mid_at_fill, mid_next, direction)
    max_one_sided = 0

    # Align periods across the ladder's buckets.
    stamps = sorted({c["period_ts"] for t in tickers for c in series.get(t, [])})
    by_ts = {t: {c["period_ts"]: c for c in series.get(t, [])} for t in tickers}

    for i, ts in enumerate(stamps):
        net_event = sum(inv.values())
        for t in tickers:
            cd = by_ts[t].get(ts)
            if not cd:
                continue
            bid, ask = cd["yes_bid_close"], cd["yes_ask_close"]
            if not bid or not ask or ask <= bid:
                continue

            pos = inv[t]
            # Skew: withdraw the side that would push inventory further out.
            buy_ok = (pos < SKEW_THRESHOLD * INVENTORY_CAP_BUCKET
                      and net_event < SKEW_THRESHOLD * INVENTORY_CAP_EVENT
                      and pos + QUOTE_SIZE <= INVENTORY_CAP_BUCKET)
            sell_ok = (pos > -SKEW_THRESHOLD * INVENTORY_CAP_BUCKET
                       and net_event > -SKEW_THRESHOLD * INVENTORY_CAP_EVENT
                       and pos - QUOTE_SIZE >= -INVENTORY_CAP_BUCKET)

            mid = (bid + ask) / 2.0
            nxt = by_ts[t].get(stamps[i + 1]) if i + 1 < len(stamps) else None
            mid_next = ((nxt["yes_bid_close"] + nxt["yes_ask_close"]) / 2.0
                        if nxt and nxt["yes_bid_close"] and nxt["yes_ask_close"] else None)

            if buy_ok:
                f = fillsim.simulate_maker(cd, "buy_yes", bid, QUOTE_SIZE)
                if f.filled:
                    inv[t] += f.contracts
                    cash -= f.contracts * bid + f.fee_cents
                    fills.append(("buy", f.contracts, bid, f.fee_cents))
                    if mid_next is not None:
                        adverse.append(mid_next - mid)      # want > 0 after a buy
            if sell_ok:
                f = fillsim.simulate_maker(cd, "sell_yes", ask, QUOTE_SIZE)
                if f.filled:
                    inv[t] -= f.contracts
                    cash += f.contracts * ask - f.fee_cents
                    fills.append(("sell", f.contracts, ask, f.fee_cents))
                    if mid_next is not None:
                        adverse.append(mid - mid_next)      # want > 0 after a sell
            max_one_sided = max(max_one_sided, abs(inv[t]))

    # Settle residual inventory at resolution.
    settle = 0
    for t, q in inv.items():
        if q == 0:
            continue
        payoff = 100 if meta[t]["result"] == "yes" else 0
        settle += q * payoff
    net = cash + settle

    return dict(event=event, net=net, cash=cash, settle=settle,
                n_fills=len(fills), fees=sum(f[3] for f in fills),
                max_one_sided=max_one_sided,
                residual=sum(abs(q) for q in inv.values()),
                adverse=adverse,
                date=meta[tickers[0]]["target_date"],
                station=meta[tickers[0]]["nws_station"],
                city=meta[tickers[0]]["city"])


def main():
    meta, series = load()
    ladders = defaultdict(list)
    for t, m in meta.items():
        ladders[m["event_ticker"]].append(t)
    ladders = {e: ts for e, ts in ladders.items() if len(ts) == 6}

    dates = sorted({meta[ts[0]]["target_date"] for ts in ladders.values()})
    folds = walk_forward_folds(dates)

    results = []
    for ev, tickers in ladders.items():
        r = run_event(ev, tickers, meta, series)
        r["fold"] = next((i for i, f in enumerate(folds, 1)
                          if r["date"] in f["test"]), None)
        r["excluded"] = r["station"] in risk.EXCLUDED_STATIONS
        results.append(r)

    report(results, folds)


def report(results, folds):
    print("=" * 78)
    print("HYPOTHESIS A -- TWO-SIDED MARKET MAKING (Phase 2b section 1)")
    print("=" * 78)

    tested = [r for r in results if r["fold"] and not r["excluded"]]
    print("\n" + "!" * 78)
    print("UNIVERSE: 10 of 12 cities. LAX and NYC remain hard-gated out of sizing")
    print("(spec v3 2.3) -- ~17% of ladder-days but ~43% of watchlist VOLUME.")
    print("!" * 78)

    if not tested:
        print("\nno ladders in test folds")
        return

    net = np.array([r["net"] for r in tested], dtype=float)
    print(f"\n  ladder-days traded   {len(tested):,}")
    print(f"  total fills          {sum(r['n_fills'] for r in tested):,}")
    print(f"  fees paid            ${sum(r['fees'] for r in tested)/100:,.2f}")
    print(f"  spread/cash P&L      ${sum(r['cash'] for r in tested)/100:,.2f}")
    print(f"  settlement P&L       ${sum(r['settle'] for r in tested)/100:,.2f}")
    print(f"  NET P&L              ${net.sum()/100:,.2f}")
    print(f"  mean per ladder-day  ${net.mean()/100:,.2f}")

    se = net.std(ddof=1) / np.sqrt(len(net))
    lo, hi = net.mean() - 1.96 * se, net.mean() + 1.96 * se
    print(f"\n  PRE-REGISTERED TEST (section 1.3)")
    print(f"    mean per ladder-day  ${net.mean()/100:+,.2f}")
    print(f"    95% CI               [${lo/100:+,.2f}, ${hi/100:+,.2f}]")
    print(f"    t-statistic          {net.mean()/se:+.2f}")
    verdict = "GO" if lo > 0 else "NO-GO"
    print(f"    -> {verdict}")

    print("\n" + "=" * 78)
    print("TAIL RISK (section 1.3 -- must be visible, not averaged away)")
    print("=" * 78)
    p = np.percentile(net, [1, 5, 25, 50, 75, 95, 99])
    print(f"\n  per-ladder-day P&L percentiles ($):")
    for lab, v in zip(["p1", "p5", "p25", "median", "p75", "p95", "p99"], p):
        print(f"    {lab:<8}{v/100:>10,.2f}")
    print(f"    worst   {net.min()/100:>10,.2f}")
    print(f"    best    {net.max()/100:>10,.2f}")
    losers = net[net < 0]
    print(f"\n  losing ladder-days   {len(losers):,} of {len(net):,} "
          f"({100*len(losers)/len(net):.1f}%)")
    print(f"  sum of worst 1%      ${np.sort(net)[:max(1,len(net)//100)].sum()/100:,.2f}")
    print(f"  worst 1% as share of gross profit: "
          f"{abs(np.sort(net)[:max(1,len(net)//100)].sum())/max(net[net>0].sum(),1):.1%}")

    inv = np.array([r["max_one_sided"] for r in tested])
    resid = np.array([r["residual"] for r in tested])
    print(f"\n  max one-sided inventory: median {np.median(inv):,.0f}  "
          f"p95 {np.percentile(inv,95):,.0f}  max {inv.max():,.0f} contracts")
    print(f"  residual at settlement : median {np.median(resid):,.0f}  "
          f"p95 {np.percentile(resid,95):,.0f}")

    print("\n" + "=" * 78)
    print("ADVERSE SELECTION (measured, not assumed)")
    print("=" * 78)
    adv = np.array([x for r in tested for x in r["adverse"]], dtype=float)
    if len(adv):
        print(f"\n  mid move after a maker fill, in our favour if positive:")
        print(f"    n           {len(adv):,}")
        print(f"    mean        {adv.mean():+.4f}c")
        print(f"    median      {np.median(adv):+.4f}c")
        print(f"    share adverse (< 0): {100*(adv<0).mean():.1f}%")
        print("\n  This is the cost src/fillsim.py cannot model and section 2.3")
        print("  requires be measured. A negative mean means fills arrive when the")
        print("  market is moving against us -- the classic maker's cost.")

    print("\n" + "=" * 78)
    print("PER-FOLD")
    print("=" * 78)
    print(f"\n{'fold':<6}{'window':<26}{'ladders':>9}{'net $':>12}{'mean $':>10}")
    print("-" * 64)
    for i, f in enumerate(folds, 1):
        rows = [r for r in tested if r["fold"] == i]
        if not rows:
            continue
        n = np.array([r["net"] for r in rows], dtype=float)
        print(f"{i:<6}{f['label']:<26}{len(rows):>9}{n.sum()/100:>12,.2f}"
              f"{n.mean()/100:>10,.2f}")

    print("\n" + "=" * 78)
    print("CAVEAT (section 1.4)")
    print("=" * 78)
    print("\n  Market making is MORE sensitive to queue position than the failed")
    print("  directional test was: the entire edge depends on being at the front of")
    print("  a thin queue, and src/fillsim.py's queue assumption is UNVALIDATED.")
    print("  Treat a GO here as weaker evidence than a GO would have been for the")
    print("  forecast strategy, and weight Phase 5.5's real-fill validation heavily.")
    print()


if __name__ == "__main__":
    np.random.seed(0)
    main()
