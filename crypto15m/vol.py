"""Method 3: high-volatility longshots (user's theory, pre-registered 2026-11-21 before any run).

    py -3.12 -m crypto15m.vol validate
    py -3.12 -m crypto15m.vol test        # frozen survivors only, once

Theory: when volatility jumps, Kalshi underprices big moves, so cheap contracts win more
often than their price says. Low hit rate, big payoff.

Rule: at minutes 3-10, if the coin's past-hour 1-minute volatility is >= R x its trailing
7-day median, buy whichever side's ask is <= C (cheapest side if both), hold to
settlement. Variants R in {1.5, 2.0} x C in {0.15, 0.25}: 4 rules, all go to validation
regardless of train, CIs widened for 4. Single-coin rule, so the per-ticker split is safe.
"""

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .common import DATA, ROOT
from .simulate import K, load, simulate, stats, fmt, subset
from .store import connect

FROZEN = os.path.join(ROOT, "config", "crypto15m_vol_frozen.json")
RESULT = os.path.join(DATA, "vol_test.json")
VARIANTS = [(r, c) for r in (1.5, 2.0) for c in (0.15, 0.25)]


def vol_ratio(D):
    sp = pd.read_sql("SELECT coin, ts, close FROM spot_minutes", connect())
    mk = D["mk"]
    ratio = np.full((len(mk), K), np.nan)
    for coin, g in sp.groupby("coin"):
        s = g.set_index("ts")["close"].sort_index()
        s = s.reindex(np.arange(s.index.min(), s.index.max() + 60, 60))  # gaps -> NaN
        v = np.log(s).diff().rolling(60, min_periods=30).std()
        med = v.rolling(7 * 24 * 60, min_periods=24 * 60).median()
        r = v / med
        rows = np.where(mk["coin"].values == coin)[0]
        o = mk["open"].values[rows]
        for k in range(1, K):
            ratio[rows, k] = r.reindex(o + 60 * k - 60).values
    return ratio


def rule(D, ratio, R, C):
    k = np.broadcast_to(np.arange(K), ratio.shape)
    m = (k >= 3) & (k <= 10) & (ratio >= R)
    py, pn = D["ask"], 1 - D["bid"]
    ey = m & (py <= C) & ~((pn <= C) & (pn < py))
    en = m & (pn <= C) & ~ey
    return np.nan_to_num(ey).astype(bool), np.nan_to_num(en).astype(bool)


def with_ratio(D):
    D = dict(D)
    D["ratio"] = vol_ratio(D)
    return D


def cmd_validate():
    D = with_ratio(load())
    T, V = subset(D, "train"), subset(D, "validation")
    print(f"high-vol share of decision minutes (ratio>=1.5): "
          f"{np.nanmean(D['ratio'][:, 3:11] >= 1.5):.1%}, (>=2.0): {np.nanmean(D['ratio'][:, 3:11] >= 2.0):.1%}\n")
    keep = []
    for R, C in VARIANTS:
        name = f"vol>={R}x median, buy side <= {C:.2f}"
        st = stats(simulate(T, *rule(T, T["ratio"], R, C), ("hold", 0, 0)), T["mk"]["day"])
        sv = stats(simulate(V, *rule(V, V["ratio"], R, C), ("hold", 0, 0)), V["mk"]["day"],
                   alpha=0.05 / len(VARIANTS))
        print("train " + fmt(name, st))
        print("valid " + fmt(name, sv))
        if sv["n"] >= 100 and sv["ci_c"][0] > 0 and sv["day_ci_c"][0] > 0:
            keep.append([R, C])
    # Context: same cheap-side rule with NO volatility filter, to see if high vol adds anything.
    for C in (0.15, 0.25):
        sb = stats(simulate(T, *rule(T, T["ratio"] * 0 + 9, 0, C), ("hold", 0, 0)), T["mk"]["day"])
        print("train " + fmt(f"(baseline, any vol) buy side <= {C:.2f}", sb))
    with open(FROZEN, "w", encoding="utf-8") as fh:
        json.dump({"frozen_at": datetime.now(timezone.utc).isoformat(), "chosen": keep[:2]}, fh, indent=2)
    print(f"\nfrozen for test: {keep[:2]}")


def cmd_test(force=False):
    chosen = json.load(open(FROZEN, encoding="utf-8"))["chosen"]
    if not chosen:
        sys.exit("nothing frozen; the test set stays unused.")
    if os.path.exists(RESULT) and not force:
        sys.exit("test already scored; it runs once.")
    D = with_ratio(load())
    Te = subset(D, "test")
    out = []
    for R, C in chosen:
        s = stats(simulate(Te, *rule(Te, Te["ratio"], R, C), ("hold", 0, 0)), Te["mk"]["day"],
                  alpha=0.05 / len(chosen))
        print(fmt(f"vol>={R}x, buy side <= {C:.2f}", s))
        out.append({"R": R, "C": C, **s,
                    "go": bool(s["n"] >= 100 and s["ci_c"][0] > 0 and s["day_ci_c"][0] > 0)})
    with open(RESULT, "w", encoding="utf-8") as fh:
        json.dump({"scored_at": datetime.now(timezone.utc).isoformat(), "results": out}, fh, indent=2)


def cmd_jolt():
    """Pre-registered 2026-11-21 (user): a jolt from 10c to 30c is a win, sell into it.
    Same 4 entries; exit when the side's bid >= 3x (or 2x) entry, else hold. 8 rules."""
    D = with_ratio(load())
    T, V = subset(D, "train"), subset(D, "validation")
    rules = [(R, C, m) for R, C in VARIANTS for m in (3.0, 2.0)]
    keep = []
    for R, C, m in rules:
        name = f"vol>={R}x, buy <= {C:.2f}, sell at {m:.0f}x"
        st = stats(simulate(T, *rule(T, T["ratio"], R, C), ("mult", m, 0)), T["mk"]["day"])
        sv = stats(simulate(V, *rule(V, V["ratio"], R, C), ("mult", m, 0)), V["mk"]["day"],
                   alpha=0.05 / len(rules))
        print("train " + fmt(name, st))
        print("valid " + fmt(name, sv))
        if sv["n"] >= 100 and sv["ci_c"][0] > 0 and sv["day_ci_c"][0] > 0:
            keep.append([R, C, m])
    for C in (0.15, 0.25):
        for m in (3.0, 2.0):
            sb = stats(simulate(T, *rule(T, T["ratio"] * 0 + 9, 0, C), ("mult", m, 0)), T["mk"]["day"])
            print("train " + fmt(f"(baseline, any vol) buy <= {C:.2f}, sell at {m:.0f}x", sb))
    with open(FROZEN.replace(".json", "_jolt.json"), "w", encoding="utf-8") as fh:
        json.dump({"frozen_at": datetime.now(timezone.utc).isoformat(), "chosen": keep[:2]}, fh, indent=2)
    print(f"\nfrozen for test: {keep[:2]}")


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "validate"
    {"validate": cmd_validate, "jolt": cmd_jolt, "test": lambda: cmd_test("--force" in sys.argv)}[c]()
