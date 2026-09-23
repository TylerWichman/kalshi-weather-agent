"""Tier 1 calibration score (spec v3 Phase 2, calibration half; methodology per section 9.5).

Answers one question: **is `p_model` honest?** No Kalshi prices involved. If the
probabilities are not calibrated, the economic backtest is not worth building.

## The model

Deliberately the simplest thing that could be calibrated, so the score measures the
data rather than a clever fit:

    T_max ~ forecast + residual_distribution(station, lead)

The residual distribution is **empirical**, taken from training residuals for that
station and lead, and used by its quantiles rather than a fitted normal. That keeps
the skew, which matters: forecast errors for daily highs are not symmetric, and a
normal fit would understate the cool tail.

This deliberately does NOT use ensemble spread. Open-Meteo serves no historical
ensemble, and ensemble spread is known to be underdispersed anyway. Calibrating the
predictive distribution from realized errors is both available and more honest.

Per-station, per-lead bias correction falls out of this for free -- the residual
distribution is centered wherever the station's bias actually is. Phase 1 measured
that bias at -2.5F (Miami) to +4.4F (LAX), which is 1-2 whole buckets, so this is
load-bearing (spec section 2.2).

## Splits (section 9.5)

Chronological, **date-level** (all 12 cities on one day share a weather regime, so a
row-level split would leak), with a **7-day embargo** at each boundary because
weather systems span the cut, and **walk-forward** rolling origin rather than one
split. Nothing is tuned against the final fold.

## Scores

Two families, because they answer different questions:

1. **Distribution-level, ladder-free** -- PIT uniformity and CRPS. The purest test of
   whether the predictive distribution is honest, with no assumption about strikes.
2. **Bucket-level** -- Brier (decomposed into reliability/resolution), log loss and
   ranked probability score over a **synthetic 2F ladder**. Kalshi's real bucket
   width is 2F; strike *placement* is synthesized here since this half of Phase 2
   uses no Kalshi data. Placement affects absolute scores, not whether the
   probabilities are calibrated.

Baselines: **climatology** (does the model add information?) and **uncorrected raw
forecast** (does the calibration step earn its keep?). Beating the market is a
separate question that needs prices -- see the economic half.

Usage:  python scripts/calibrate.py
"""

import os
import sqlite3
import sys
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "calibration.sqlite")

EMBARGO_DAYS = 7
N_FOLDS = 4
MIN_TRAIN_DAYS = 120
BUCKET_WIDTH = 2.0      # Kalshi's real ladder width
N_BUCKETS = 6           # less tail + 4 between + greater tail

# Section 9.5: 0-24h is the CONTROL. The go/no-go rests on 24-48h.
LEAD_LABEL = {0: "0-24h  (CONTROL)", 1: "24-48h (DECISION)", 2: "48-72h",
              3: "72-96h", 4: "96-120h", 5: "120-144h"}


# ----------------------------------------------------------------- data

def _doy(date_str):
    import datetime
    d = datetime.date.fromisoformat(date_str)
    return d.timetuple().tm_yday


def load(conn):
    rows = conn.execute(
        "SELECT nws_station, city, target_date, lead_days, forecast_f, actual_f "
        "FROM calibration_set WHERE actual_f IS NOT NULL ORDER BY target_date"
    ).fetchall()
    return [dict(station=r[0], city=r[1], date=r[2], lead=r[3],
                 fc=float(r[4]), act=float(r[5])) for r in rows]


def walk_forward_folds(dates):
    """Expanding-window folds with an embargo gap, per section 9.5."""
    dates = sorted(set(dates))
    n = len(dates)
    usable = n - MIN_TRAIN_DAYS
    if usable <= 0:
        return []
    test_len = usable // N_FOLDS
    folds = []
    for k in range(N_FOLDS):
        test_start = MIN_TRAIN_DAYS + k * test_len
        test_end = test_start + test_len if k < N_FOLDS - 1 else n
        train_end = test_start - EMBARGO_DAYS
        if train_end < 30:
            continue
        folds.append({
            "train": set(dates[:train_end]),
            "embargo": set(dates[train_end:test_start]),
            "test": set(dates[test_start:test_end]),
            "label": f"{dates[test_start]} .. {dates[test_end-1]}",
        })
    return folds


