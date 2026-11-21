"""Passive two-sided quoting on ETH/SOL 15-min windows, simulated on the public trade tape.

Spec: docs/crypto15m-maker-preregistration.md (fixed 2026-11-21 before any run).

    py -3.12 -m crypto15m.maker validate   # train report + validation decision, freeze
    py -3.12 -m crypto15m.maker test       # frozen variants on test, once
"""

import gzip
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .common import DATA, ROOT
from .store import connect

FROZEN = os.path.join(ROOT, "config", "crypto15m_maker_frozen.json")
RESULT = os.path.join(DATA, "maker_test.json")
VARIANTS = [(stop, mode) for stop in (8, 12) for mode in ("improve", "join")]
STEP, LOOKBACK, SIZE, CAP = 10.0, 30.0, 10.0, 50.0
MAKER_FEE = 0.0175


def split_of(ticker):
    h = int(hashlib.sha256(ticker.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "test" if h < 0.30 else "validation" if h < 0.45 else "train"


def load():
    con = connect()
    rows = con.execute("""SELECT t.ticker, t.coin, m.open, m.close, m.result, t.data
                          FROM trade_blobs t JOIN markets m USING (ticker)
                          WHERE m.result IN ('yes','no')""").fetchall()
    out = []
    for tk, coin, o, c, res, blob in rows:
        tr = np.array(json.loads(gzip.decompress(blob)), dtype=float)
        if len(tr) == 0:
            continue
        out.append({"ticker": tk, "coin": coin, "open": o, "close": c,
                    "yes": 1.0 if res == "yes" else 0.0, "tr": tr, "split": split_of(tk),
                    "day": pd.Timestamp(o, unit="s", tz="UTC").tz_convert("America/New_York").date().isoformat()})
    return out


def run_window(w, stop_min, mode, fee_k=MAKER_FEE):
    """Returns (pnl dollars, contracts filled, quoted?)."""
    tr = w["tr"]
    ts, px, cnt, ty = tr[:, 0], tr[:, 1], tr[:, 2], tr[:, 3]
    hit_bid = ty == 0   # taker bought NO: traded at the YES bid
    lift = ty == 1      # taker bought YES: traded at the YES ask
    pos, cash, filled, quoted = 0.0, 0.0, 0.0, False
    t = w["open"] + 60.0
    end = w["open"] + 60.0 * stop_min
    while t < end:
        lo = np.searchsorted(ts, t - LOOKBACK, "right")
        hi = np.searchsorted(ts, t, "right")
        hb = np.where(hit_bid[lo:hi])[0]
        la = np.where(lift[lo:hi])[0]
        if len(hb) and len(la):
            bid, ask = px[lo + hb[-1]], px[lo + la[-1]]
            if bid >= 0.10 and ask <= 0.90 and ask > bid:
                if mode == "improve":
                    qb, qa = bid + 0.01, ask - 0.01
                    if qb >= qa:
                        qb, qa = bid, ask
                else:
                    qb, qa = bid, ask
                quoted = True
                j0 = hi
                j1 = np.searchsorted(ts, t + STEP, "right")
                rb = SIZE if pos < CAP else 0.0
                ra = SIZE if pos > -CAP else 0.0
                for j in range(j0, j1):
                    if rb > 0 and hit_bid[j] and px[j] < qb - 1e-9:
                        q = min(rb, cnt[j], CAP - pos)
                        if q > 0:
                            pos += q; rb -= q; filled += q
                            cash -= q * qb + q * fee_k * qb * (1 - qb)
                    elif ra > 0 and lift[j] and px[j] > qa + 1e-9:
                        q = min(ra, cnt[j], CAP + pos)
                        if q > 0:
                            pos -= q; ra -= q; filled += q
                            cash += q * qa - q * fee_k * qa * (1 - qa)
        t += STEP
    pnl = cash + pos * w["yes"]
    return pnl, filled, quoted


def evaluate(ws, stop, mode, fee_k=MAKER_FEE):
    r = [run_window(w, stop, mode, fee_k) for w in ws]
    df = pd.DataFrame({"pnl": [x[0] for x in r], "filled": [x[1] for x in r],
                       "quoted": [x[2] for x in r], "day": [w["day"] for w in ws],
                       "coin": [w["coin"] for w in ws]})
    return df[df["quoted"]]


def ci(v, groups=None, alpha=0.05, B=2000, seed=5):
    rng = np.random.default_rng(seed)
    v = np.asarray(v, float)
    if len(v) < 10:
        return float("nan"), float("nan")
    q = [100 * alpha / 2, 100 * (1 - alpha / 2)]
    if groups is None:
        bs = [v[rng.integers(0, len(v), len(v))].mean() for _ in range(B)]
    else:
        g = pd.Series(v).groupby(np.asarray(groups))
        s, n = g.sum().values, g.count().values
        bs = []
        for _ in range(B):
            i = rng.integers(0, len(s), len(s))
            bs.append(s[i].sum() / n[i].sum())
    return tuple(np.percentile(bs, q))


def report(name, df, alpha=0.05):
    if df.empty:
        return {"name": name, "n": 0}, f"{name:<34} no windows quoted"
    lo, hi = ci(df["pnl"], alpha=alpha)
    dlo, dhi = ci(df["pnl"], df["day"], alpha=alpha)
    s = {"name": name, "n": int(len(df)), "mean_c": 100 * df["pnl"].mean(),
         "ci_c": [100 * lo, 100 * hi], "day_ci_c": [100 * dlo, 100 * dhi],
         "fills_per_window": float(df["filled"].mean()),
         "c_per_contract": float(100 * df["pnl"].sum() / max(df["filled"].sum(), 1))}
    line = (f"{name:<34} windows {s['n']:>5}  {s['mean_c']:+7.2f}c/window  "
            f"CI [{lo*100:+.1f},{hi*100:+.1f}] day [{dlo*100:+.1f},{dhi*100:+.1f}]  "
            f"fills {s['fills_per_window']:.0f}/window  {s['c_per_contract']:+.2f}c/contract")
    return s, line


def cmd_validate():
    ws = load()
    by = {k: [w for w in ws if w["split"] == k] for k in ("train", "validation", "test")}
    print({k: len(v) for k, v in by.items()}, "windows with trades (test not simulated)\n")
    alpha = 0.05 / len(VARIANTS)
    keep = []
    for stop, mode in VARIANTS:
        name = f"stop m{stop}, {mode}"
        _, lt = report(name, evaluate(by["train"], stop, mode))
        sv, lv = report(name, evaluate(by["validation"], stop, mode), alpha=alpha)
        _, l0 = report(name + " (0 fee, context)", evaluate(by["train"], stop, mode, 0.0))
        print("train " + lt)
        print("      " + l0)
        print("valid " + lv)
        if sv["n"] >= 300 and sv["ci_c"][0] > 0 and sv["day_ci_c"][0] > 0:
            keep.append([stop, mode])
    with open(FROZEN, "w", encoding="utf-8") as fh:
        json.dump({"frozen_at": datetime.now(timezone.utc).isoformat(), "chosen": keep[:2]}, fh, indent=2)
    print(f"\nfrozen for test: {keep[:2]}")


def cmd_test(force=False):
    chosen = json.load(open(FROZEN, encoding="utf-8"))["chosen"]
    if not chosen:
        sys.exit("nothing frozen; the test set stays unused.")
    if os.path.exists(RESULT) and not force:
        sys.exit("test already scored; it runs once.")
    te = [w for w in load() if w["split"] == "test"]
    out = []
    for stop, mode in chosen:
        s, line = report(f"stop m{stop}, {mode}", evaluate(te, stop, mode), alpha=0.05 / len(chosen))
        print(line)
        out.append({**s, "go": bool(s["n"] >= 300 and s["ci_c"][0] > 0 and s["day_ci_c"][0] > 0)})
    with open(RESULT, "w", encoding="utf-8") as fh:
        json.dump({"scored_at": datetime.now(timezone.utc).isoformat(), "results": out}, fh, indent=2)


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "validate"
    {"validate": cmd_validate, "test": lambda: cmd_test("--force" in sys.argv)}[c]()
