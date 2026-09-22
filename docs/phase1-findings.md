# Phase 1 — Data Pipeline: Findings

Built 2026-09-22. Pipeline is running on a schedule and accumulating.
Spec: `kalshi-weather-daytrading-agent-spec-v3.md`.

## What shipped

| component | file | status |
|---|---|---|
| Storage layer (spec §7) | `src/db.py` | 10 tables, append-only where it matters |
| Kalshi client + station/ladder verification | `src/kalshi.py` | working, unauthenticated |
| NWS + Open-Meteo + observations ingestion | `src/weather.py` | working, no API keys |
| Data Collector Agent | `src/collector.py` | 4 jobs: contracts, books, forecasts, observations |
| Phase 1 acceptance check | `scripts/verify_phase1.py` | passing on 22/24, 2 explained |

Scheduled and running:

| task | cadence | why |
|---|---|---|
| `KalshiWeatherBasisLogger` | daily 15:00 | CLI products age out in ~7 days |
| `KalshiWeatherCollectorFast` | every 15 min | order books and observations are **not backfillable at all** |
| `KalshiWeatherCollectorSlow` | every 6 h | contract discovery + forecast runs |

Kalshi serves no historical order-book endpoint, so every 15-minute slot missed is
data that cannot ever be recovered. That is the same argument that justified the
basis logger, applied to market data.

## 1. The Phase 1 gate: station matching — PASS

Spec Phase 1 says get station matching right "before anything else". Verified three
ways, all green:

- **Kalshi's own rules text** is parsed per market and checked against
  `config/watchlist.json`. A mismatch raises `StationMismatch`, logs a risk event
  and skips the series rather than ingesting it. 144/144 markets verified.
- **Ladder structure** is checked for contiguity and for agreement with Kalshi's
  human-readable subtitle. 24/24 ladders clean.
- **NWS point forecast vs market modal bucket**: 22/24 ladders within one bucket.
  The 2 exceptions were both Atlanta, and are explained in §3 — not a wiring fault.

### A real off-by-one, caught by the ladder check

The `less` tail is **strict** against its strike. `cap_strike=80` means "79° or
below", not "≤80". My first implementation had `≤cap`, one degree too wide.

This also existed in the basis logger, where it made the settled bucket one degree
too permissive and could have inflated the measured agreement rate. Both were fixed
and the basis was recomputed: **the 0-flips-in-334 result holds after the correction.**

`kalshi.verify_bucket_bounds()` now cross-checks every computed bound against
Kalshi's own subtitle text, so this cannot recur silently.

## 2. Both forecast inputs carry per-station bias

Open-Meteo interpolates a ~25 km grid cell to a point; the NWS gridpoint product is
gridded too. Neither is a station forecast. Measured ensemble-mean minus NWS point,
24 station-days:

```
overall: mean -0.54F  median -1.20F  sd 2.06F  range -3.0..+5.5
```

Per station, sign is **stable across days** — a grid-to-point offset, not noise:

| station | mean | per-day |
|---|---|---|
| KMIA | −2.46 | −2.5, −2.4 |
| KATL | −2.21 | −3.0, −1.4 |
| KPHL | −1.88 | −2.0, −1.8 |
| KOKC | −1.83 | −1.7, −2.0 |
| KHOU | +0.05 | +0.1, +0.0 |
| KDCA | +2.12 | +2.0, +2.2 |
| KLAX | **+4.44** | +3.4, +5.5 |

LAX is the outlier in both magnitude and direction — a coastal station whose grid
cell misses the marine layer.

At 2° bucket width, a 2–4°F bias is **1–2 whole buckets**. Spec §2.2's per-station,
per-lead-time calibration is therefore load-bearing, not polish: **raw ensemble
members fed into bucket probabilities would be wrong by more than the bucket width.**

## 3. The important finding: at short lead, the market beats our inputs badly

Measured against the actual CLI values for 2026-09-22, using forecasts snapshotted at
5–8 h lead:

| predictor | correct bucket |
|---|---|
| **Kalshi market modal bucket** | **12 / 12 (100%)** |
| NWS gridpoint | 4 / 12 (33%) |
| Ensemble mean | 1 / 12 (8%) |

Error against the realized station value:

