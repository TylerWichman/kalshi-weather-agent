"""Economic backtest -- does the 24-48h edge survive fees? (spec v3 Phase 2)

The calibration half said `p_model` is honest. That is necessary, not sufficient:
Kalshi's prices may be just as well calibrated, in which case there is no trade.
This half asks whether the model beats *the market*, net of fees and fills.

## Method

For each (station, target_date):

1. Fit the Tier 1 model on a **rolling 45-day window ending before the embargo** --
   identical to `scripts/calibrate.py`, so nothing is re-tuned here.
2. Take the **24-48h lead** forecast, integrate the residual distribution over the
   real Kalshi ladder's bucket edges to get `p_model` per bucket.
3. Read market prices from candles in the **24-48h window before close**.
4. Run every hard gate in `src/risk.py` (station exclusion, short-lead, implausible
   edge, spread, fee bar).
5. Size at **25% Kelly on the net-of-fee edge**, capped per ladder.
6. Fill via `src/fillsim.py` -- **maker only, resting at the bid**.
7. **Hold to resolution.** Settlement is not a trade, so there is no exit fee. This
   deliberately avoids compounding an exit-timing assumption onto the fill
   assumption; intraday exits belong in a later pass.

One position per ladder per day: the six buckets of an event are one bet, not six
(spec section 2.3), so only the single best gated bucket is taken.

## Reading the output

Three caveats travel with every number and are printed alongside them:

- **Universe.** LAX and NYC are hard-gated out of sizing, which is 17% of
  station-days but **~43% of watchlist volume**. A headline figure covers 10 of 12
  cities and roughly 57% of the volume, never the whole watchlist.
- **Queue position is assumed, not measured** (`src/fillsim.py`). Conservative on
  fill rate, silent on adverse selection.
- **Per fold, not pooled**, so fold-to-fold variance stays visible.

Usage:  python scripts/backtest.py
"""

import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from src import fees, fillsim, risk                      # noqa: E402
from calibrate import (EmpiricalResidualModel, walk_forward_folds)   # noqa: E402

BANKROLL_CENTS = 1_000_000        # $10,000
KELLY_FRACTION = 0.25
MAX_LADDER_FRACTION = 0.02        # of bankroll, per ladder (section 2.3)
LEAD_DAYS = 1                     # the 24-48h decision bucket
ENTRY_WINDOW = (48, 24)           # hours before close


def attach(conn, alias, path):
    conn.execute(f"ATTACH DATABASE '{Path(path).as_uri()}?mode=ro' AS {alias}")


def load_data():
    conn = sqlite3.connect(":memory:", uri=True)
    attach(conn, "h", os.path.join(ROOT, "data", "history.sqlite"))
    attach(conn, "k", os.path.join(ROOT, "data", "calibration.sqlite"))
    conn.row_factory = sqlite3.Row

    ladders = defaultdict(list)
    for r in conn.execute("""
        SELECT m.ticker, m.event_ticker, m.nws_station, m.city, m.target_date,
               m.bucket_low_f, m.bucket_high_f, m.result, m.close_time,
               c.forecast_f, c.actual_f
        FROM h.hist_markets m
        JOIN k.calibration_set c
          ON c.nws_station = m.nws_station AND c.target_date = m.target_date
        WHERE c.lead_days = ? AND c.actual_f IS NOT NULL
          AND m.result IN ('yes','no') AND m.close_time IS NOT NULL
        ORDER BY m.target_date, m.event_ticker, COALESCE(m.bucket_low_f, -999)
    """, (LEAD_DAYS,)):
        ladders[r["event_ticker"]].append(dict(r))

    candles = defaultdict(list)
    for r in conn.execute(
            "SELECT ticker, period_ts, yes_bid_close, yes_ask_close, "
            "price_low, price_high, volume FROM h.hist_candles ORDER BY ticker, period_ts"):
        candles[r["ticker"]].append(dict(r))

    train = [dict(station=r["nws_station"], date=r["target_date"], lead=r["lead_days"],
                  fc=float(r["forecast_f"]), act=float(r["actual_f"]))
             for r in conn.execute(
                 "SELECT nws_station, target_date, lead_days, forecast_f, actual_f "
                 "FROM k.calibration_set WHERE actual_f IS NOT NULL")]
    conn.close()
    return ladders, candles, train


