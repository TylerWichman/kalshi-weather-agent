"""KXRAIN market-calibration test -- implements docs/phase3-kxrain-preregistration.md.

That document is the authority. Section references below point into it, and any
discrepancy between this script and it is a bug in this script.

    python scripts/rain_calibration.py gate1           # development set, early kill
    python scripts/rain_calibration.py gate1 --freeze  # also writes config/kxrain_frozen.json
    python scripts/rain_calibration.py gate2           # test set, run ONCE after 26OCT24 settles

Model-free: the only inputs are Kalshi's own quotes (hourly candles) and Kalshi's
own `result`. No weather data is read.
"""

import argparse
import json
import math
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.fees import trade_fee_cents          # noqa: E402
from src.kalshi import parse_event_date       # noqa: E402

DB = os.path.join(ROOT, "data", "candidates.sqlite")
FROZEN = os.path.join(ROOT, "config", "kxrain_frozen.json")

SERIES = "KXRAIN"
FEE_MULTIPLIER = 1.0          # /series/KXRAIN: fee_type=quadratic, fee_multiplier=1

# §3 -- fixed at registration, never tuned.
MARGIN = 0.03                 # (f)
BAND = (5, 95)                # (g) cents, price of the side bought
DECISION_HOUR_UTC = 0         # (b)
DIAG_HOUR_UTC = 12            # §5 diagnostic only

# §4
DEV_FIRST, DEV_LAST = date(2026, 7, 15), date(2026, 9, 23)
TEST_FIRST = date(2026, 9, 27)
TEST_EVENTS = 28                             # Amendment 2 (was 45)
TEST_NOMINAL_LAST = date(2026, 10, 24)       # Amendment 2 (was 2026-11-10)
TEST_EXTEND_LAST = date(2026, 11, 24)        # Amendment 2 (was 2026-12-10)

# §5
BOOT = 10_000
MIN_TRADES = 100
MIN_DOLLARS_PER_DAY = 5.0
DEPTH_CAP = 100
BOOK_WINDOW_S = 600
BOOK_GUARD_S = 60             # Amendment 3: only snapshots taken >= 60 s before 00:00 UTC
MAX_MISSING_BOOK = 0.10
MAX_DAY_SHARE = 0.25
MAX_CITY_SHARE = 0.40

# Additional analysis, registered 2026-09-24 before any test-period data existed
# (pre-registration Amendment 1). Reported after the verdict; never changes what
# is traded or the verdict. The 30-50c band was found by looking at Gate 1, so any
# result in it can only motivate a NEW, separately pre-registered hypothesis.
BAND_EDGES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]   # by market mid, cents
FLAGGED_BAND = (30, 50)
FLAG_MIN_TRADES = 30
FLAG_MIN_LIFT_C = 2.0

# §5 diagnostic: per-city and per-region breakdown, labelled thin. US Census regions.
REGION = {
    "BOS": "Northeast", "PVD": "Northeast", "NYC": "Northeast", "EWR": "Northeast",
    "TTN": "Northeast", "PHIL": "Northeast", "PIT": "Northeast",
    "CHI": "Midwest", "MKE": "Midwest", "MIN": "Midwest", "CMH": "Midwest",
    "DC": "South", "ATL": "South", "MIA": "South", "LEX": "South", "NOLA": "South",
    "HOU": "South", "AUS": "South", "SATX": "South", "DAL": "South", "CLL": "South",
    "OKC": "South",
    "DEN": "West", "PHX": "West", "LV": "West", "LAX": "West", "SFO": "West", "SEA": "West",
}


# --------------------------------------------------------------------------- #
# Data

def decision_ts(d, hour):
    return int(datetime(d.year, d.month, d.day, hour, tzinfo=timezone.utc).timestamp())


