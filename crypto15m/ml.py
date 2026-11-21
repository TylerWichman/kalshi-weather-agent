"""Method 2: a gradient-boosted model of P(YES) from everything known at each minute,
plus the pre-registered cross-coin lag rule.

    py -3.12 -m crypto15m.ml validate   # fit on TRAIN, score on VALIDATION, maybe freeze
    py -3.12 -m crypto15m.ml test       # frozen config on TEST, once

The model counts as ONE hypothesis family in the ledger (5 trade thresholds, Bonferroni).
Features per (window, minute k): Kalshi price path (mid, spread, 1/2/3-min changes,
distance from window low/high), spot vs strike and its recent moves in volatility units,
the volatility model's fair price, hour/weekday, the coin's last 3 results, and the same
price/spot features for all three coins in that 15-min slot (cross-coin information).
"""

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import log_loss

from .common import DATA, ROOT
from .simulate import K, feats, load, simulate, stats, fmt

FROZEN = os.path.join(ROOT, "config", "crypto15m_ml_frozen.json")
RESULT = os.path.join(DATA, "ml_test.json")
THETAS = (0.02, 0.04, 0.06, 0.08, 0.10)
COINS3 = ("BTC", "ETH", "SOL")


def per_coin_block(D, F):
    """[W, K, f] features describing a window's own market at each minute."""
    mid, lps, vol = D["mid"], D["lps"], D["vol1"]
    sd = np.where(vol > 0, vol, np.nan)
    def lag(a, n):
        out = a - np.roll(a, n, axis=1)
        out[:, :n] = np.nan
        return out
    cols = {
        "mid": mid, "spread": D["ask"] - D["bid"],
        "dm1": F["d"][1], "dm2": F["d"][2], "dm3": F["d"][3],
        "off_lo": mid - F["lo"], "off_hi": F["hi"] - mid,
        "z": D["z"], "fair": D["fair"], "gap": D["fair"] - mid,
        "sz": lps / sd, "sr1": lag(lps, 1) / sd, "sr3": lag(lps, 3) / sd, "vol": vol,
    }
    return cols


def build(D):
    F = feats(D)
    mk = D["mk"]
    W = len(mk)
    own = per_coin_block(D, F)
    # previous results per coin (mk is sorted by coin, close)
    prev = {}
    for i in (1, 2, 3):
        prev[i] = mk.groupby("coin")["result"].shift(i).map({"yes": 1.0, "no": 0.0}).values
    # cross-coin: index of each coin's window with the same open time
    slot = {c: dict(zip(mk.loc[mk.coin == c, "open"], mk.index[mk.coin == c])) for c in COINS3}
    opens = mk["open"].values
    t = pd.to_datetime(opens, unit="s", utc=True).tz_convert("America/New_York")
    rows = []
    ks = np.arange(1, K - 1)  # decide at minutes 1..13
    base = {}
    for name, a in own.items():
        base[name] = a[:, ks].ravel()
    base["k"] = np.tile(ks, W).astype(float)
    base["hour"] = np.repeat(t.hour.values, len(ks)).astype(float)
    base["dow"] = np.repeat(t.dayofweek.values, len(ks)).astype(float)
    base["coin"] = np.repeat(mk["coin"].map({c: i for i, c in enumerate(COINS3)}).values, len(ks)).astype(float)
    for i in (1, 2, 3):
        base[f"prev{i}"] = np.repeat(prev[i], len(ks))
    for c in COINS3:
        j = np.array([slot[c].get(o, -1) for o in opens])
        have = j >= 0
        for name in ("mid", "dm1", "gap", "sz", "sr1", "sr3"):
            a = np.full((W, len(ks)), np.nan)
            a[have] = own[name][j[have]][:, ks]
            base[f"{c}_{name}"] = a.ravel()
    X = pd.DataFrame(base)
    y = np.repeat(D["yes"], len(ks))
    w = np.repeat(np.arange(W), len(ks))
    return X, y, w, ks