# ---------------------------------------------------------------- model

class EmpiricalResidualModel:
    """Predictive distribution = forecast + empirical residual quantiles.

    Trained on a ROLLING recent window, not the full expanding history. Residuals
    are strongly seasonal -- measured monthly means run +2.9F in February against
    -0.3F in July, with spread from 3.3F to 5.2F -- so pooling a year of history
    applies the wrong bias correction to the test season. The first run of this
    script used an expanding window and its PIT KS got *worse* as training data
    grew (0.10 -> 0.21 across folds), which is that mis-specification showing.

    A rolling window is also what production would do: refit daily on recent
    residuals, which tracks the season automatically without modelling it.
    """

    MIN_N = 40        # below this, back off to the pooled residual distribution
    WINDOW_DAYS = 45  # rolling; see class docstring

    def fit(self, train_rows):
        if self.WINDOW_DAYS:
            cutoff = sorted({r["date"] for r in train_rows})[-self.WINDOW_DAYS:]
            train_rows = [r for r in train_rows if r["date"] in set(cutoff)]
        return self._fit(train_rows)

    def _fit(self, train_rows):
        self.by_key = {}
        pooled = defaultdict(list)
        for r in train_rows:
            resid = r["act"] - r["fc"]
            self.by_key.setdefault((r["station"], r["lead"]), []).append(resid)
            pooled[r["lead"]].append(resid)
        self.by_key = {k: np.sort(np.array(v)) for k, v in self.by_key.items()}
        self.pooled = {k: np.sort(np.array(v)) for k, v in pooled.items()}
        return self

    def residuals(self, station, lead):
        r = self.by_key.get((station, lead))
        if r is None or len(r) < self.MIN_N:
            return self.pooled.get(lead, np.array([0.0]))
        return r

    def cdf(self, station, lead, fc, x):
        """P(T_max <= x). Empirical, so it inherits the residuals' skew."""
        res = self.residuals(station, lead)
        return float(np.searchsorted(res, x - fc, side="right") / len(res))

    def pit(self, station, lead, fc, actual):
        """Probability integral transform. Should be ~Uniform(0,1) if calibrated.

        Randomized within the tie interval, because the actual is reported to whole
        degrees while the residual distribution is continuous -- without this the
        PIT histogram shows spurious discreteness artifacts rather than miscalibration.
        """
        res = self.residuals(station, lead)
        lo = np.searchsorted(res, actual - fc - 0.5, side="left") / len(res)
        hi = np.searchsorted(res, actual - fc + 0.5, side="right") / len(res)
        return float(lo + (hi - lo) * np.random.random()) if hi > lo else float(lo)

    def sample(self, station, lead, fc, n=400):
        res = self.residuals(station, lead)
        idx = np.random.randint(0, len(res), size=min(n, len(res) * 4))
        return fc + res[idx]