def load(conn, first, last, hour):
    """One row per market with a two-sided quote in the candle ending at `hour` UTC.

    §3(c): a market missing either side is skipped. A 0c bid or 100c ask is
    Kalshi's encoding of an empty side, so it counts as missing.
    """
    rows, skipped = [], defaultdict(int)
    q = conn.execute(
        "SELECT ticker, event_ticker, result FROM markets WHERE series_ticker=?", (SERIES,))
    for ticker, event, result in q:
        d = parse_event_date(event)
        if d is None or not (first <= d <= last):
            continue
        if result not in ("yes", "no"):
            skipped["unsettled"] += 1
            continue
        ts = decision_ts(d, hour)
        c = conn.execute(
            "SELECT yes_bid_close, yes_ask_close FROM candles "
            "WHERE ticker=? AND interval_min=60 AND period_ts=?", (ticker, ts)).fetchone()
        if c is None:
            skipped["no candle at decision time"] += 1
            continue
        bid, ask = c
        if bid is None or ask is None or bid <= 0 or ask >= 100:
            skipped["one-sided quote"] += 1
            continue
        if bid > ask:
            skipped["crossed quote"] += 1
            continue
        rows.append(dict(ticker=ticker, event=event, day=d, city=ticker.rsplit("-", 1)[1],
                         bid=bid, ask=ask, mid=(bid + ask) / 2.0,
                         y=1 if result == "yes" else 0, ts=ts))
    return rows, dict(skipped)


# --------------------------------------------------------------------------- #
# §3(e) recalibration: p = sigmoid(a + b * logit(mid/100)), maximum likelihood

def logit(p):
    return math.log(p / (1 - p))


def sigmoid(z):
    return 1.0 / (1.0 + math.exp(-z))


def fit(rows):
    x = np.array([logit(r["mid"] / 100.0) for r in rows])
    y = np.array([r["y"] for r in rows], dtype=float)
    X = np.column_stack([np.ones_like(x), x])
    w = np.array([0.0, 1.0])                   # start at the identity (market as-is)
    for _ in range(100):
        p = 1.0 / (1.0 + np.exp(-(X @ w)))
        g = X.T @ (y - p)
        H = -(X.T * (p * (1 - p))) @ X
        step = np.linalg.solve(H, g)
        w = w - step
        if np.max(np.abs(step)) < 1e-10:
            break
    return float(w[0]), float(w[1])


def p_model(r, a, b):
    return sigmoid(a + b * logit(r["mid"] / 100.0))


# --------------------------------------------------------------------------- #
# §3(d)(f)(g)(h) entry rule and settlement P&L, 1 contract, taker

def decide(r, a, b):
    """Returns (side, price_cents, fee_cents) or None."""
    p = p_model(r, a, b)
    ask, no_price = r["ask"], 100 - r["bid"]
    fee_yes = trade_fee_cents(1, ask, is_maker=False, fee_multiplier=FEE_MULTIPLIER)
    fee_no = trade_fee_cents(1, no_price, is_maker=False, fee_multiplier=FEE_MULTIPLIER)
    yes = (BAND[0] <= ask <= BAND[1]) and (p - ask / 100.0 >= fee_yes / 100.0 + MARGIN)
    no = (BAND[0] <= no_price <= BAND[1]) and \
         ((1 - p) - no_price / 100.0 >= fee_no / 100.0 + MARGIN)
    assert not (yes and no), f"both sides qualify on {r['ticker']}: impossible unless crossed"
    if yes:
        return "yes", ask, fee_yes
    if no:
        return "no", no_price, fee_no
    return None


def settle(r, side, price, fee):
    won = (r["y"] == 1) if side == "yes" else (r["y"] == 0)
    return (100 if won else 0) - price - fee


def trades_for(rows, a, b):
    out = []
    for r in rows:
        d = decide(r, a, b)
        if d:
            side, price, fee = d
            out.append(dict(r, side=side, price=price, fee=fee,
                            pnl=settle(r, side, price, fee)))
    return out


# --------------------------------------------------------------------------- #
# Statistics