| source | mean | MAE | \|err\| ≥ 2°F |
|---|---|---|---|
| NWS gridpoint | −1.08°F | 1.75°F | 6/12 |
| Ensemble mean | −1.45°F | 2.17°F | 7/12 |

The reason is structural, not a bug: **a daily high is set in the afternoon.** By
5–8 h before local midnight it has already happened, the market can see it in the
observations, and most ladders are priced at 99–100¢ on the correct bucket. Our
gridded forecasts are still predicting a day that is effectively over.

### Why this is dangerous, not just disappointing

Atlanta on 2026-09-22 is the worked example. Actual high 86°F, set at 2:59 PM.

- Market: `T87` (≤86) at **99¢ bid** — correct.
- NWS gridpoint: **90°F.**
- A naive `p_model` off that forecast puts most mass on the 89–90 bucket, which the
  market is offering at **1¢**.

That reads as a ~90-point edge on a 1¢ contract. It is not an edge; it is a certain
total loss. **The fee gate does not save you** — fees are trivial at 1¢, so a
fee-aware filter waves it straight through. Kelly sizing on a 90-point edge would
size it enormously.

This is the single most dangerous failure mode found so far, and neither spec v2 nor
v3 guarded against it.

### Fix, implemented

`station_observations` table plus a collector job, polling live station temperatures
every 15 minutes. The running observed max tracks the realized CLI value within ~1°F
— far better than either forecast at this lead:

| station | observed max so far | CLI actual |
|---|---|---|
| KATL | 86.0 | 86 |
| KMIA | 89.6 | 89 |
| KMDW | 64.4 | 64 |
| KDFW | 96.8 | 96 |
| KDEN | 82.9 | 83 |

**Still required (not yet built), and these belong in Phase 2/3:**

1. **`p_model` must condition on observations already in hand**, not forecasts alone.
   For a same-day high the estimate is `max(observed_so_far, P(remaining hours exceed it))`,
   which collapses toward certainty as the afternoon passes.
2. **A hard short-lead guard.** No position on a same-day contract past the point the
   high is plausibly set unless the estimate is observation-conditioned. This belongs
   in Risk & Sizing (§2.3) as a limit enforced in code, next to the spread gate.
3. **Treat a large edge at short lead as a red flag, not an opportunity.** At 5 h lead
   against a 100¢-confident market, a 90-point edge means the model is broken. A
   sanity bound that blocks and logs implausibly large edges would have caught this.

## 4. Where the edge must actually live

Phase 0 assumed the edge came from reading forecast models better than the crowd.
Phase 1 says that cannot be true at short lead, where the market is simply reading
observations and is right essentially always.

So any real edge has to be at **longer lead — tomorrow's contracts and beyond**,
where the high has not happened and forecast skill still matters. Note that the
29–32 h ladders in the snapshot are priced far less confidently than the same-day
ones, which is consistent with genuine uncertainty still being present.

This sharpens Phase 2's question. It is no longer "does the model beat the market",
it is **"does the model beat the market at 24–48 h lead, after fees, given that the
0–12 h window is unwinnable?"** Phase 2 should score by lead-time bucket and treat
short-lead performance as a control rather than evidence.

Not yet testable: tomorrow's actuals do not exist. The accumulating logs will answer
it within a couple of weeks.

## 5. Current state

```
contracts            144 markets, 24 ladders, 12 cities, all station-verified
market_prices        accumulating every 15 min, full depth retained
forecast_snapshots   NWS point + 82 ensemble members (31 GEFS + 51 ECMWF) per station-day
station_observations 2,607 rows across 12 stations, accumulating every 15 min
risk_events          none
```

## 6. Recommended spec changes

1. **Add live station observations to §2.1 as a first-class data source.** v3 lists
   forecasts, ensembles, climatology and order books — not observations. They are the
   dominant input at short lead.
2. **Add the short-lead guard to §2.3** as a hard limit enforced in code.
3. **Add an implausible-edge circuit breaker to §2.3.** An edge above some threshold
   against a confident market indicates model failure, not opportunity.
4. **Add per-station forecast bias calibration to §2.2 as a prerequisite**, with the
   measured 2–4°F magnitudes recorded so its importance is not re-litigated.
5. **Restate the edge hypothesis in §1 and Phase 2** around 24–48 h lead, and require
   Phase 2 to score by lead-time bucket.