def slot_split(D):
    """Leakage-safe split. Every window in a 15-min slot (BTC, ETH, SOL) lands on the same
    side, and slots holding any test window are excluded, so the model never learns a
    label from the same slot it is scored on."""
    import hashlib
    mk = D["mk"]
    has_test = mk.groupby("open")["split"].transform(lambda s: (s == "test").any()).values
    h = mk["open"].map(lambda o: int(hashlib.sha256(f"slot{o}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF).values
    out = np.where(has_test, "excluded", np.where(h < 0.25, "validation", "train"))
    return out


def fit(D, splits):
    X, y, w, ks = build(D)
    tr = (splits == "train")[w]
    m = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=31,
                                       l2_regularization=1.0, min_samples_leaf=200,
                                       early_stopping=True, validation_fraction=0.15,
                                       random_state=7)
    # Early-stopping holdout is drawn from train rows only; the split is by row, so
    # minutes of one window can sit on both sides of it. That only affects when boosting
    # stops, never validation or test.
    m.fit(X[tr], y[tr])
    p = np.full(len(y), np.nan)
    p[:] = m.predict_proba(X)[:, 1]
    P = np.full((len(D["yes"]), K), np.nan)
    P[w, np.tile(ks, len(D["yes"]))] = p
    return m, P, X, y, w


def trade_arrays(D, P, theta):
    ey = (P - D["ask"] - 0.07 * D["ask"] * (1 - D["ask"])) >= theta
    nb = 1 - D["bid"]
    en = ((1 - P) - nb - 0.07 * nb * (1 - nb)) >= theta
    return np.nan_to_num(ey).astype(bool), np.nan_to_num(en).astype(bool)


def sub(D, P, split, splits):
    sel = splits == split
    S = {k: (v[sel] if isinstance(v, np.ndarray) else v[sel].reset_index(drop=True)) for k, v in D.items()}
    return S, P[sel]


def lag_rule(D, coin_px):
    """Pre-registered 2026-11-21 before any run: BTC leads the thin ETH/SOL markets.
    At minutes 1-12, if BTC spot moved >= 1.5 sd (1-min vol) over the last minute, buy
    YES on ETH and SOL that slot (NO if it fell), unless that market's mid already moved
    >= 5c the same way in that minute."""
    mk = D["mk"]
    bt = mk[mk.coin == "BTC"].set_index("open").index
    bidx = dict(zip(mk.loc[mk.coin == "BTC", "open"], np.where(mk.coin == "BTC")[0]))
    sr1 = np.full((len(mk), K), np.nan)
    lps, vol = D["lps"], D["vol1"]
    d = lps - np.roll(lps, 1, axis=1)
    d[:, 0] = np.nan
    bsr = d / vol
    for i, (c, o) in enumerate(zip(mk["coin"], mk["open"])):
        if c in ("ETH", "SOL") and o in bidx:
            sr1[i] = bsr[bidx[o]]
    F = feats(D)
    m = (F["k"] >= 1) & (F["k"] <= 12)
    ey = m & (sr1 >= 1.5) & ~(F["d"][1] >= 0.05)
    en = m & (sr1 <= -1.5) & ~(F["d"][1] <= -0.05)
    return np.nan_to_num(ey).astype(bool), np.nan_to_num(en).astype(bool)


def cmd_validate():
    D = load()
    splits = slot_split(D)
    print({k: int((splits == k).sum()) for k in ("train", "validation", "excluded")}, "windows")
    m, P, X, y, w = fit(D, splits)
    split = splits[w]
    for s in ("train", "validation"):
        sel = (split == s) & ~np.isnan(X["mid"].values)
        mid = np.clip(X["mid"].values[sel], 0.01, 0.99)
        pm = np.clip(P.ravel()[0:0].sum() + m.predict_proba(X[sel])[:, 1], 0.01, 0.99)
        print(f"{s:<11} log loss  market {log_loss(y[sel], mid):.4f}   model {log_loss(y[sel], pm):.4f}"
              f"   (lower is better; n={sel.sum()} market-minutes)")
    imp = pd.Series(dict(zip(X.columns, np.zeros(len(X.columns)))))
    V, PV = sub(D, P, "validation", splits)
    T, PT = sub(D, P, "train", splits)
    alpha = 0.05 / len(THETAS)
    print("\nTrading on the model, first trigger per window, hold to settlement:")
    keep = []
    for th in THETAS:
        st = stats(simulate(T, *trade_arrays(T, PT, th), ("hold", 0, 0)), T["mk"]["day"])
        sv = stats(simulate(V, *trade_arrays(V, PV, th), ("hold", 0, 0)), V["mk"]["day"], alpha=alpha)
        print("  train " + fmt(f"model edge>={th:.2f}", st))
        print("  valid " + fmt(f"model edge>={th:.2f}", sv))
        if sv["n"] >= 100 and sv["ci_c"][0] > 0 and sv["day_ci_c"][0] > 0:
            keep.append(th)

    print("\nCross-coin lag rule (pre-registered):")
    lag_ok = False
    for s, S in (("train", T), ("valid", V)):
        ey, en = lag_rule(S, None)
        for ex in (("hold", 0, 0), ("time", 1, 0)):
            r = stats(simulate(S, ey, en, ex), S["mk"]["day"], alpha=0.05 if s == "train" else 0.025)
            print(f"  {s} " + fmt(f"BTC leads ETH/SOL, exit {ex[0]}", r))
            if s == "valid" and r["n"] >= 100 and r["ci_c"][0] > 0 and r["day_ci_c"][0] > 0:
                lag_ok = ex[0]

    with open(FROZEN, "w", encoding="utf-8") as fh:
        json.dump({"frozen_at": datetime.now(timezone.utc).isoformat(),
                   "model_theta": keep[0] if keep else None, "lag_exit": lag_ok}, fh, indent=2)
    print(f"\nfrozen: model theta {keep[0] if keep else None}, lag rule {lag_ok or None}")


if __name__ == "__main__":
    {"validate": cmd_validate}[sys.argv[1] if len(sys.argv) > 1 else "validate"]()