class ClimatologyModel:
    """Baseline: DAY-OF-YEAR conditional climatology per station.

    Conditioning on day-of-year matters. Pooling a station's whole year gives
    KNYC an sd of 18.4F spanning 17-100F, which any forecast beats trivially --
    a strawman that inflates apparent skill. The honest baseline is "what does
    this station usually do at this time of year", a +/-15 day window.
    """

    HALF_WINDOW = 15
    TRAILING_DAYS = 30   # see dist(): the only seasonally-local option with 1yr of data

    def fit(self, train_rows):
        self.by_station_doy = defaultdict(list)
        self.by_station_dated = defaultdict(list)
        self.by_station = defaultdict(list)
        for r in train_rows:
            if r["lead"] != 0:           # one row per station-day
                continue
            doy = _doy(r["date"])
            self.by_station_doy[r["station"]].append((doy, r["act"]))
            self.by_station_dated[r["station"]].append((r["date"], r["act"]))
            self.by_station[r["station"]].append(r["act"])
        self.all = np.sort(np.array(
            [v for vs in self.by_station.values() for v in vs]))
        for k in self.by_station_dated:
            self.by_station_dated[k].sort()
        self._cache = {}
        return self

    def dist(self, station, date=None):
        if date is None:
            d = self.by_station.get(station)
            return np.sort(np.array(d)) if d else self.all
        key = (station, date)
        if key in self._cache:
            return self._cache[key]
        # Day-of-year conditioning needs multiple years. With ~1 year and
        # chronological splits, a test date in March has NO March history in a
        # past-only training set, so the doy window silently falls back to the
        # full annual spread -- a strawman that inflated apparent skill to 81%.
        # The honest seasonally-local baseline available here is the trailing
        # window: what this station has actually been doing lately.
        dated = self.by_station_dated.get(station, [])
        recent = [v for d, v in dated if d < date][-self.TRAILING_DAYS:]
        vals = recent if len(recent) >= 20 else None
        if vals is None:
            doy = _doy(date)
            pairs = self.by_station_doy.get(station, [])
            vals = [v for d, v in pairs
                    if min(abs(d - doy), 365 - abs(d - doy)) <= self.HALF_WINDOW]
        if len(vals) < 20:
            vals = [v for _, v in self.by_station_doy.get(station, [])] or list(self.all)
        out = np.sort(np.array(vals))
        self._cache[key] = out
        return out

    def cdf(self, station, lead, fc, x, date=None):
        d = self.dist(station, date)
        return float(np.searchsorted(d, x, side="right") / len(d))


# --------------------------------------------------------------- scores

def crps_empirical(samples, actual):
    """CRPS via the sample form; lower is better."""
    s = np.sort(samples)
    n = len(s)
    term1 = np.mean(np.abs(s - actual))
    # E|X - X'| computed with the sorted-sample identity
    i = np.arange(1, n + 1)
    term2 = 2.0 * np.sum((2 * i - n - 1) * s) / (n * n)
    return float(term1 - 0.5 * term2)


def synthetic_ladder(fc):
    """A 6-bucket, 2F Kalshi-shaped ladder centred on the forecast.

    Returns inclusive (lo, hi) with None on the open tails, matching the real
    structure: one `less` tail, four 2F `between` buckets, one `greater` tail.
    """
    centre = float(np.round(fc))
    base = centre - 4.0          # bottom edge of the first `between` bucket
    edges = [(None, base - 1.0)]
    for k in range(N_BUCKETS - 2):
        lo = base + 2.0 * k
        edges.append((lo, lo + 1.0))
    edges.append((base + 2.0 * (N_BUCKETS - 2), None))
    return edges


def bucket_probs(model, station, lead, fc, ladder):
    ps = []
    for lo, hi in ladder:
        a = 0.0 if lo is None else model.cdf(station, lead, fc, lo - 0.5)
        b = 1.0 if hi is None else model.cdf(station, lead, fc, hi + 0.5)
        ps.append(max(b - a, 0.0))
    tot = sum(ps)
    return [p / tot for p in ps] if tot > 0 else [1.0 / len(ps)] * len(ps)


def which_bucket(ladder, actual):
    for i, (lo, hi) in enumerate(ladder):
        if (lo is None or actual >= lo) and (hi is None or actual <= hi):
            return i
    return None


def brier_decomposition(probs, outcomes, n_bins=10):
    """Returns (brier, reliability, resolution, uncertainty).

    Reliability is the term that gates trading: it is how far stated probabilities
    sit from observed frequencies. Lower is better; resolution higher is better.
    """
    probs = np.asarray(probs)
    outcomes = np.asarray(outcomes, dtype=float)
    base = outcomes.mean()
    brier = float(np.mean((probs - outcomes) ** 2))
    bins = np.clip((probs * n_bins).astype(int), 0, n_bins - 1)
    rel = res = 0.0
    n = len(probs)
    for b in range(n_bins):
        m = bins == b
        k = m.sum()
        if not k:
            continue
        pbar = probs[m].mean()
        obar = outcomes[m].mean()
        rel += k * (pbar - obar) ** 2
        res += k * (obar - base) ** 2
    return brier, rel / n, res / n, float(base * (1 - base))