def day_bootstrap(trades, seed=20260924):
    """95% CI of mean net P&L per trade, resampling days as units (§5 Gate 2.1)."""
    by_day = defaultdict(list)
    for t in trades:
        by_day[t["day"]].append(t["pnl"])
    days = list(by_day)
    sums = np.array([sum(by_day[d]) for d in days], dtype=float)
    cnts = np.array([len(by_day[d]) for d in days], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(days), size=(BOOT, len(days)))
    means = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def summarize(label, trades):
    if not trades:
        print(f"  {label}: no trades")
        return
    pnl = [t["pnl"] for t in trades]
    lo, hi = day_bootstrap(trades)
    n_yes = sum(t["side"] == "yes" for t in trades)
    print(f"  {label}: {len(trades)} trades ({n_yes} YES / {len(trades) - n_yes} NO) "
          f"on {len({t['day'] for t in trades})} days")
    print(f"    mean net {np.mean(pnl):+.2f}c/contract   day-block 95% CI "
          f"[{lo:+.2f}, {hi:+.2f}]   total {sum(pnl):+,.0f}c   "
          f"hit {np.mean([p > 0 for p in pnl]):.1%}")
    for side in ("yes", "no"):
        s = [t["pnl"] for t in trades if t["side"] == side]
        if s:
            print(f"    {side.upper():<3} {len(s):>4} trades  mean {np.mean(s):+.2f}c  "
                  f"total {sum(s):+,.0f}c")


def reliability(rows, label):
    """§5 diagnostic: market calibration at a given hour, and Brier decomposition."""
    print(f"\n  Market reliability, {label} ({len(rows)} quoted markets, "
          f"{len({r['day'] for r in rows})} days)")
    print(f"    {'mid band':<10}{'n':>6}{'mean mid':>10}{'freq YES':>10}{'gap':>8}")
    edges = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    y = np.array([r["y"] for r in rows], dtype=float)
    f = np.array([r["mid"] / 100 for r in rows])
    base = y.mean() if len(y) else 0
    rel = res = 0.0
    for lo, hi in zip(edges, edges[1:]):
        m = (f * 100 >= lo) & (f * 100 < hi if hi < 100 else f * 100 <= hi)
        if m.sum() == 0:
            continue
        fb, ob = f[m].mean(), y[m].mean()
        rel += m.sum() * (fb - ob) ** 2
        res += m.sum() * (ob - base) ** 2
        print(f"    {lo:>3}-{hi:<5}{m.sum():>7}{fb:>10.3f}{ob:>10.3f}{ob - fb:>+8.3f}")
    n = max(len(y), 1)
    print(f"    Brier {np.mean((f - y) ** 2):.4f} = reliability {rel / n:.4f} "
          f"- resolution {res / n:.4f} + uncertainty {base * (1 - base):.4f}"
          f"   (base rate {base:.3f})")


# --------------------------------------------------------------------------- #
# Gate 1 -- §5, development set, leave-one-calendar-week-out

