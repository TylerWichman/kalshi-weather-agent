"""Trading simulator for the 15-min crypto markets: entries, exits, and a luck benchmark.

    py -3.12 -m crypto15m.simulate search        # TRAIN: all rules + permutation null
    py -3.12 -m crypto15m.simulate validate      # VALIDATION: finalists -> freeze
    py -3.12 -m crypto15m.simulate test          # TEST: frozen rules, once

Splits (by sha256 of the ticker, so they're random per window and fixed forever):
  test        h < 0.30   (same test set as backtest.py, still unscored)
  validation  0.30 <= h < 0.45
  train       h >= 0.45
Validation windows were inside the earlier backtest.py train set; only aggregate results
of hold-to-settlement rules were seen there. The forward live record stays the final judge.

Execution model, per contract: buy at the minute-close ask, sell at the minute-close bid
(both taker), Kalshi fee 0.07*P*(1-P) on each leg (unrounded: assumes orders of ~100
contracts, where per-order rounding is negligible), settlement pays $1 or 0 with no fee.
One position per window per rule: the first trigger.

Luck benchmark: the whole rule search is re-run with each window's signals applied to a
different, randomly chosen window's prices and outcome. Signals then carry no information,
so the best rule in each shuffled run shows how good "best of N" looks by chance.
"""

import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .common import DATA, ROOT
from .store import connect

FROZEN = os.path.join(ROOT, "config", "crypto15m_sim_frozen.json")
RESULT = os.path.join(DATA, "simulate_test.json")
K = 15  # minute slots 0..14; slot k = state at open + 60k (slot 0 unused)
MIN_TRADES = 200


