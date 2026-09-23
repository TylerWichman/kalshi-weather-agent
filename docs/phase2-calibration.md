# Phase 2, Calibration Half — Is `p_model` Honest?

Run 2026-09-22. No Kalshi prices involved. Reproduce: `scripts/build_calibration_set.py`
then `scripts/calibrate.py`.

**Verdict: conditional pass.** Three of four gates pass cleanly. The fourth (PIT
uniformity) fails at the pooled level, and the failure is **concentrated and
explainable** rather than diffuse. Two named exclusions make the model usable; one of
them is commercially awkward.

## Data

| | |
|---|---|
| Pairs | **26,124** forecast/actual |
| Dates | 363 (2025-09-22 → 2026-09-19) — a **full seasonal cycle** |
| Stations | 12 |
| Leads | 0–5 days |
| Forecast | Open-Meteo previous-runs, **`ecmwf_ifs025` pinned** |
| Actual | NCEI GHCN-Daily TMAX |

Both sources validated before use:

- **GHCN TMAX matches the NWS final CLI product exactly, 58/58** across all 12
  stations. CLI is the product Kalshi's station IDs are named after, so GHCN is the
  same number with years of history instead of seven days.
- **The forecast archive does not leak.** Error grows monotonically with lead under
  ECMWF (CRPS 1.40 → 2.02 → 2.26 → 2.48 → 2.71 → 2.97). A leaking archive would score
  equally well at every lead.
- **`best_match` must not be used.** The default blend switches model families near
  48h, showing up as a bias discontinuity (MAE 2.10 → 4.76, bias +1.3 → +4.8°F), not
  smooth skill decay. A backtest on the default would be fitting that artifact.

## Model

`T_max ~ forecast + empirical residual quantiles(station, lead)`, fit on a **rolling
45-day window**. Empirical quantiles rather than a fitted normal, so the residual skew
survives. Per-station bias correction falls out for free.

Deliberately not ensemble-based: Open-Meteo serves no historical ensemble, and
ensemble spread is underdispersed anyway. Calibrating from realized errors is both
available and more honest.

## Method (spec §9.5)

Chronological, **date-level** splits (all 12 cities on one day share a weather regime,
so a row-level split would leak), **7-day embargo**, 4 walk-forward folds.

## Results — 24–48h decision bucket

| gate | value | target | |
|---|---|---|---|
| PIT KS | 0.0893 | < 0.05 | **FAIL** |
| Reliability | 0.00230 | < 0.005 | PASS |
| CRPS skill vs climatology | 71.6% | > 15% | PASS |
| Resolution | 0.0123 | > 0.01 | PASS |

By lead time, with 0–24h as the §9.5 control:

| lead | PIT KS | CRPS | skill | Brier | reliability | RPS |
|---|---|---|---|---|---|---|
| 0–24h (control) | 0.0719 | 1.400 | 80.3% | 0.1191 | 0.00152 | 0.1103 |
| **24–48h (decision)** | **0.0893** | **2.020** | **71.6%** | **0.1283** | **0.00230** | **0.1469** |
| 48–72h | 0.0833 | 2.256 | 68.3% | 0.1299 | 0.00234 | 0.1576 |
| 72–96h | 0.0946 | 2.483 | 65.1% | 0.1294 | 0.00223 | 0.1663 |
| 120–144h | 0.0869 | 2.968 | 58.3% | 0.1313 | 0.00224 | 0.1832 |

Skill degrades smoothly with lead, as it should.

## Where the failure lives

### 1. Coastal stations

| station | city | PIT KS | mean PIT | status |
|---|---|---|---|---|
| **KLAX** | Los Angeles | **0.2910** | 0.305 | **FAILS** |
| **KNYC** | New York City | **0.2000** | 0.435 | **FAILS** |
| KPHL | Philadelphia | 0.1734 | 0.436 | marginal |
| KHOU | Houston | 0.1524 | 0.420 | marginal |
| KDCA, KDFW, KOKC, KATL | | 0.105–0.125 | ~0.455 | marginal |
| KMIA, KDEN, KMDW, KAUS | | 0.066–0.099 | ~0.47 | OK |

Excluding LAX and NYC, pooled KS improves to **0.0717**.

LAX is the worst by a wide margin, with mean PIT 0.305 — actuals land in the lower
tail far more often than stated, i.e. the distribution sits too warm. This is the same
station Phase 1 flagged with the largest forecast bias (+4.4°F). The model already
applies a per-station correction, so what remains is **non-stationary** bias: the
marine layer shifts the offset faster than a rolling window tracks it.

**This is commercially awkward.** LAX is the single largest market on the watchlist —
433k of ~1.35M contracts, about **32% of all volume**. The city with the most
liquidity is the one the model handles worst.

### 2. Spring transition

| fold | window | PIT KS |
|---|---|---|
| 1 | Jan 20 – Mar 20 | 0.0746 |
| **2** | **Mar 21 – May 19** | **0.2613** |
| 3 | May 20 – Jul 18 | 0.1249 |
| **4** | **Jul 19 – Sep 19** | **0.0470** (passes) |

Calibration is seasonal. It is worst through the spring regime transition, when a
rolling residual window lags fastest-changing conditions, and best in stable late
summer, where it passes outright.

Having a full year of data is what made this visible — a two-week live sample would
have shown one regime and called it the answer.

## Two corrections made during this run

Both were structural mis-specifications diagnosed from training-set statistics, not
threshold tuning. Disclosed because they happened after seeing first-run output:

1. **Expanding → rolling training window.** The first run used all history, and PIT KS
   got *worse* as training data grew (0.10 → 0.21 across folds) — the signature of
   stale seasonal residuals. Residual means run +2.9°F in February against −0.3°F in
   July. A rolling window is also what production would do.
2. **Climatology baseline fixed.** The first baseline pooled a station's whole year
   (KNYC sd 18.4°F, range 17–100°F), which any forecast beats trivially and inflated
   skill to 81.5%. Day-of-year conditioning needs multiple years and silently fell
   back with one, so the baseline is now a **trailing 30-day window** — seasonally
   local and genuinely knowable. Honest skill: **71.6%**.

## What this does and does not say

**Does:** the probabilities are well-calibrated in the reliability sense (0.0023), the
model carries real information (71.6% CRPS skill, resolution 0.0123), and skill
degrades smoothly with lead.

**Does not:** say anything about edge. Beating climatology is not beating the market.
Kalshi's prices may be just as well calibrated, and if so there is no trade. That is
the economic half.

## Recommendation

**Proceed to the historical loader, with two constraints written into the model:**

1. **Exclude LAX and NYC from live sizing until a coastal correction exists.** Keep
   scoring them. A marine-layer feature — onshore flow, dewpoint spread, or simply a
   much shorter residual window for coastal sites — is the obvious Tier 2 candidate.
   Losing 32% of volume hurts, so this is worth real effort before Phase 6.
2. **Treat spring as a known-degraded regime.** Either widen the predictive
   distribution when recent residual volatility rises, or stand down when rolling
   residual spread exceeds its trailing norm. The model should know when it is in a
   regime it handles badly.

Neither blocks the economic backtest, because both are exclusions rather than
corrections to fit.