def gate1(conn, freeze):
    rows, skipped = load(conn, DEV_FIRST, DEV_LAST, DECISION_HOUR_UTC)
    events = {r["event"] for r in rows}
    print(f"GATE 1 -- development {DEV_FIRST} .. {DEV_LAST}")
    print(f"  {len(rows)} quoted markets across {len(events)} events at "
          f"{DECISION_HOUR_UTC:02d}:00 UTC; skipped {skipped}")

    week = lambda d: d.isocalendar()[:2]
    weeks = sorted({week(r["day"]) for r in rows})
    oof, folds = [], []
    for w in weeks:
        train = [r for r in rows if week(r["day"]) != w]
        test = [r for r in rows if week(r["day"]) == w]
        a, b = fit(train)
        t = trades_for(test, a, b)
        oof += t
        folds.append((w, len(test), a, b, len(t), sum(x["pnl"] for x in t)))

    print(f"\n  Leave-one-week-out folds ({len(weeks)}):")
    print(f"    {'ISO week':<10}{'mkts':>6}{'alpha':>9}{'beta':>8}{'trades':>8}{'net c':>9}")
    for w, n, a, b, nt, pnl in folds:
        print(f"    {w[0]}-W{w[1]:02d}  {n:>6}{a:>+9.3f}{b:>8.3f}{nt:>8}{pnl:>+9.0f}")

    print()
    summarize("OUT-OF-FOLD", oof)
    mean_oof = float(np.mean([t["pnl"] for t in oof])) if oof else 0.0
    passed = bool(oof) and mean_oof > 0

    a, b = fit(rows)
    full = trades_for(rows, a, b)
    print(f"\n  Full-sample fit: alpha {a:+.4f}  beta {b:.4f}  "
          f"(identity = 0, 1; in-sample, NOT the gate)")
    summarize("IN-SAMPLE (diagnostic)", full)
    # Where the frozen curve says the market is wrong, and which way.
    cross = None
    if abs(b - 1) > 1e-9:
        z = -a / (b - 1)        # logit where p == mid
        cross = 100 * sigmoid(z)
    print(f"    recalibrated p - mid at mid = 10/30/50/70/90c: " + " ".join(
        f"{100 * (sigmoid(a + b * logit(m / 100)) - m / 100):+.1f}" for m in (10, 30, 50, 70, 90))
          + (f"   (curve crosses market at {cross:.1f}c)" if cross and 0 < cross < 100 else ""))

    reliability(rows, f"{DECISION_HOUR_UTC:02d}:00 UTC (decision time)")
    diag, _ = load(conn, DEV_FIRST, DEV_LAST, DIAG_HOUR_UTC)
    reliability(diag, f"{DIAG_HOUR_UTC:02d}:00 UTC (observations available -- control)")

    print("\n" + "=" * 78)
    print(f"GATE 1: out-of-fold mean net {mean_oof:+.2f}c/contract over {len(oof)} trades "
          f"-> {'PASS (proceed to Gate 2)' if passed else 'NO-GO'}")
    print("=" * 78)

    if freeze:
        if not passed:
            print("Not freezing: Gate 1 is NO-GO, the test period is not run (§5).")
            return passed
        n_yes = sum(t["side"] == "yes" for t in full)
        frozen = dict(
            registered_in="docs/phase3-kxrain-preregistration.md",
            frozen_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            alpha=a, beta=b, margin=MARGIN, band_cents=list(BAND),
            decision_hour_utc=DECISION_HOUR_UTC,
            dev=dict(first=str(DEV_FIRST), last=str(DEV_LAST), markets=len(rows),
                     events=len(events), oof_trades=len(oof), oof_mean_net_c=mean_oof,
                     insample_trades=len(full), insample_yes=n_yes,
                     insample_no=len(full) - n_yes),
            direction=dict(
                sides_traded=sorted({t["side"] for t in full}),
                # §5 Gate 2.5 operationalised: each side the frozen rule trades must
                # make money on the test set on its own, so a profit cannot come
                # from the opposite side of the mispricing that was registered.
                rule="every side with >= 20% of test trades must have mean net > 0"),
        )
        os.makedirs(os.path.dirname(FROZEN), exist_ok=True)
        json.dump(frozen, open(FROZEN, "w"), indent=2)
        print(f"Frozen -> {os.path.relpath(FROZEN, ROOT)}. Commit it before "
              f"{TEST_FIRST} 00:00 UTC.")
    return passed


# --------------------------------------------------------------------------- #
# Gate 2 -- §5, test set, evaluated once

def book_size(conn, t):
    """Contracts shown at the best price on the side bought, from the latest snapshot
    taken 23:50:00-23:59:00 UTC (§5 Gate 2.3 with Amendment 3's 60 s buffer). Runs the
    00:00 guard discarded never reach the books table. None if no snapshot."""
    r = conn.execute(
        "SELECT yes_levels, no_levels FROM books WHERE ticker=? AND snap_ts BETWEEN ? AND ? "
        "ORDER BY snap_ts DESC LIMIT 1", (t["ticker"], t["ts"] - BOOK_WINDOW_S, t["ts"] - BOOK_GUARD_S)).fetchone()
    if r is None:
        return None
    # Buying YES lifts resting NO bids; buying NO lifts resting YES bids.
    levels = json.loads(r[1] if t["side"] == "yes" else r[0])
    return min(DEPTH_CAP, levels[0][1]) if levels else 0