def split_of(ticker):
    h = int(hashlib.sha256(ticker.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "test" if h < 0.30 else "validation" if h < 0.45 else "train"


# ------------------------------------------------------------------ data

def load():
    con = connect()
    mk = pd.read_sql("SELECT * FROM markets WHERE result IN ('yes','no') AND strike IS NOT NULL", con)
    km = pd.read_sql("SELECT ticker, ts, bid, ask FROM kminutes", con)
    sp = pd.read_sql("SELECT coin, ts, open, close FROM spot_minutes", con)
    mk = mk.sort_values(["coin", "close"]).reset_index(drop=True)
    W = len(mk)
    idx = {t: i for i, t in enumerate(mk["ticker"])}
    bid = np.full((W, K), np.nan)
    ask = np.full((W, K), np.nan)
    km["w"] = km["ticker"].map(idx)
    km = km.dropna(subset=["w"])
    km["k"] = (km["ts"] - mk["open"].values[km["w"].astype(int)]) // 60
    km = km[(km["k"] >= 1) & (km["k"] < K)]
    w, k = km["w"].astype(int).values, km["k"].astype(int).values
    bid[w, k], ask[w, k] = km["bid"].values, km["ask"].values
    bad = (bid <= 0) | (ask >= 1) | (ask <= bid - 1e-9)
    bid[bad], ask[bad] = np.nan, np.nan

    # Spot features: z-distance to strike and the model fair price, per minute slot.
    z = np.full((W, K), np.nan)
    lps = np.full((W, K), np.nan)   # log(spot / strike), basis-adjusted
    vol1 = np.full((W, K), np.nan)  # 1-minute log-return stdev over the prior hour
    for coin, g in sp.groupby("coin"):
        s = g.set_index("ts").sort_index()
        lr = np.log(s["close"]).diff()
        vol = lr.rolling(60, min_periods=30).std()
        rows = np.where(mk["coin"].values == coin)[0]
        o = mk["open"].values[rows]
        pre = s.reindex(o - 60)
        basis = mk["strike"].values[rows] / ((pre["open"].values + pre["close"].values) / 2)
        for kk in range(1, K):
            t = o + 60 * kk - 60  # candle starting here closes at open + 60k
            px = s["close"].reindex(t).values * basis
            v = vol.reindex(t).values / math.sqrt(60)
            left = 900 - 60 * kk
            sd = v * np.sqrt(max(left - 40, 1))
            z[rows, kk] = np.log(px / mk["strike"].values[rows]) / sd
            lps[rows, kk] = np.log(px / mk["strike"].values[rows])
            vol1[rows, kk] = v * math.sqrt(60)
        # slot 0 = the open itself: spot at the open vs strike (basis-adjusted)
        lps[rows, 0] = np.log(s["close"].reindex(o - 60).values * basis / mk["strike"].values[rows])
    from scipy.special import ndtr  # noqa: E402  (scipy ships with sklearn)
    fair = ndtr(z)
    mk["split"] = mk["ticker"].map(split_of)
    mk["day"] = pd.to_datetime(mk["open"], unit="s", utc=True).dt.tz_convert("America/New_York").dt.date.astype(str)
    return {"mk": mk, "bid": bid, "ask": ask, "mid": (bid + ask) / 2, "z": z, "fair": fair,
            "lps": lps, "vol1": vol1,
            "yes": (mk["result"] == "yes").values.astype(float)}


def subset(D, split):
    sel = (D["mk"]["split"] == split).values
    return {k: (v[sel] if isinstance(v, np.ndarray) else v[sel].reset_index(drop=True))
            for k, v in D.items()}


# ------------------------------------------------------------------ engine

def fee(p):
    return 0.07 * p * (1 - p)


def simulate(D, ey, en, exit_rule, perm=None):
    """ey/en: bool [W,K] entry signals for YES / NO. Returns pnl per window (nan = no trade).

    perm: optional permutation; window w's signals trade window perm[w]'s prices/outcome.
    """
    W = ey.shape[0]
    bid, ask, yes = D["bid"], D["ask"], D["yes"]
    if perm is not None:
        bid, ask, yes = bid[perm], ask[perm], yes[perm]
    buy_y, buy_n = ask, 1 - bid          # what each side costs
    sell_y, sell_n = bid, 1 - ask        # what each side fetches
    ok_y = ey & (buy_y > 0.01) & (buy_y < 0.99)
    ok_n = en & (buy_n > 0.01) & (buy_n < 0.99)
    trig = ok_y | ok_n
    has = trig.any(1)
    k0 = np.where(has, trig.argmax(1), 0)
    r = np.arange(W)
    side_yes = ok_y[r, k0]
    entry = np.where(side_yes, buy_y[r, k0], buy_n[r, k0])
    cost = entry + fee(entry)
    sell = np.where(side_yes[:, None], sell_y, sell_n)
    win = np.where(side_yes, yes == 1, yes == 0).astype(float)
    pnl = win - cost                     # default: hold to settlement
    done = ~has
    kind, a, b = exit_rule
    if kind != "hold":
        for j in range(1, K):
            live = (~done) & (j > k0)
            px = sell[:, j]
            valid = live & ~np.isnan(px)
            if kind == "time":
                hit = valid & (j == k0 + a)
            else:
                hit = np.zeros(W, bool)
                if a:
                    hit |= valid & (px - entry >= a)
                if b:
                    hit |= valid & (entry - px >= b)
            pnl = np.where(hit, px - fee(px) - cost, pnl)
            done |= hit
    return np.where(has, pnl, np.nan)


# ------------------------------------------------------------------ rules

MINUTES = {"m1-4": (1, 4), "m5-9": (5, 9), "m10-13": (10, 13), "m2-12": (2, 12)}
EXITS = {"hold": ("hold", 0, 0), "tp5": ("tp", 0.05, 0), "tp10": ("tp", 0.10, 0),
         "tp20": ("tp", 0.20, 0), "sl10": ("tp", 0, 0.10), "tp10sl10": ("tp", 0.10, 0.10),
         "t1": ("time", 1, 0), "t3": ("time", 3, 0)}


def feats(D):
    mid = D["mid"]
    d = {n: mid - np.roll(mid, n, axis=1) for n in (1, 2, 3)}
    for n in d:
        d[n][:, :n + 1] = np.nan
    lo = np.fmin.accumulate(np.where(np.isnan(mid), np.inf, mid), axis=1)
    hi = np.fmax.accumulate(np.where(np.isnan(mid), -np.inf, mid), axis=1)
    # minute the running low/high was set
    W = mid.shape[0]
    lo_at = np.zeros_like(mid)
    hi_at = np.zeros_like(mid)
    for k in range(1, K):
        new_lo = mid[:, k] <= lo[:, k - 1] if k > 1 else np.ones(W, bool)
        new_hi = mid[:, k] >= hi[:, k - 1] if k > 1 else np.ones(W, bool)
        lo_at[:, k] = np.where(new_lo, k, lo_at[:, k - 1])
        hi_at[:, k] = np.where(new_hi, k, hi_at[:, k - 1])
    kk = np.broadcast_to(np.arange(K), mid.shape)
    return {"d": d, "lo": lo, "hi": hi, "lo_at": lo_at, "hi_at": hi_at, "k": kk}


def window(F, name):
    a, b = MINUTES[name]
    return (F["k"] >= a) & (F["k"] <= b)


def user_rules():
    """Pre-registered 2026-11-21 from the user's description, before any run of it:
    'strong rallies on peaks and valleys, it shoots up at the start of a rally'."""
    def valley(D, F):
        m = window(F, "m2-12")
        ey = m & (D["mid"] - F["lo"] >= 0.10) & (F["lo_at"] <= F["k"] - 1)
        en = m & (F["hi"] - D["mid"] >= 0.10) & (F["hi_at"] <= F["k"] - 1)
        return ey, en
    return {f"USER valley/peak rally 10c, exit {x}": (valley, EXITS[x]) for x in ("t3", "hold")}


def search_rules():
    R = {}
    for n in (1, 2, 3):
        for x in (0.05, 0.10, 0.15, 0.20):
            for wn in ("m1-4", "m5-9", "m10-13"):
                def mom(D, F, n=n, x=x, wn=wn):
                    m = window(F, wn)
                    return m & (F["d"][n] >= x), m & (F["d"][n] <= -x)

                def rev(D, F, n=n, x=x, wn=wn):
                    m = window(F, wn)
                    return m & (F["d"][n] <= -x), m & (F["d"][n] >= x)
                R[f"momentum d{n}>={x:.2f} {wn}"] = mom
                R[f"fade d{n}>={x:.2f} {wn}"] = rev
    for lo, hi in ((0.05, 0.15), (0.15, 0.35), (0.35, 0.65), (0.65, 0.85), (0.85, 0.95)):
        for wn in ("m1-4", "m5-9", "m10-13"):
            def band_y(D, F, lo=lo, hi=hi, wn=wn):
                m = window(F, wn)
                return m & (D["ask"] >= lo) & (D["ask"] < hi), np.zeros_like(m)

            def band_n(D, F, lo=lo, hi=hi, wn=wn):
                m = window(F, wn)
                p = 1 - D["bid"]
                return np.zeros_like(m), m & (p >= lo) & (p < hi)
            R[f"buy YES at {lo:.2f}-{hi:.2f} {wn}"] = band_y
            R[f"buy NO at {lo:.2f}-{hi:.2f} {wn}"] = band_n
    for x in (0.05, 0.10, 0.15, 0.20):
        for wn in ("m1-4", "m5-9", "m10-13"):
            def model(D, F, x=x, wn=wn):
                m = window(F, wn)
                return m & (D["fair"] - D["ask"] >= x), m & ((1 - D["fair"]) - (1 - D["bid"]) >= x)
            R[f"model gap>={x:.2f} {wn}"] = model
    for x in (0.05, 0.10, 0.15):
        for y in (0.03, 0.05):
            for wn in ("m1-4", "m5-9", "m10-13"):
                def vp(D, F, x=x, y=y, wn=wn):
                    m = window(F, wn)
                    ey = m & (D["mid"] - F["lo"] >= x) & (F["d"][1] >= y) & (F["lo_at"] <= F["k"] - 1)
                    en = m & (F["hi"] - D["mid"] >= x) & (F["d"][1] <= -y) & (F["hi_at"] <= F["k"] - 1)
                    return ey, en
                R[f"valley/peak bounce>={x:.2f} last1m>={y:.2f} {wn}"] = vp
    out = {}
    for name, f in R.items():
        for ex, rule in EXITS.items():
            out[f"{name}, exit {ex}"] = (f, rule)
    return out


# ------------------------------------------------------------------ stats

def stats(pnl, days, alpha=0.05, B=1000, seed=11):
    ok = ~np.isnan(pnl)
    v, dd = pnl[ok], days[ok]
    n = len(v)
    if n < 5:
        return {"n": int(n)}
    rng = np.random.default_rng(seed)
    bs = [v[rng.integers(0, n, n)].mean() for _ in range(B)]
    by = pd.Series(v).groupby(dd.values if hasattr(dd, "values") else dd)
    sums, cnts = by.sum().values, by.count().values
    bd = []
    for _ in range(B):
        i = rng.integers(0, len(sums), len(sums))
        bd.append(sums[i].sum() / cnts[i].sum())
    q = [100 * alpha / 2, 100 * (1 - alpha / 2)]
    return {"n": int(n), "mean_c": 100 * v.mean(), "ci_c": list(100 * np.percentile(bs, q)),
            "day_ci_c": list(100 * np.percentile(bd, q)), "win": float((v > 0).mean())}


def fmt(name, s):
    if s["n"] < 5:
        return f"{name:<62} n={s['n']}"
    return (f"{name:<62} n={s['n']:>5} mean {s['mean_c']:+6.2f}c "
            f"CI [{s['ci_c'][0]:+.2f},{s['ci_c'][1]:+.2f}] day [{s['day_ci_c'][0]:+.2f},{s['day_ci_c'][1]:+.2f}] "
            f"win {s['win']:.0%}")


def run_all(D, rules, perm=None):
    F = feats(D)
    out = {}
    for name, (f, ex) in rules.items():
        ey, en = f(D, F)
        ey = np.nan_to_num(ey, nan=0).astype(bool)
        en = np.nan_to_num(en, nan=0).astype(bool)
        out[name] = simulate(D, ey, en, ex, perm)
    return out


# ------------------------------------------------------------------ commands

def cmd_search(nulls=20):
    D = load()
    T = subset(D, "train")
    W = len(T["yes"])
    print(f"TRAIN {W} windows; validation {int((D['mk']['split'] == 'validation').sum())}; "
          f"test {int((D['mk']['split'] == 'test').sum())} (untouched)\n")

    print("== Your pre-registered rules (train) ==")
    for name, p in run_all(T, user_rules()).items():
        print(fmt(name, stats(p, T["mk"]["day"])))

    rules = search_rules()
    res = run_all(T, rules)
    means = {n: np.nanmean(p) for n, p in res.items() if np.sum(~np.isnan(p)) >= MIN_TRADES}
    print(f"\n== Broad search: {len(rules)} rules, {len(means)} with >= {MIN_TRADES} trades ==")

    rng = np.random.default_rng(2026)
    null_best = []
    for i in range(nulls):
        perm = rng.permutation(W)
        pr = run_all(T, rules, perm)
        m = [np.nanmean(p) for p in pr.values() if np.sum(~np.isnan(p)) >= MIN_TRADES]
        null_best.append(100 * max(m))
    bar = float(np.percentile(null_best, 95))
    print(f"luck benchmark: best rule on shuffled data, {nulls} runs: "
          f"median {np.median(null_best):+.2f}c, 95th pct {bar:+.2f}c\n")

    top = sorted(means.items(), key=lambda kv: -kv[1])[:25]
    for name, m in top:
        flag = "  <- beats luck" if 100 * m > bar else ""
        print(fmt(name, stats(res[name], T["mk"]["day"])) + flag)
    finalists = [n for n, m in top if 100 * m > bar][:10]
    finalists = list(user_rules()) + finalists
    os.makedirs(os.path.dirname(FROZEN), exist_ok=True)
    with open(FROZEN + ".finalists", "w", encoding="utf-8") as fh:
        json.dump({"at": datetime.now(timezone.utc).isoformat(), "luck_95_c": bar,
                   "finalists": finalists}, fh, indent=2)
    print(f"\n{len(finalists)} finalist(s) for validation (your 2 rules always go through).")


def all_rules():
    r = dict(search_rules())
    r.update(user_rules())
    return r


def cmd_validate():
    with open(FROZEN + ".finalists", encoding="utf-8") as fh:
        fin = json.load(fh)["finalists"]
    D = load()
    V = subset(D, "validation")
    R = all_rules()
    res = run_all(V, {n: R[n] for n in fin})
    alpha = 0.05 / max(len(fin), 1)
    keep = []
    print(f"VALIDATION {len(V['yes'])} windows; CIs widened for {len(fin)} finalists\n")
    for n in fin:
        s = stats(res[n], V["mk"]["day"], alpha=alpha)
        print(fmt(n, s))
        if s["n"] >= 100 and s["ci_c"][0] > 0 and s["day_ci_c"][0] > 0:
            keep.append(n)
    keep = keep[:3]
    with open(FROZEN, "w", encoding="utf-8") as fh:
        json.dump({"frozen_at": datetime.now(timezone.utc).isoformat(), "chosen": keep}, fh, indent=2)
    print(f"\nfrozen {len(keep)} rule(s) for the one-time test: {keep}")


def cmd_test(force=False):
    with open(FROZEN, encoding="utf-8") as fh:
        chosen = json.load(fh)["chosen"]
    if not chosen:
        sys.exit("nothing frozen; the test set stays unused.")
    if os.path.exists(RESULT) and not force:
        sys.exit("test already scored; it runs once.")
    D = load()
    Te = subset(D, "test")
    R = all_rules()
    res = run_all(Te, {n: R[n] for n in chosen})
    alpha = 0.05 / len(chosen)
    out = []
    for n in chosen:
        s = stats(res[n], Te["mk"]["day"], alpha=alpha)
        print(fmt(n, s))
        out.append({"rule": n, **s, "go": bool(s["n"] >= 100 and s["ci_c"][0] > 0 and s["day_ci_c"][0] > 0)})
    with open(RESULT, "w", encoding="utf-8") as fh:
        json.dump({"scored_at": datetime.now(timezone.utc).isoformat(), "results": out}, fh, indent=2)


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "search"
    {"search": cmd_search, "validate": cmd_validate,
     "test": lambda: cmd_test("--force" in sys.argv)}[c]()