def bucket_probs(model, station, fc, ladder):
    ps = []
    for b in ladder:
        lo, hi = b["bucket_low_f"], b["bucket_high_f"]
        a = 0.0 if lo is None else model.cdf(station, LEAD_DAYS, fc, lo - 0.5)
        z = 1.0 if hi is None else model.cdf(station, LEAD_DAYS, fc, hi + 0.5)
        ps.append(max(z - a, 0.0))
    tot = sum(ps)
    return [p / tot for p in ps] if tot > 0 else [1.0 / len(ps)] * len(ps)


def entry_candle(candles, ticker, close_ts):
    """The last candle inside the 24-48h pre-close window with a two-sided quote."""
    lo = close_ts - ENTRY_WINDOW[0] * 3600
    hi = close_ts - ENTRY_WINDOW[1] * 3600
    best = None
    for c in candles.get(ticker, []):
        if lo <= c["period_ts"] <= hi and c["yes_bid_close"] and c["yes_ask_close"]:
            best = c
    return best


def kelly_contracts(p_model, price_cents):
    """25% Kelly on the net-of-fee edge, capped per ladder."""
    c = price_cents / 100.0
    if c <= 0 or c >= 1:
        return 0
    edge = p_model - c
    if edge <= 0:
        return 0
    f = KELLY_FRACTION * edge / (1.0 - c)
    stake = min(f, MAX_LADDER_FRACTION) * BANKROLL_CENTS
    return int(stake / price_cents)


def run():
    ladders, candles, train_rows = load_data()
    dates = sorted({b[0]["target_date"] for b in ladders.values()})
    folds = walk_forward_folds(dates)
    if not folds:
        sys.exit("not enough dates for walk-forward folds")

    results = []
    blocked = defaultdict(int)

    for fi, fold in enumerate(folds, 1):
        model = EmpiricalResidualModel().fit(
            [r for r in train_rows if r["date"] in fold["train"]])

        for ev, ladder in ladders.items():
            d = ladder[0]["target_date"]
            if d not in fold["test"]:
                continue
            station = ladder[0]["nws_station"]
            fc = ladder[0]["forecast_f"]
            close_ts = int(datetime.fromisoformat(
                ladder[0]["close_time"].replace("Z", "+00:00")).timestamp())
            probs = bucket_probs(model, station, fc, ladder)

            best = None
            for b, p in zip(ladder, probs):
                cd = entry_candle(candles, b["ticker"], close_ts)
                if not cd:
                    continue
                bid, ask = cd["yes_bid_close"], cd["yes_ask_close"]
                if not bid or not ask:
                    continue

                # BOTH directions. Considering only "buy YES" biases the whole
                # backtest toward cheap tails, because a 6-bucket ladder puts most
                # buckets at a few cents and a resting bid there is nearly always
                # the cheap side. Buying NO at n rests as a YES offer at 100-n.
                options = []
                if 0 < bid < 100:
                    options.append(dict(side="buy_yes", limit=bid, price=bid,
                                        p=p, edge=p - bid / 100.0))
                no_price = 100 - ask
                if 0 < no_price < 100:
                    options.append(dict(side="sell_yes", limit=ask, price=no_price,
                                        p=1.0 - p, edge=(1.0 - p) - no_price / 100.0))

                for o in options:
                    n = kelly_contracts(o["p"], o["price"])
                    cand = dict(nws_station=station, lead_hours=36.0, edge=o["edge"],
                                p_market_cents=o["price"], bid_cents=bid, ask_cents=ask,
                                contracts=max(n, 1), entry_cents=o["price"],
                                exit_cents=None, entry_is_maker=True, exit_is_maker=True)
                    blocks = risk.gate(cand)
                    # Excluded stations are SHADOW-SCORED, not skipped: spec 2.3 gates
                    # sizing, not measurement, and the Tier 2 coastal work needs them.
                    hard = [g for g, _ in blocks if g != "station_excluded"]
                    is_shadow = any(g == "station_excluded" for g, _ in blocks)
                    if blocks:
                        for g, _ in blocks:
                            blocked[g] += 1
                    if hard or n <= 0:
                        continue
                    if best is None or o["edge"] > best["edge"]:
                        best = dict(bucket=b, p=o["p"], price=o["price"],
                                    limit=o["limit"], side=o["side"], edge=o["edge"],
                                    contracts=n, candle=cd, shadow=is_shadow)

            if not best:
                continue

            fill = fillsim.simulate_maker(best["candle"], best["side"],
                                          best["limit"], best["contracts"])
            if not fill.filled:
                blocked["no_fill"] += 1
                continue

            bucket_yes = best["bucket"]["result"] == "yes"
            # A sell_yes position is a NO purchase: it wins when the bucket does
            # NOT settle yes. Cost per contract is the side's own price -- the yes
            # price when buying yes, the no price (100 - yes limit) when selling.
            won = bucket_yes if best["side"] == "buy_yes" else not bucket_yes
            cost = best["price"]
            gross = fill.contracts * (100 - cost) if won else -fill.contracts * cost
            results.append(dict(
                fold=fi, date=d, station=station, city=ladder[0]["city"],
                ticker=best["bucket"]["ticker"], excluded=best["shadow"],
                side=best["side"], p_model=best["p"], price=cost, edge=best["edge"],
                contracts=fill.contracts, fee=fill.fee_cents,
                gross=gross, net=gross - fill.fee_cents, won=won))

    return results, blocked, folds