def gate2(conn):
    fz = json.load(open(FROZEN))
    a, b = fz["alpha"], fz["beta"]
    settled_days = sorted({parse_event_date(e) for (e,) in conn.execute(
        "SELECT DISTINCT event_ticker FROM markets WHERE series_ticker=? AND result IN ('yes','no')",
        (SERIES,)) if parse_event_date(e) and parse_event_date(e) >= TEST_FIRST})
    if len(settled_days) < TEST_EVENTS:
        sys.exit(f"Only {len(settled_days)}/{TEST_EVENTS} test events settled and loaded. "
                 f"Load with `python -m src.candidates history --series KXRAIN` and wait.")

    last = settled_days[TEST_EVENTS - 1]
    rows, skipped = load(conn, TEST_FIRST, last, DECISION_HOUR_UTC)
    trades = trades_for(rows, a, b)
    # Gate 2.2: extend to 26DEC10 or 100 trades, whichever first.
    if len(trades) < MIN_TRADES:
        for d in settled_days[TEST_EVENTS:]:
            if d > TEST_EXTEND_LAST or len(trades) >= MIN_TRADES:
                break
            more, _ = load(conn, d, d, DECISION_HOUR_UTC)
            rows += more
            trades += trades_for(more, a, b)
            last = d

    days = sorted({r["day"] for r in rows})
    print(f"GATE 2 -- test {TEST_FIRST} .. {last}  ({len(days)} days, {len(rows)} quoted "
          f"markets; skipped {skipped})")
    print(f"  frozen alpha {a:+.4f} beta {b:.4f} (at {fz['frozen_at']})\n")
    summarize("TEST", trades)

    checks = {}
    pnl = [t["pnl"] for t in trades]
    lo, hi = day_bootstrap(trades) if trades else (0, 0)
    checks["1 profitable, CI > 0"] = bool(trades) and np.mean(pnl) > 0 and lo > 0
    checks["2 >= 100 trades"] = len(trades) >= MIN_TRADES

    sizes = [book_size(conn, t) for t in trades]
    missing = sum(s is None for s in sizes) / max(len(trades), 1)
    dollars = sum(t["pnl"] * s for t, s in zip(trades, sizes) if s) / 100.0
    per_day = dollars / max(len(days), 1)
    print(f"\n  Depth-sized: ${dollars:,.2f} net over {len(days)} days = ${per_day:.2f}/day; "
          f"{missing:.1%} of trades had no snapshot within 10 min")
    if missing > MAX_MISSING_BOOK:
        print("  >10% of trades lack a book snapshot: §5 Gate 2.3 says extend the period. "
              "VERDICT WITHHELD.")
        return
    checks["3 >= $5/day at book depth"] = per_day >= MIN_DOLLARS_PER_DAY

    mid = days[len(days) // 2]
    h1 = sum(t["pnl"] for t in trades if t["day"] < mid)
    h2 = sum(t["pnl"] for t in trades if t["day"] >= mid)
    print(f"  halves split at {mid}: {h1:+,.0f}c / {h2:+,.0f}c")
    checks["4 both halves positive"] = h1 > 0 and h2 > 0

    total = sum(pnl)
    by_day, by_city = defaultdict(float), defaultdict(float)
    for t in trades:
        by_day[t["day"]] += t["pnl"]
        by_city[t["city"]] += t["pnl"]
    day_share = max(by_day.values()) / total if total > 0 else float("inf")
    city_share = max(by_city.values()) / total if total > 0 else float("inf")
    side_ok = all(np.mean([t["pnl"] for t in trades if t["side"] == s]) > 0
                  for s in ("yes", "no")
                  if sum(t["side"] == s for t in trades) >= 0.2 * len(trades))
    print(f"  largest day {day_share:.1%} of P&L, largest city {city_share:.1%}; "
          f"every major side profitable: {side_ok}")
    checks["5 mechanism (sides, day<=25%, city<=40%)"] = (
        side_ok and day_share <= MAX_DAY_SHARE and city_share <= MAX_CITY_SHARE)

    print("\n" + "=" * 78)
    for k, v in checks.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"GATE 2: {'GO' if all(checks.values()) else 'NO-GO'}")
    print("=" * 78)
    additional_analysis(conn, rows, trades, last)