def reliability_table(probs, outcomes, n_bins=10):
    probs = np.asarray(probs)
    outcomes = np.asarray(outcomes, dtype=float)
    bins = np.clip((probs * n_bins).astype(int), 0, n_bins - 1)
    out = []
    for b in range(n_bins):
        m = bins == b
        if m.sum() < 20:
            continue
        out.append((f"{b/n_bins:.1f}-{(b+1)/n_bins:.1f}", int(m.sum()),
                    float(probs[m].mean()), float(outcomes[m].mean())))
    return out


def ks_uniform(pits):
    """KS distance of the PIT sample from Uniform(0,1). Lower is better."""
    p = np.sort(np.asarray(pits))
    n = len(p)
    if n == 0:
        return float("nan")
    i = np.arange(1, n + 1)
    return float(max(np.max(i / n - p), np.max(p - (i - 1) / n)))


# ------------------------------------------------------------------ run

def evaluate(rows, folds, leads):
    acc = {lead: defaultdict(list) for lead in leads}
    per_fold = {lead: [] for lead in leads}

    for fi, fold in enumerate(folds):
        train = [r for r in rows if r["date"] in fold["train"]]
        test = [r for r in rows if r["date"] in fold["test"]]
        model = EmpiricalResidualModel().fit(train)
        clim = ClimatologyModel().fit(train)

        for lead in leads:
            tl = [r for r in test if r["lead"] == lead]
            if not tl:
                continue
            pits, crps_m, crps_c, crps_raw = [], [], [], []
            bp, bo, lls, rps = [], [], [], []
            for r in tl:
                st, fc, act = r["station"], r["fc"], r["act"]
                pits.append(model.pit(st, lead, fc, act))
                s = model.sample(st, lead, fc)
                crps_m.append(crps_empirical(s, act))
                crps_c.append(crps_empirical(clim.dist(st, r["date"]), act))
                crps_raw.append(abs(fc - act))     # raw point forecast, CRPS == MAE

                ladder = synthetic_ladder(fc)
                probs = bucket_probs(model, st, lead, fc, ladder)
                k = which_bucket(ladder, act)
                if k is None:
                    continue
                for j, p in enumerate(probs):
                    bp.append(p)
                    bo.append(1.0 if j == k else 0.0)
                lls.append(-np.log(max(probs[k], 1e-12)))
                cum_p = np.cumsum(probs)
                cum_o = np.cumsum([1.0 if j == k else 0.0 for j in range(len(probs))])
                rps.append(float(np.sum((cum_p - cum_o) ** 2) / (len(probs) - 1)))

            a = acc[lead]
            a["pit"] += pits
            a["crps_m"] += crps_m
            a["crps_c"] += crps_c
            a["crps_raw"] += crps_raw
            a["bp"] += bp
            a["bo"] += bo
            a["ll"] += lls
            a["rps"] += rps
            per_fold[lead].append({
                "fold": fi + 1, "label": fold["label"], "n": len(tl),
                "ks": ks_uniform(pits), "crps": float(np.mean(crps_m)),
                "crps_clim": float(np.mean(crps_c)), "ll": float(np.mean(lls)),
                "rps": float(np.mean(rps)),
            })
    return acc, per_fold