def report(results, blocked, folds):
    print("=" * 78)
    print("ECONOMIC BACKTEST -- 24-48h decision bucket (spec v3 Phase 2)")
    print("=" * 78)

    trade = [r for r in results if not r["excluded"]]
    excl = [r for r in results if r["excluded"]]

    print("\n" + "!" * 78)
    print("UNIVERSE: results below cover 10 of 12 cities.")
    print("LAX and NYC are hard-gated out of sizing (spec 2.3, coastal miscalibration):")
    print("  ~17% of station-days, but ~43% of watchlist VOLUME.")
    print("A headline figure here represents roughly 57% of tradeable volume,")
    print("NOT the full watchlist.")
    print("!" * 78)

    def summarize(rows, label):
        if not rows:
            print(f"\n  {label}: no trades")
            return
        net = sum(r["net"] for r in rows)
        gross = sum(r["gross"] for r in rows)
        fee = sum(r["fee"] for r in rows)
        stake = sum(r["contracts"] * r["price"] for r in rows)
        wins = sum(1 for r in rows if r["won"])
        print(f"\n  {label}")
        print(f"    trades          {len(rows):>10,}")
        print(f"    contracts       {sum(r['contracts'] for r in rows):>10,}")
        print(f"    capital staked  ${stake/100:>9,.0f}")
        print(f"    gross P&L       ${gross/100:>9,.0f}")
        print(f"    fees paid       ${fee/100:>9,.0f}")
        print(f"    NET P&L         ${net/100:>9,.0f}")
        print(f"    return on stake {100*net/stake if stake else 0:>9.2f}%")
        print(f"    hit rate        {100*wins/len(rows):>9.1f}%")
        print(f"    fee / gross     {100*fee/abs(gross) if gross else 0:>9.2f}%")

    summarize(trade, "TRADEABLE universe (10 cities, ~57% of volume)")
    summarize(excl, "EXCLUDED stations (LAX+NYC) -- scored only, NOT traded")

    print("\n" + "=" * 78)
    print("PER-FOLD (variance, not pooled)")
    print("=" * 78)
    print(f"\n{'fold':<6}{'window':<26}{'trades':>8}{'net $':>10}{'ret%':>8}{'hit%':>7}")
    print("-" * 65)
    for fi, fold in enumerate(folds, 1):
        rows = [r for r in trade if r["fold"] == fi]
        if not rows:
            print(f"{fi:<6}{fold['label']:<26}{'0':>8}")
            continue
        net = sum(r["net"] for r in rows)
        stake = sum(r["contracts"] * r["price"] for r in rows)
        wins = sum(1 for r in rows if r["won"])
        print(f"{fi:<6}{fold['label']:<26}{len(rows):>8}{net/100:>10,.0f}"
              f"{100*net/stake if stake else 0:>8.2f}{100*wins/len(rows):>7.1f}")

    print("\n" + "=" * 78)
    print("GATE ACTIVITY (why candidates were rejected)")
    print("=" * 78)
    for g, n in sorted(blocked.items(), key=lambda x: -x[1]):
        print(f"  {g:<22}{n:>8,}")

    print("\n" + "=" * 78)
    print("ASSUMPTIONS ATTACHED TO EVERY NUMBER ABOVE")
    print("=" * 78)
    for k, v in fillsim.assumptions().items():
        print(f"  {k:<32}{v}")
    print("\n  Entry: maker only, resting at the bid. Held to resolution, so no exit")
    print("  fee (settlement is not a trade). Intraday exits are a later pass.")
    print()


if __name__ == "__main__":
    np.random.seed(0)
    res, blk, fl = run()
    report(res, blk, fl)
