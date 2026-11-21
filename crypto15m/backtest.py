"""Pattern backtests for the 15-min crypto markets, with a frozen train/test split.

    py -3.12 -m crypto15m.backtest build     # backfill -> data/crypto15m/dataset.parquet
    py -3.12 -m crypto15m.backtest train     # explore on TRAIN only, freeze rules
    py -3.12 -m crypto15m.backtest test      # score the frozen rules on TEST, once

Split: each market (15-min window) goes to test if sha256(ticker) maps below 0.30, else
train. It's deterministic, so markets settled later get assigned the same way and the live
forward record can be scored with the identical rule. (The user chose a random split by
window; the day-block CI below is reported alongside as a diagnostic, since neighboring
windows share a regime.)

A trade = buy 1 contract at the Kalshi ask at a minute's close, pay the taker fee, hold to
settlement. At most one trade per market per rule (its first trigger), so a market that
triggers at every minute counts once.
"""

import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from .common import COINS, DATA, ROOT, fair_yes, fee, read_jsonl

DATASET = os.path.join(DATA, "dataset.parquet")
FROZEN = os.path.join(ROOT, "config", "crypto15m_frozen.json")
RESULT = os.path.join(DATA, "backtest.json")
TEST_FRAC = 0.30


def is_test(ticker):
    h = int(hashlib.sha256(ticker.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return h < TEST_FRAC


# ------------------------------------------------------------------ build

def build():
    rows = []
    for coin in COINS:
        markets = read_jsonl(os.path.join(DATA, f"markets_{coin}.jsonl"))
        candles = {r["ticker"]: r["c"] for r in read_jsonl(os.path.join(DATA, f"candles_{coin}.jsonl"))}
        spot = {r[0]: r for r in read_jsonl(os.path.join(DATA, f"spot_{coin}.jsonl"))}
        markets.sort(key=lambda m: m["close"])
        hist = []  # prior results, same coin
        for m in markets:
            res = 1 if m["result"] == "yes" else 0 if m["result"] == "no" else None
            prev = hist[-3:]
            hist.append(res)
            if res is None or not m["strike"] or m["ticker"] not in candles:
                continue
            o, c = m["open"], m["close"]
            pre = spot.get(o - 60)
            if not pre:
                continue
            basis = m["strike"] / ((pre[3] + pre[4]) / 2)
            kc = {r[0]: r for r in candles[m["ticker"]]}
            for k in range(1, 15):
                T = o + 60 * k
                kr, sr = kc.get(T), spot.get(T - 60)
                if not kr or not sr or kr[1] is None or kr[2] is None:
                    continue
                closes = [spot[t][4] for t in range(T - 61 * 60, T, 60) if t in spot]
                if len(closes) < 30:
                    continue
                lr = np.diff(np.log(closes))
                vol = float(np.std(lr, ddof=1))
                adj = sr[4] * basis
                left = c - T
                p = fair_yes(adj, m["strike"], left, vol / math.sqrt(60))
                rows.append({
                    "coin": coin, "ticker": m["ticker"], "open": o, "minute": k, "left": left,
                    "strike": m["strike"], "spot": adj, "basis": basis, "vol1m": vol,
                    "move": math.log(adj / m["strike"]),
                    "z": math.log(adj / m["strike"]) / (vol / math.sqrt(60) * math.sqrt(left)),
                    "fair": p, "bid": kr[1], "ask": kr[2], "kvol": kr[4] or 0.0,
                    "prev1": prev[-1] if len(prev) >= 1 else None,
                    "prev2": prev[-2] if len(prev) >= 2 else None,
                    "prev3": prev[-3] if len(prev) >= 3 else None,
                    "hour_et": int(pd.Timestamp(o, unit="s", tz="UTC").tz_convert("America/New_York").hour),
                    "yes": res,
                })
    df = pd.DataFrame(rows)
    df["test"] = df["ticker"].map(is_test)
    df["day"] = pd.to_datetime(df["open"], unit="s", utc=True).dt.tz_convert("America/New_York").dt.date.astype(str)
    df.to_parquet(DATASET)
    n = df.groupby("test")["ticker"].nunique()
    print(f"rows {len(df)}; markets train {n.get(False, 0)} test {n.get(True, 0)}; "
          f"days {df['day'].min()}..{df['day'].max()}")


# ------------------------------------------------------------------ scoring

def trades(df, side_fn):
    """side_fn(df) -> Series of 'yes'/'no'/None per row. First trigger per market."""
    side = side_fn(df)
    t = df[side.notna()].copy()
    t["side"] = side[side.notna()]
    t = t.sort_values(["ticker", "minute"]).groupby("ticker", as_index=False).first()
    t["price"] = np.where(t["side"] == "yes", t["ask"], 1 - t["bid"])
    t = t[(t["price"] > 0) & (t["price"] < 1)]
    t["fee"] = t["price"].map(fee)
    win = np.where(t["side"] == "yes", t["yes"] == 1, t["yes"] == 0)
    t["pnl"] = win.astype(float) - t["price"] - t["fee"]
    return t


def ci(pnl, groups=None, n=2000, seed=7, alpha=0.05):
    """95% bootstrap CI of mean pnl; resample groups (days) when given, else trades."""
    rng = np.random.default_rng(seed)
    if len(pnl) < 5:
        return (float("nan"), float("nan"))
    if groups is None:
        v = pnl.values
        ms = [v[rng.integers(0, len(v), len(v))].mean() for _ in range(n)]
    else:
        g = {k: x.values for k, x in pnl.groupby(groups)}
        keys = list(g)
        ms = []
        for _ in range(n):
            pick = rng.integers(0, len(keys), len(keys))
            v = np.concatenate([g[keys[i]] for i in pick])
            ms.append(v.mean())
    return tuple(np.percentile(ms, [100 * alpha / 2, 100 * (1 - alpha / 2)]))


def summarize(name, t, alpha=0.05):
    if t.empty:
        return {"rule": name, "n": 0}
    lo, hi = ci(t["pnl"], alpha=alpha)
    dlo, dhi = ci(t["pnl"], t["day"], alpha=alpha)
    return {"rule": name, "n": int(len(t)), "mean_c": 100 * t["pnl"].mean(),
            "ci_c": [100 * lo, 100 * hi], "day_ci_c": [100 * dlo, 100 * dhi],
            "win": float((t["pnl"] > 0).mean()), "avg_price": float(t["price"].mean())}


def fmt(s):
    if not s["n"]:
        return f"{s['rule']:<44} n=0"
    return (f"{s['rule']:<44} n={s['n']:>5}  mean {s['mean_c']:+6.2f}c  "
            f"CI [{s['ci_c'][0]:+.2f},{s['ci_c'][1]:+.2f}]  day-CI [{s['day_ci_c'][0]:+.2f},{s['day_ci_c'][1]:+.2f}]  "
            f"win {s['win']:.0%}  px {s['avg_price']:.2f}")


# ------------------------------------------------------------------ rule families

def rule_model(th, coin=None, min_minute=1, max_minute=14):
    def f(df):
        e_up = df["fair"] - df["ask"] - df["ask"].map(fee)
        no_px = 1 - df["bid"]
        e_dn = (1 - df["fair"]) - no_px - no_px.map(fee)
        ok = df["minute"].between(min_minute, max_minute) & df["ask"].between(0.02, 0.98)
        if coin:
            ok &= df["coin"] == coin
        out = pd.Series(None, index=df.index, dtype=object)
        out[ok & (e_up >= th) & (e_up >= e_dn)] = "yes"
        out[ok & (e_dn >= th) & (e_dn > e_up)] = "no"
        return out
    return f


def rule_band(lo, hi, side, minute):
    """Favorite/longshot: buy `side` when its ask is in [lo, hi) at `minute`."""
    def f(df):
        px = df["ask"] if side == "yes" else 1 - df["bid"]
        ok = (df["minute"] == minute) & (px >= lo) & (px < hi)
        return pd.Series(np.where(ok, side, None), index=df.index, dtype=object)
    return f


def rule_streak(pattern, side, minute=1):
    """After the previous windows went `pattern` (newest last, e.g. (1,1) = two UPs)."""
    def f(df):
        ok = df["minute"] == minute
        for i, v in enumerate(reversed(pattern), 1):
            ok &= df[f"prev{i}"] == v
        return pd.Series(np.where(ok, side, None), index=df.index, dtype=object)
    return f


def candidate_rules():
    R = {}
    for th in (0.02, 0.04, 0.06, 0.08, 0.10, 0.15):
        R[f"model edge>={th:.2f}"] = rule_model(th)
        R[f"model edge>={th:.2f} min<=10"] = rule_model(th, max_minute=10)
    for coin in COINS:
        R[f"model edge>=0.06 {coin}"] = rule_model(0.06, coin=coin)
    for minute in (5, 10, 13):
        for lo, hi in ((0.80, 0.90), (0.90, 0.95), (0.95, 0.99)):
            for side in ("yes", "no"):
                R[f"band {side} {lo:.2f}-{hi:.2f} @m{minute}"] = rule_band(lo, hi, side, minute)
    for pat in ((1,), (0,), (1, 1), (0, 0), (1, 1, 1), (0, 0, 0)):
        for side in ("yes", "no"):
            R[f"after {''.join('U' if x else 'D' for x in pat)} buy {side} @m1"] = rule_streak(pat, side)
    return R


# ------------------------------------------------------------------ commands

def info_value(tr):
    """Does the model add information beyond the market price? Logistic fit on TRAIN."""
    d = tr.dropna(subset=["fair"]).copy()
    eps = 1e-4
    lg = lambda p: np.log(np.clip(p, eps, 1 - eps) / (1 - np.clip(p, eps, 1 - eps)))
    d["mkt"] = (d["bid"] + d["ask"]) / 2
    X = np.c_[lg(d["mkt"]), lg(d["fair"])]
    m = LogisticRegression(C=1e6, max_iter=1000).fit(X, d["yes"])
    print(f"\nlogit(yes) ~ {m.intercept_[0]:+.3f} + {m.coef_[0][0]:.3f}*logit(market) + "
          f"{m.coef_[0][1]:.3f}*logit(model)   (n={len(d)} market-minutes)")
    print("  model coefficient near 0 => the volatility model adds nothing the price doesn't know.")


def train():
    df = pd.read_parquet(DATASET)
    tr = df[~df["test"]]
    print(f"TRAIN: {tr['ticker'].nunique()} markets, {len(tr)} market-minutes\n")
    info_value(tr)
    print()
    res = []
    for name, f in candidate_rules().items():
        s = summarize(name, trades(tr, f))
        res.append(s)
    res.sort(key=lambda s: -(s.get("ci_c", [-99])[0] if s["n"] else -99))
    for s in res:
        print(fmt(s))
    # Selection (fixed before looking): rules whose TRAIN trade-level CI lower bound > 0
    # and day-block CI lower bound > 0, with n >= 100. At most 5, best lower bound first.
    chosen = [s["rule"] for s in res
              if s["n"] >= 100 and s["ci_c"][0] > 0 and s["day_ci_c"][0] > 0][:5]
    os.makedirs(os.path.dirname(FROZEN), exist_ok=True)
    with open(FROZEN, "w", encoding="utf-8") as fh:
        json.dump({"frozen_at": datetime.now(timezone.utc).isoformat(), "test_frac": TEST_FRAC,
                   "chosen": chosen, "train_markets": int(tr["ticker"].nunique())}, fh, indent=2)
    print(f"\nfrozen {len(chosen)} rule(s) -> {FROZEN}: {chosen}")


def test(force=False):
    with open(FROZEN, encoding="utf-8") as fh:
        frozen = json.load(fh)
    if os.path.exists(RESULT) and not force:
        sys.exit("test already scored; it runs once. (--force only if the user says so)")
    df = pd.read_parquet(DATASET)
    te = df[df["test"]]
    R = candidate_rules()
    k = max(len(frozen["chosen"]), 1)
    out = [summarize(n, trades(te, R[n]), alpha=0.05 / k) for n in frozen["chosen"]]
    # GO needs: test mean > 0, trade-level CI lower bound > 0 after a Bonferroni-style
    # widening (alpha 0.05/k), and day-block CI lower bound > 0.
    for s in out:
        print(fmt(s))
    go = [s for s in out if s["n"] >= 50 and s["ci_c"][0] > 0 and s["day_ci_c"][0] > 0]
    verdict = "GO" if go else "NO-GO"
    summary = (f"{len(frozen['chosen'])} rule(s) frozen on {frozen['train_markets']} train markets; "
               f"scored once on {te['ticker'].nunique()} test markets. "
               + (f"Passing: {', '.join(s['rule'] for s in go)}." if go else "None held up after fees."))
    th = {}
    model_go = [s for s in go if s["rule"].startswith("model edge>=")]
    if model_go:
        v = float(model_go[0]["rule"].split(">=")[1].split()[0])
        th = {"signal": v, "strong": v + 0.04}
    with open(RESULT, "w", encoding="utf-8") as fh:
        json.dump({"verdict": verdict, "summary": summary, "thresholds": th,
                   "cols": ["Rule", "Trades", "Mean ¢", "95% CI ¢", "Day CI ¢", "Win"],
                   "rows": [[s["rule"], s["n"], f"{s['mean_c']:+.2f}",
                             f"[{s['ci_c'][0]:+.1f}, {s['ci_c'][1]:+.1f}]",
                             f"[{s['day_ci_c'][0]:+.1f}, {s['day_ci_c'][1]:+.1f}]",
                             f"{s['win']:.0%}"] for s in out if s["n"]],
                   "scored_at": datetime.now(timezone.utc).isoformat()}, fh, indent=2)
    print(f"\n{verdict}: {summary}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"build": build, "train": train, "test": lambda: test("--force" in sys.argv)}[cmd]()