def in_band(mid, lo, hi):
    return lo <= mid < hi or (hi == 100 and mid == 100)


def additional_analysis(conn, rows, trades, last):
    """Amendment 1. Descriptive only: the verdict above is already final."""
    print("\nADDITIONAL ANALYSIS -- Amendment 1. NOT part of the verdict above, and")
    print("not a basis for changing this rule. Trades are the frozen rule's, unaltered.\n")
    overall = float(np.mean([t["pnl"] for t in trades])) if trades else 0.0
    print(f"  Frozen-rule trades by market mid at decision time (all trades: "
          f"{len(trades)}, mean {overall:+.2f}c)")
    print(f"    {'mid band':<10}{'trades':>7}{'mean net':>10}{'total':>9}   day-block 95% CI")
    for lo, hi in zip(BAND_EDGES, BAND_EDGES[1:]):
        b = [t for t in trades if in_band(t["mid"], lo, hi)]
        if not b:
            continue
        ci = day_bootstrap(b) if len(b) >= 10 else None
        print(f"    {lo:>3}-{hi:<5}{len(b):>8}{np.mean([t['pnl'] for t in b]):>+10.2f}"
              f"{sum(t['pnl'] for t in b):>+9.0f}   "
              + (f"[{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci else "(n < 10)"))

    lo, hi = FLAGGED_BAND
    f = [t for t in trades if in_band(t["mid"], lo, hi)]
    fm = float(np.mean([t["pnl"] for t in f])) if f else float("nan")
    trigger = len(f) >= FLAG_MIN_TRADES and fm - overall >= FLAG_MIN_LIFT_C
    print(f"\n  Flagged {lo}-{hi}c band (found in Gate 1): {len(f)} trades, mean {fm:+.2f}c, "
          f"lift {fm - overall:+.2f}c over all trades")
    print("  -> " + ("MEETS the registered trigger (>= 30 trades, >= +2c lift): write a NEW "
                     "pre-registration with its own forward test. It does not change this "
                     "verdict." if trigger else
                     "does not meet the registered trigger for a new hypothesis."))

    print(f"\n  By region and city -- THIN: each slice is a handful of trades on correlated days.")
    for key, label in ((lambda t: REGION.get(t["city"], "(unmapped)"), "region"),
                       (lambda t: t["city"], "city")):
        g = defaultdict(list)
        for t in trades:
            g[key(t)].append(t["pnl"])
        print(f"    {label:<11}" + "  ".join(
            f"{k} {len(v)}/{np.mean(v):+.1f}c" for k, v in sorted(g.items())))

    reliability(rows, f"test, {DECISION_HOUR_UTC:02d}:00 UTC (decision time)")
    diag, _ = load(conn, TEST_FIRST, last, DIAG_HOUR_UTC)
    reliability(diag, f"test, {DIAG_HOUR_UTC:02d}:00 UTC (observations available -- control)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gate", choices=["gate1", "gate2"])
    ap.add_argument("--freeze", action="store_true")
    args = ap.parse_args()
    conn = sqlite3.connect(DB)
    if args.gate == "gate1":
        gate1(conn, args.freeze)
    else:
        gate2(conn)


if __name__ == "__main__":
    main()