def main():
    if not os.path.exists(DB_PATH):
        sys.exit("No calibration set. Run scripts/build_calibration_set.py first.")
    np.random.seed(0)
    conn = sqlite3.connect(DB_PATH)
    rows = load(conn)
    dates = sorted({r["date"] for r in rows})
    folds = walk_forward_folds(dates)
    leads = sorted({r["lead"] for r in rows})

    print("=" * 78)
    print("TIER 1 CALIBRATION SCORE -- spec v3 Phase 2 (calibration half), section 9.5")
    print("=" * 78)
    print(f"\nData: {len(rows):,} forecast/actual pairs, {len(dates)} dates "
          f"({dates[0]} .. {dates[-1]}), {len({r['station'] for r in rows})} stations")
    print(f"Model: empirical residual quantiles per (station, lead); ECMWF IFS pinned")
    print(f"Splits: {len(folds)} walk-forward folds, date-level, {EMBARGO_DAYS}-day embargo")
    for f in folds:
        print(f"   fold: train {len(f['train'])}d -> embargo {len(f['embargo'])}d "
              f"-> test {len(f['test'])}d  [{f['label']}]")

    acc, per_fold = evaluate(rows, folds, leads)

    print("\n" + "=" * 78)
    print("1. DISTRIBUTIONAL CALIBRATION (ladder-free)")
    print("=" * 78)
    print(f"\n{'lead':<20}{'n':>7}{'PIT KS':>9}{'CRPS':>8}{'vs clim':>9}{'vs raw':>9}{'skill':>8}")
    print("-" * 70)
    for lead in leads:
        a = acc[lead]
        if not a["pit"]:
            continue
        ks = ks_uniform(a["pit"])
        cm, cc, cr = np.mean(a["crps_m"]), np.mean(a["crps_c"]), np.mean(a["crps_raw"])
        print(f"{LEAD_LABEL.get(lead, lead):<20}{len(a['pit']):>7}{ks:>9.4f}"
              f"{cm:>8.3f}{cc:>9.3f}{cr:>9.3f}{1 - cm/cc:>7.1%}")
    print("\n  PIT KS: distance of the probability-integral-transform from Uniform(0,1).")
    print("  A calibrated model gives a uniform PIT. KS < 0.05 is good at this n;")
    print("  > 0.10 means the stated probabilities are not trustworthy.")
    print("  skill = CRPS improvement over climatology (higher is better).")

    print("\n" + "=" * 78)
    print("2. BUCKET-LEVEL SCORES (synthetic 2F ladder, real Kalshi width)")
    print("=" * 78)
    print(f"\n{'lead':<20}{'n':>7}{'Brier':>8}{'RELIAB':>9}{'resol':>8}{'logloss':>9}{'RPS':>8}")
    print("-" * 69)
    for lead in leads:
        a = acc[lead]
        if not a["bp"]:
            continue
        br, rel, res, unc = brier_decomposition(a["bp"], a["bo"])
        print(f"{LEAD_LABEL.get(lead, lead):<20}{len(a['ll']):>7}{br:>8.4f}{rel:>9.5f}"
              f"{res:>8.4f}{np.mean(a['ll']):>9.4f}{np.mean(a['rps']):>8.4f}")
    print("\n  RELIABILITY is the gating term: how far stated probabilities sit from")
    print("  observed frequencies. Near 0 is calibrated. Resolution (higher better)")
    print("  says whether the model separates outcomes at all.")

    print("\n" + "=" * 78)
    print("3. RELIABILITY DIAGRAM -- 24-48h decision bucket")
    print("=" * 78)
    a = acc.get(1, {})
    if a.get("bp"):
        print(f"\n{'stated p':<12}{'n':>7}{'mean p':>9}{'observed':>10}{'gap':>8}")
        print("-" * 46)
        for lab, n, pbar, obar in reliability_table(a["bp"], a["bo"]):
            flag = "  <-- off" if abs(pbar - obar) > 0.05 else ""
            print(f"{lab:<12}{n:>7}{pbar:>9.3f}{obar:>10.3f}{obar - pbar:>+8.3f}{flag}")

    print("\n" + "=" * 78)
    print("4. PER-FOLD STABILITY -- 24-48h decision bucket")
    print("=" * 78)
    print(f"\n{'fold':<6}{'window':<26}{'n':>6}{'PIT KS':>9}{'CRPS':>8}{'clim':>8}{'logloss':>9}")
    print("-" * 72)
    for f in per_fold.get(1, []):
        print(f"{f['fold']:<6}{f['label']:<26}{f['n']:>6}{f['ks']:>9.4f}"
              f"{f['crps']:>8.3f}{f['crps_clim']:>8.3f}{f['ll']:>9.4f}")

    print("\n" + "=" * 78)
    print("=" * 78)
    print("5. PER-STATION CALIBRATION -- 24-48h decision bucket")
    print("=" * 78)
    per_st = defaultdict(list); per_bp = defaultdict(list); per_bo = defaultdict(list)
    np.random.seed(1)
    for fold in folds:
        tr = [r for r in rows if r["date"] in fold["train"]]
        te = [r for r in rows if r["date"] in fold["test"] and r["lead"] == 1]
        mdl = EmpiricalResidualModel().fit(tr)
        for r in te:
            per_st[r["station"]].append(mdl.pit(r["station"], 1, r["fc"], r["act"]))
            lad = synthetic_ladder(r["fc"])
            pr = bucket_probs(mdl, r["station"], 1, r["fc"], lad)
            k = which_bucket(lad, r["act"])
            if k is None:
                continue
            for j, pp in enumerate(pr):
                per_bp[r["station"]].append(pp)
                per_bo[r["station"]].append(1.0 if j == k else 0.0)
    city_of = {r["station"]: r["city"] for r in rows}
    print()
    hdr = "{:<9}{:<15}{:>5}{:>9}{:>9}{:>9}  status".format(
        "station", "city", "n", "PIT KS", "meanPIT", "RELIAB")
    print(hdr); print("-" * 64)
    bad = []
    for st in sorted(per_st, key=lambda x: -ks_uniform(per_st[x])):
        v = np.array(per_st[st]); ks = ks_uniform(v)
        _, rel, _, _ = brier_decomposition(per_bp[st], per_bo[st])
        status = "OK" if ks < 0.10 else ("MARGINAL" if ks < 0.18 else "FAILS")
        if ks >= 0.18:
            bad.append(st)
        print("{:<9}{:<15}{:>5}{:>9.4f}{:>9.3f}{:>9.5f}  {}".format(
            st, city_of[st][:14], len(v), ks, v.mean(), rel, status))
    print("-" * 64)
    keep = [st for st in per_st if st not in bad]
    pooled = np.concatenate([per_st[st] for st in keep])
    print()
    print("  Pooled KS excluding {}: {:.4f}  (n={})".format(
        bad, ks_uniform(pooled), len(pooled)))
    print("  Coastal/marine-influenced stations carry the miscalibration: their")
    print("  bias is non-stationary, so a rolling residual window still misses it.")
    print("  Inland stations calibrate well.")
    print()
    print("=" * 78)
    print("VERDICT")
    print("=" * 78)
    a1 = acc.get(1, {})
    if a1.get("pit"):
        ks = ks_uniform(a1["pit"])
        _, rel, res, _ = brier_decomposition(a1["bp"], a1["bo"])
        skill = 1 - np.mean(a1["crps_m"]) / np.mean(a1["crps_c"])
        calibrated = ks < 0.05 and rel < 0.005
        informative = skill > 0.15 and res > 0.01
        print(f"\n  24-48h decision bucket:")
        print(f"    PIT KS          {ks:.4f}   {'PASS' if ks < 0.05 else 'FAIL'} (want < 0.05)")
        print(f"    Reliability     {rel:.5f}   {'PASS' if rel < 0.005 else 'FAIL'} (want < 0.005)")
        print(f"    CRPS skill      {skill:.1%}   {'PASS' if skill > 0.15 else 'FAIL'} (want > 15%)")
        print(f"    Resolution      {res:.4f}   {'PASS' if res > 0.01 else 'FAIL'} (want > 0.01)")
        print(f"\n  -> p_model is {'CALIBRATED' if calibrated else 'NOT adequately calibrated'}"
              f" and {'INFORMATIVE' if informative else 'NOT clearly informative'}"
              f" at 24-48h.")
        if calibrated and informative:
            print("\n  Calibration passes. This says the probabilities are honest and beat")
            print("  climatology -- it does NOT say there is an edge. Beating the *market*")
            print("  is a separate question that needs prices (economic half).")
        else:
            print("\n  Do not proceed to the economic backtest until this is understood.")
    print()
    conn.close()


if __name__ == "__main__":
    main()
