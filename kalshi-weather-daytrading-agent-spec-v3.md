# Kalshi Weather Day-Trading Agent — Build Spec (v3)

## 0. Read this first

**This supersedes v1 and v2.** It keeps everything v2 added — the mandatory mock-money simulation
week and the live intraday dashboard — and corrects four things that Phase 0 discovery proved wrong
or incomplete in both prior versions. **Phases 0, 0.5 and 1 are complete and running**; findings are
in `docs/phase0-discovery.md` and `docs/phase1-findings.md`, the confirmed contract universe is in
`config/watchlist.json`, and the pipeline lives in `src/`. Fees are confirmed as of 2026-09-22 (§3).

### What changed from v2, and why

| # | v2 said | Reality | Where it hits |
|---|---|---|---|
| 1 | NWS is "typically Kalshi's settlement source" | **The Weather Company (TWC)** settles every one of the 48 daily temp series. NWS-settled temp series exist but are **delisted with zero open markets**. Measured basis: **0 bucket flips in 334 observations** (§2.7) — favorable, but only 7 days deep. | §2.1, §4, §5, §9 |
| 2 | Contracts are independent binaries with a threshold | Each event is a **mutually exclusive, exhaustive 6-bucket ladder**. | §2.2, §2.6 |
| 3 | Watchlist is "high/low contracts" undifferentiated | **Highs are ~18× the volume of lows**; lows quote 7–11¢ spreads that exceed any plausible edge. | §2.1, §8 |
| 4 | Fee = `0.07 × …`, maker ≈ 25% of taker | **CONFIRMED 2026-09-22.** Taker 0.07 formula is correct. **Maker is $0 for weather**, not 25% — the API's `fee_type` enum puts weather 409/409 on taker-only `quadratic`, with `quadratic_with_maker_fees` used only by 44 Financials/Economics series. Resting orders are free, so maker-only becomes the default. | §3, §2.3 |
| 5 | *(not in v2)* | At 0–12h lead the market picks the correct bucket 12/12 vs. our best forecast input's 4/12 — the high has already happened. **The 0–12h window is hard-blocked for live trading** until the 24–48h edge is proven separately. | §2.1, §2.3, §9.5 |

Core direction is unchanged: **Kalshi's daily temperature high/low contracts**, traded actively
throughout the day — not buy-and-hold-to-resolution, but a system that enters and exits positions
multiple times as new forecast data and market prices move.

Why this niche:
- **Breadth:** 24 cities × daily contracts = many simultaneous markets to scan for mispricing.
- **Real forecast data most traders won't fully use:** NWS and global ensembles (GFS, ECMWF) update
  every ~6 hours with genuine new information.
- **Contracts resolve daily**, so there's a constant stream of fresh markets.
- **Fees are a first-class design constraint, not an afterthought** (see §3).
- **The ladder structure gives a second, model-independent signal** (see §2.6) that v1/v2 missed.

---

## 1. Objective

Build an automated system that:
1. Tracks open Kalshi daily **high**-temperature contracts across the watchlist in §8.
2. Continuously compares its own weather-model-based probability estimate to Kalshi's live price.
3. Enters and exits positions intraday as new forecast runs land and as prices move.
4. Filters every candidate trade through a **fee-aware profitability check** before acting.
5. Runs a **continuous ladder-coherence check** independent of the forecast model (§2.6).
6. Manages risk automatically within hard limits (§2.3).
7. **Measures the NWS↔TWC settlement basis continuously, starting immediately** (§2.7) — this is a
   prerequisite for trusting anything in Phase 2, not a Phase 7 nicety.
8. Runs a **mandatory one-week live simulation** with mock money before real capital (§8, Phase 5.5).
9. Produces a **live dashboard** for the trading day plus a **daily end-of-day summary**.

Non-goal: guaranteed daily profit. Expect variance day to day; the goal is positive expected value
over time, with fees and slippage genuinely accounted for, not assumed away.

---

## 2. System Architecture

Six components. The Forecasting and Execution agents run on a tight intraday loop; the Reporting
Agent serves two outputs (live + EOD); the Basis Logger runs independently of the trading path and
starts before Phase 1 is complete.

```
┌─────────────────┐   ┌──────────────────┐   ┌───────────────────┐
│  1. Data         │──▶│  2. Forecasting   │──▶│  3. Risk & Sizing  │
│  Collector Agent │   │  Agent            │   │  Agent (fee-aware) │
│  (order books    │   │  (distribution    │   │                    │
│  5-15min; model  │   │  → 6 buckets;     │   │                    │
│  runs ~6h)       │   │  re-scores live)  │   │                    │
└────────┬────────┘   └──────────────────┘   └─────────┬──────────┘
         │                                                  │
         │            ┌──────────────────┐                  ▼
         ├───────────▶│  2.6 Ladder       │──────▶┌───────────────────┐
         │            │  Coherence Check  │       │  (trade decision) │
         │            │  (no model; pure  │       │                   │
         │            │  order-book math) │       └─────────┬─────────┘
         │            └──────────────────┘                  │
         │                                                  ▼
         │   ┌─────────────────┐   ┌──────────────────┐
         │   │  5. Reporting/   │◀──│  4. Execution     │
         │   │  Dashboard Agent │   │  Agent (intraday  │
         │   │  (live + EOD)    │   │  enter/exit loop; │
         │   └─────────────────┘   │  sim or live mode)│
         │                          └──────────────────┘
         ▼
┌──────────────────────────┐
│  2.7 NWS↔TWC Basis Logger │   runs from day one, independent of
│  (daily; off trading path)│   trading; gates Phase 2 go/no-go
└──────────────────────────┘
```

### 2.1 Data Collector Agent

Pulls the live list of open Kalshi daily high-temperature contracts across the §8 watchlist. Per
contract it pulls:

- **NWS point forecast** (`api.weather.gov`) for the station matched to the contract. **This is a
  forecast *input*, not the settlement source** — see §2.7. Free, no key, requires a User-Agent
  header. Gridpoint IDs for all 24 stations are pre-resolved in `config/watchlist.json`.
- **Ensemble model data** via Open-Meteo's `ensemble-api.open-meteo.com/v1/ensemble` — confirmed
  working, free, no key, returns **82 members** per point (GEFS 31 + ECMWF IFS 51). Request with
  `temperature_unit=fahrenheit` so there's no conversion rounding at bucket boundaries.
- **Live station observations** (`api.weather.gov/stations/{id}/observations`) — polled every
  15 minutes. **Added after Phase 1 measurement; this is the dominant input at short lead.** At 5-8h
  before a daily high is final the high has usually already occurred, and the market prices off
  observed data while gridded forecasts lag it by 2-4°F. Measured: market 12/12 correct buckets,
  NWS gridpoint 4/12, ensemble mean 1/12 (`docs/phase1-findings.md`). The running observed max
  tracks the realized value within ~1°F.
- **Live Kalshi order book** (`/markets/{ticker}/orderbook`) — full depth, not just top of book.
  Production read endpoints work **unauthenticated**.
- **Historical station climatology** — forecast-vs-actual accuracy by lead time, per station, built
  in-house from NWS station history.

Scheduling is tied to real information events, not just wall clock: refresh forecasts on each new
GFS/ECMWF run (~every 6h), poll order books every 5–15 min during active hours.

Storage is append-only and timestamped — needed to reconstruct "what was known when" for
backtesting, auditing, and the live dashboard.

**Ticker naming is inconsistent** (`KXHIGHNY`, `KXHIGHTATL`, `KXHIGHAUS`, `KXHIGHTHOU`). Do **not**
derive tickers from city codes; read them from the `/series` endpoint and match against
`config/watchlist.json`.

### 2.2 Forecasting Agent — ladder-aware (changed from v2)

**v2 was wrong to model each contract as an independent binary.** Each Kalshi event is a mutually
exclusive, exhaustive ladder of 6 markets — one `less` tail, four 2°-wide `between` buckets, one
`greater` tail. Example, `KXHIGHNY-26SEP23`:

| ticker | type | range | bid | ask |
|---|---|---|---|---|
| `-T65` | less | ≤64° | 0.06 | 0.07 |
| `-B65.5` | between | 65–66° | 0.26 | 0.28 |
| `-B67.5` | between | 67–68° | 0.47 | 0.48 |
| `-B69.5` | between | 69–70° | 0.13 | 0.14 |
| `-B71.5` | between | 71–72° | 0.02 | 0.03 |
| `-T72` | greater | ≥73° | 0.01 | 0.02 |

**Required approach:** fit **one continuous predictive distribution** over the station's daily high,
then **integrate it over the six bucket boundaries** to get all six probabilities at once. Do not
produce six independent `P(threshold)` estimates — they will not be mutually coherent, and the
incoherence will read as fake edge.

- **Per-station bias correction is a prerequisite, not a refinement.** Both forecast inputs are
  gridded products interpolated to a point, and both carry a station-specific offset that holds its
  sign across days: measured −2.5°F (Miami) to **+4.4°F (LAX)**, mean −0.54°F, sd 2.06°F. At 2°
  bucket width that is **1-2 whole buckets**. Raw ensemble members integrated over bucket edges
  without this correction are wrong by more than the bucket width. Fit it per station and per lead
  time before scoring anything.
- **Condition on observations already in hand.** For a same-day high, `p_model` is not a forecast —
  it is `max(observed_so_far, P(remaining hours exceed it))`, collapsing toward certainty as the
  afternoon passes. A model that ignores the observed maximum will confidently contradict a market
  that can see it.
- **Tier 1 (ship first):** treat the 82 ensemble members as a sample; fit a normal or skew-normal
  (skew matters — daily highs are not symmetric, especially under cloud/frontal uncertainty); shift
  by a lead-time- and station-specific bias correction learned from historical NWS forecast-vs-actual;
  integrate over bucket edges. Blend in the NWS point forecast as a location prior where it and the
  ensemble mean disagree.
- **Tier 2 (only after Tier 1 backtests clean):** gradient boosting on ensemble spread, ensemble
  skew, day-of-year seasonality, recent station bias, cloud-cover forecast, and time-to-resolution,
  calibrated against realized outcomes. Still emits a distribution, not per-bucket binaries.

By construction the six outputs sum to 1. **Assert this in code** — it is a cheap invariant and a
violation means a boundary or integration bug.

Re-run whenever new forecast data lands **or** the Kalshi price moves meaningfully. Output per
contract per update: `{p_model, confidence_band, p_market, edge = p_model − p_market, timestamp,
lead_time_hours, ladder_id}`. This stream feeds the trading logic and the live dashboard.

### 2.3 Risk & Sizing Agent (fee-aware)

**Every candidate trade must clear a fee-aware profitability bar before sizing, not just an edge
threshold.** See §3 for the fee formula and what is and isn't confirmed about it.

- **Round-trip cost estimator:** compute the expected fee of entering *and* exiting (or holding to
  resolution) at the current price level, using the **API-sourced per-series fee parameters**, before
  evaluating any trade. Never a flat assumed percentage.
- **Minimum-edge threshold, computed dynamically per trade:** eligible only if
  `edge × position_size > estimated_round_trip_fee + required_margin`. Because the fee is quadratic
  in price, this bar is much higher near 50¢ than near the extremes, so the agent will naturally
  prefer contracts priced away from the middle. That is intended.
- **Spread-aware gate (new):** reject any candidate where the quoted spread alone exceeds the modeled
  edge. This is what disqualifies the low-temperature series wholesale (§8) and it must be enforced
  per-contract at runtime too, since liquidity varies through the day.
- **Rest orders by default — maker execution is free (§3).** Now that maker fees are confirmed $0
  for weather, this is no longer a "prefer when convenient" tradeoff. **The default is always to rest
  a limit order**, and crossing the spread as a taker is the exception that must justify itself:
  taking requires the edge to exceed the taker fee bar (1.75 points at 50¢, 0.63 at the extremes)
  *plus* the margin, whereas resting requires no fee edge at all. A maker/maker round trip costs
  **zero**, which means a trade needs only to overcome spread and adverse selection, not fees.
- **But free is not costless — model the two implicit costs.** A zero fee does not make resting
  risk-free, and the sizing logic must not treat it as though it does:
  - **Adverse selection.** A resting order fills preferentially when the market moves against it —
    you get hit exactly when you were wrong. This cost is real, appears in no fee schedule, and can
    exceed what a taker fee would have been. **Measure it in Phase 5.5** by comparing realized fill
    outcomes against the mid at fill time, and feed the estimate back into the sizing bar.
  - **Non-fill risk.** The edge can evaporate before the order fills, and on a ladder this can leave
    one leg filled and the rest not — a partial position that was never the intended bet.
  - The taker escape hatch therefore stays, for genuinely large and fast-moving edges (§2.3, v2's
    original intent), but it is now an explicit exception rather than a coin-flip tradeoff.
- **Position sizing:** fractional-Kelly (e.g. 25% of full Kelly) on the **net-of-fees** edge.
- **Correlation handling:** bucket exposure by **ladder** first (six markets on one event are one
  bet, not six), then by city, then by region. A position in `-B67.5` and a position in `-B69.5` on
  the same event are not independent.
- **Hard limits (enforced in code):**
  - Max % of capital in any single contract.
  - Max % of capital in any single **ladder/event**.
  - Max % of capital in any single city/region (weather across nearby cities is correlated).
  - Max number of open positions at once.
  - Max round trips per contract per day (prevents fee bleed from over-trading).
  - Daily loss limit — halts new trading for the day, requires manual review to resume.
  - Max slippage tolerance per order — limit orders only, reject if the book is too thin.
  - **Short-lead guard — HARD BLOCK ON LIVE TRADING (new, Phase 1).** **No live position may be
    opened in the 0–12h lead window, at all, until the 24–48h edge has been separately proven in
    Phase 2.** This is not a tunable threshold; it is a gate. At short lead the market reads
    observations and picks the correct bucket essentially always (measured 12/12 vs. our best
    forecast input's 4/12), so a forecast-driven model trading into that window is taking the wrong
    side of a settled question. The window may be reopened only by evidence, and only after the
    long-lead edge stands on its own — see §9.5 and Phase 2. Simulation and paper modes may
    continue to *score* the window as a control (§9.5), but must not size positions in it.
  - **Station exclusion — HARD GATE on LAX and NYC (new, Phase 2).** **No live
    position may be sized in KLAX or KNYC** until a coastal correction exists. Phase 2
    calibration found the PIT failure concentrated in coastal stations: KLAX KS 0.2910
    (mean PIT 0.305) and KNYC 0.2000 against a 0.05 target, with pooled KS improving
    from 0.0893 to 0.0717 once both are removed. Per-station bias correction is already
    applied, so what remains is **non-stationary** marine bias a rolling residual window
    does not track. This is a gate, not a confidence weight: a soft down-weighting would
    still trade on probabilities known to be systematically wrong, and systematic errors
    do not average out across repeated smaller bets. **Cost: LAX is ~32% of watchlist
    volume**, so this removes the deepest market — revisit as a **Tier 2** item (marine-
    layer feature, or a much shorter residual window for coastal sites) once the economic
    backtest shows the core edge is real on the other cities. Both stations continue to be
    **loaded and scored**; only sizing is blocked.
  - **Implausible-edge circuit breaker (new, Phase 1).** An edge above a configured threshold
    against a confidently-priced market (say >40 points against a market at ≥95¢) indicates model
    failure, not opportunity. Block, log a risk event, and require review. Worked example: Atlanta
    2026-09-22 settled at 86°F with the market bidding 99¢ on "≤86", while the NWS gridpoint said
    90°F — a naive model saw a ~90-point edge on a 1¢ contract that was a certain total loss.
    **The fee gate does not catch this**: fees are trivial at 1¢, so a fee-aware filter passes it
    straight through, and Kelly sizing on a 90-point edge would size it enormously.
- **Kill switch:** immediate, trivial to trigger, flattens or freezes positions on command. Surfaced
  on the live dashboard and in every EOD report.
- **Mode-aware:** identical behavior in simulation (Phase 5.5) and live (Phase 6) — same limits, same
  logic — so the simulation week tests the real system, not a toy version.

### 2.4 Execution Agent (intraday loop)

- Runs continuously during active hours: checks for new signals, places/cancels/replaces limit
  orders, manages open positions.
- **Queue position is unobservable in historical data — the backtest's load-bearing
  assumption (new, Phase 2).** Maker fees are $0, so **fill probability, not fee, is the
  binding constraint**, which makes this the most assumption-laden part of the economic
  backtest. Candles give bid/ask and traded OHLC plus volume; trade prints exist only
  post-cutoff; **neither reveals how many contracts rest ahead of ours.** `src/fillsim.py`
  therefore assumes: (a) **trade-through required, not trade-at** — a resting bid at P fills
  only if the market traded strictly below P, since trading *at* P may only have consumed
  the queue ahead; (b) a **10% participation cap** on the period's printed volume; (c) **no
  queue credit** carried across periods. All three bias against the strategy on fill rate —
  but none captures **adverse selection**, which biases *for* it. **Phase 5.5 must validate
  this** against live full-depth captures, reporting realized fill rate and
  fill-price-versus-mid-at-fill. Until then every backtest P&L figure carries this caveat.
- **Simulated mode (Phase 5.5):** instead of sending orders, records what *would* have been
  submitted, using the **real live order book** to determine a realistic fill price and whether the
  order would have filled at all. Simulate against actual depth — never assume a mid-price fill —
  and update a mock cash/position ledger with fees included.
- **Live mode (Phase 6+):** same logic, real orders.
- **Exit logic:** close early if a new forecast run moves `p_model` against the position by more than
  X points, if the edge has been captured and holding only adds fee/resolution risk, or as resolution
  approaches and liquidity thins. Note that forecast skill rises sharply in the final hours before a
  daily high is set, so a stale-forecast position held to resolution is a known failure mode.
- Every order (real or simulated) logged with full context — model estimate, fee calculation, edge
  after fees, mode — for both dashboards and later backtesting.

### 2.5 Reporting/Dashboard Agent — two outputs

**A. Live dashboard.** Updates continuously during the trading day (auto-refresh every 30–60s, or
push if the stack supports it). Shows: open positions with live unrealized P&L; `p_model` vs.
`p_market` per watched contract, **grouped by ladder with the ladder sum displayed** (§2.6), so
candidate edges and incoherence are both visible before a trade fires; today's trades with fees paid;
risk exposure vs. limits; kill-switch state; current NWS↔TWC basis estimate and sample size (§2.7);
and during Phase 5.5 a prominent **"SIMULATION MODE — mock money"** banner so it is never ambiguous
whether the numbers are real. Build as a lightweight local web app (FastAPI/Flask + auto-refreshing
HTML, or Streamlit) reading the same database the agents write to.

**B. End-of-day summary.** Generated once daily: realized + unrealized P&L; **total fees paid, called
out explicitly**; P&L net of fees; capital deployed vs. available; every trade with its triggering
edge, including round trips within the same contract; open positions; **fee efficiency** (% of gross
P&L consumed by fees, today and trailing 30 days — the single most important health metric for this
strategy, front and center, not buried); risk status; model calibration health by lead time; and the
running NWS↔TWC basis distribution.

### 2.6 Ladder Coherence Check (new in v3 — model-independent)

A lightweight process, **separate from forecast-based edge detection and running continuously**, that
does pure arithmetic on the order book. No weather model involved.

Because each event's six buckets are mutually exclusive and exhaustive, their true probabilities sum
to exactly 1. The observed mids do not: the NYC ladder above summed to **0.985**. Some of that gap is
ordinary bid/ask friction, but a ladder that departs meaningfully from 1 is a mispricing detectable
with no forecast skill whatsoever.

Requirements:
- Compute, per ladder per order-book poll: sum of mids, sum of bids, sum of asks.
- **Only the executable sums establish a real opportunity.** A sum-of-asks < 1 means the whole ladder
  can be bought for less than its guaranteed $1 payout; a sum-of-bids > 1 means it can be sold for
  more. The mid sum is a monitoring signal, not a tradeable one.
- Any such opportunity must still clear the §2.3 fee gate — six legs of fees, and the fee is quadratic
  per leg, so the raw gap must be sizeable to survive. Expect most flagged gaps to be unprofitable;
  log them anyway, because the flag rate over time tells you how efficient these books are.
- Depth-check every leg before signalling: a 3¢ gap on a leg with 2 contracts resting is not an
  opportunity.
- Surface on the live dashboard and log to `ladder_coherence` regardless of whether a trade fires.

### 2.7 NWS↔TWC Basis Logger (new in v3 — running now, `scripts/basis_logger.py`)

These contracts settle on **The Weather Company**, not NWS. `weather.com/kalshi` is a client-rendered
Next.js app — a plain fetch returns a ~25KB JS shell with no data and no API key — so there is no
direct programmatic path to the settlement values. The basis is instead inferred from **Kalshi's own
settled outcomes**: the winning bucket bounds the TWC value to a range. Coarse, free, and honest.

This mattered because a 1° disagreement at a bucket boundary flips a contract outright, and bucket
edges are only 2° apart. So the basis does not need to be large to invalidate a Phase 2 backtest
calibrated on NWS.

#### Use the CLI product, not raw observations

**Kalshi's station IDs *are* NWS CLI climatological product IDs.** Their rules text says
"New York City (CLINYC)", and `CLINYC` is the NWS climate report for Central Park, fetchable at
`api.weather.gov/products/types/CLI/locations/NYC`. So the correct NWS comparison value is the CLI
product's official `MAXIMUM`/`MINIMUM` field.

Each location issues a **preliminary** product each afternoon ("VALID TODAY AS OF...") and a **final**
one early the next morning covering the previous day. **Only the final one is valid.** Measured on
NYC 2026-09-20: preliminary said max 67, final said 69 — a 2° gap, one full bucket, from product
choice alone.

Getting this wrong is not a small error. An initial version of the logger took the max over sampled
METAR observations instead, which systematically understates true highs, and produced an apparent
**49.4% bucket-flip rate** that was entirely methodology artifact.

#### Measured result (as of 2026-09-22)

Against final CLI products, over 2026-09-15 → 09-21, all 24 cities, highs and lows:

| metric | value |
|---|---|
| Observations | 334 |
| NWS selects the settled bucket | **334 / 334 = 100.0%** |
| **Bucket-flip rate** | **0.0%** |
| Cities with any flip | 0 of 24 |

**Interpretation: favorable, and a genuine de-risking — but do not over-read it.**

- n=334 spans only **7 distinct days**. Days are the unit of correlation, not rows: all 24 cities on
  one day share a synoptic regime. The effective independent sample is closer to 7 than 334.
- Agreement is measured **at bucket resolution (2° wide)**, which is exactly what settlement depends
  on, but it does not establish exact-degree agreement.
- A calm week is the easy case. Disagreement is likeliest on volatile days — frontal passage, late
  convective cooling, a high set at an odd hour — which is also when edges are largest and positions
  biggest. **The tail matters more than the mean here.**

**Therefore: keep logging daily.** Run `scripts/basis_logger.py` once a day. The CLI products endpoint
retains only ~15 products per location (~7 days), so a missed week is unrecoverable from this source
— which is precisely why this runs from day one rather than being deferred to Phase 2.

Pursuing exact TWC values is now a **lower priority** than it was, but still worth doing opportunistically:
1. A TWC/weather.com API key (their v3 API is commercially licensed; check for a free tier).
2. Headless-browser scrape of `weather.com/kalshi` — fragile, but would sharpen the basis from a
   bucket-level range to an exact daily value.

**Gate:** Phase 2's go/no-go is still evaluated with the measured basis folded in. On current evidence
that fold-in is close to a no-op, but the flip rate must be **re-checked against the accumulated log
at Phase 2 time**, not assumed to still be zero.

---

## 3. Fees — CONFIRMED 2026-09-22

Restating because it is the difference between a working strategy and a fee-bleeding one.
**Both open questions from the v3 draft are now closed.** Implemented in `src/fees.py`.

### Taker fee — confirmed, matches the original spec

```
fee = ceil_to_cent(0.07 × fee_multiplier × contracts × price × (1 − price))
```

The `0.07` coefficient is confirmed against Kalshi's published fee schedule. Quadratic in price, so
it peaks at 50¢ — **1.75¢/contract**, which is the parabola's natural maximum, not a separate cap.

### Maker fee — **$0 for weather.** Confirmed two independent ways

1. **Kalshi's fee schedule** lists no maker fee for "Most markets", which weather falls under. The
   50%-of-taker maker rate applies only to **Combos**.
2. **The API encodes the distinction directly.** `fee_type` is a two-value enum:

   | `fee_type` | weather | Financials | Economics |
   |---|---|---|---|
   | `quadratic` (taker only) | **409 / 409** | 1,038 | 856 |
   | `quadratic_with_maker_fees` | **0** | 34 | 10 |

   The maker-fee variant exists and is in active use (CPI, Fed, GDP, GPU pricing), and **weather is
   0 of 409** on it. This is positive confirmation, not an absent field.

`fee_type` and `fee_multiplier` are still read from `/series` per series and stored per contract.
`fees.assert_no_maker_fee()` runs on every contract-discovery pass and raises if a watchlist series
moves onto the maker-fee schedule, because the execution strategy's core economics depend on it.

### Express the fee bar in probability points, not % of position value

The v1/v2 framing — "~3.5% of cost at 50¢, ~0.7% near 10¢/90¢" — is **misleading and should not be
used for trade decisions.** Percent-of-cost is not symmetric, because the cost basis changes while
the $1 payoff does not:

| price | taker fee / contract | % of cost | **edge needed (points)** |
|---|---|---|---|
| 10¢ | 0.63¢ | 6.30% | **0.63** |
| 50¢ | 1.75¢ | 3.50% | **1.75** |
| 90¢ | 0.63¢ | 0.70% | **0.63** |

In percent-of-cost terms 10¢ looks nine times worse than 90¢. In the unit that actually decides a
trade — **probability points of edge required** — they are identical. Always size the bar in points.
The genuine, symmetric conclusion stands: taker trades near 50¢ carry roughly 2.8× the edge
requirement of trades near the extremes.

### Round-trip cost, the number that gates a trade

100 contracts, entering and exiting at 50¢ (the worst case):

| execution | round-trip fee | min edge to break even |
|---|---|---|
| taker / taker | 350¢ | **3.50 points** |
| maker / taker | 175¢ | **1.75 points** |
| **maker / maker** | **0¢** | **0.00 points** |

Holding to resolution instead of exiting incurs no exit fee — settlement is not a trade.

### Implementation requirement

`fees.trade_fee_cents()` is called before **every** trade decision, real or simulated, and every
calculation is logged alongside the decision it gated (§2.4), because the fee-efficiency metric in
§2.5 is reconstructed from those logs.

---

## 4. Kalshi API Integration

- **Base URL (production):** `https://api.elections.kalshi.com/trade-api/v2`
- **Sandbox:** `https://demo-api.kalshi.co/trade-api/v2` — confirmed reachable and healthy.
- **Public read endpoints work unauthenticated** (`/series`, `/markets`, `/markets/{t}/orderbook`).
  This means **Phases 1–3 need no credentials at all**. Credentials are required from Phase 4.
- Auth for trading: API key + signed requests, credentials in environment variables or a secrets
  manager, never in code or logs. **No credentials currently exist** — this needs a human login.
- Key endpoints: series/market discovery, order book detail (full depth — essential given thin
  books), order placement/cancel/status, positions/balance, fills history.
- **Read fee parameters (`fee_type`, `fee_multiplier`) from `/series` per series** (§3).
- **Confirm settlement source and station from each market's `rules_primary` text at build time** —
  it names both the source agency and the station ID, and it is authoritative per-market in a way the
  generic contract-terms PDF is not.
- Exchange runs ~24/7, with one Thursday 03:00–05:00 UTC maintenance window. Respect documented rate
  limits; build backoff/retry.
- **For Phase 5.5 (simulation):** use **production market-data endpoints read-only**. Phase 0
  resolved v2's open question here — production reads are unauthenticated, so the simulation can
  mirror real books without risking real orders and without depending on sandbox liquidity, which is
  not representative.

---

## 5. Data Sources Reference (corrected)

| Source | Use | Access |
|---|---|---|
| **The Weather Company** (`weather.com/kalshi`) | **The settlement source — the actual resolution target for every contract traded here** | **No direct access (§2.7). Inferred from Kalshi settled outcomes; licensed v3 API or headless scrape would sharpen it.** |
| **NWS CLI products** (`api.weather.gov/products/types/CLI/locations/{LOC}`) | **Official daily max/min — the basis reference. Kalshi's station IDs are these product IDs (`CLINYC` → `NYC`). Use the final morning product, never the preliminary afternoon one.** | Free, public REST. **~7 days retention — log daily or lose it.** |
| NWS/NOAA API (`api.weather.gov`) | Point forecasts and observations — **forecast input, NOT the settlement source and NOT the daily-extreme source** | Free, public REST, User-Agent required |
| Open-Meteo Ensemble API | GFS/ECMWF ensemble members (82 per point), multiple runs/day | Free, no key, confirmed working |
| Historical station climatology (in-house) | Calibrate forecast-to-actual accuracy by lead time, per station | Derived from NWS station history |
| Kalshi Markets API | Contract list, prices, order book, **fee parameters** | Public reads unauthenticated; trading needs auth |

**The first two rows are different things and v1/v2 conflated them.** NWS is what the model reads;
TWC is what the money settles on. §2.7 exists to measure the gap between them.

### Station mapping

All 24 Kalshi station IDs map cleanly to NWS stations with working observations and gridpoint
forecasts; the full map is in `config/watchlist.json`. **Two are worth flagging because the obvious
guess is wrong:**

- **Chicago is `CLIMDW` = Midway (KMDW), not O'Hare.**
- **Houston is `CLIHOU` = Hobby (KHOU), not Bush/IAH.**
- NYC is `CLINYC` = Central Park (KNYC), not LaGuardia or JFK.

Getting any of these wrong is precisely the §9 station-mismatch failure, and it fails silently.

---

## 6. Tech Stack

- **Language:** Python.
- **Scheduling:** APScheduler or similar, triggering on both wall-clock intervals (order book polls)
  and external events (new model run available).
- **Storage:** SQLite to start; move to Postgres if intraday polling across the watchlist outgrows it.
- **Modeling:** scipy/statsmodels for the Tier 1 distributional fit (`scipy.stats.skewnorm` and
  `.cdf()` over bucket edges is the natural primitive); scikit-learn for Tier 2.
- **Live dashboard:** small local web app (FastAPI/Flask + auto-refreshing HTML, or Streamlit) reading
  the shared database.
- **EOD dashboard:** static HTML report regenerated daily.
- **Secrets:** `.env` / secrets manager, gitignored.
- **Logging:** structured JSON lines for every decision, including the fee calculation that gated it,
  tagged `mode: simulation` or `mode: live` so the two are never mixed in analysis.

---

## 7. Data Model

- `contracts` — Kalshi ticker, **ladder/event id**, city, settlement source, settlement station id,
  matched NWS station, **bucket type (`less`/`between`/`greater`) and bucket edges**, open/close/
  resolution times, **`fee_type` and `fee_multiplier` as read from the API**.
- `forecast_snapshots` — timestamped NWS + ensemble pulls per station, append-only. Store **ensemble
  members individually**, not just mean/spread — Tier 2 and any re-fit will need the raw sample.
- `market_prices` — timestamped Kalshi order book snapshots per contract, with depth.
- `model_estimates` — timestamped `p_model`, confidence band, features used, linked to contract and
  ladder.
- `ladder_coherence` — per ladder per poll: sum of bids, mids, asks; flagged opportunity or not;
  whether it survived the fee gate (§2.6).
- `basis_observations` — per station per day: NWS observed max/min, settled bucket, implied TWC range,
  implied basis, and whether NWS would have selected a different bucket (§2.7).
- `trades` — every order (submitted/filled/cancelled/rejected), entry or exit, price, size,
  **fee paid**, **mode**, linked to the model estimate or coherence flag that triggered it.
- `positions` — current and historical, with entry/exit details, net-of-fee P&L, and mode.
- `risk_events` — every limit hit, kill-switch trigger, or blocked trade, with reason.

---

## 8. Initial Watchlist — highs only (changed from v2)

Phase 0 liquidity measurement, point-in-time 24h volume across all 48 daily series (~1,355,000
contracts total):

| tier | series | 24h vol | median spread |
|---|---|---|---|
| Top 3 highs (LAX, MIA, NY) | 3 | 769k (57%) | 1¢ |
| Highs, top 21 cities | 21 | ~1,280k | 1–2¢ |
| **All lows** | 24 | ~72k (5%) | **3–11¢** |
| Tail (SAN, SDF, TTN, EWR) | 8 | <4k each | 8–11¢ |

**Lows are excluded from the initial watchlist.** They carry ~5% of the volume at 7–11¢ spreads. An
8¢ spread exceeds any plausible modeled edge once fees are added, so trading them would dilute focus
and capital across a structurally worse segment before modeling even begins. Revisit only if
intraday logging shows their spreads compress materially during active hours.

**Phase 1–5 watchlist — 12 high-temperature series.** All 12 are collected and scored,
but **LAX and NYC are hard-gated out of sizing** (§2.3) pending a coastal correction, so
10 are tradeable. That removes ~43% of watchlist volume, LAX alone being ~32%.

**Phase 1–5 watchlist — 12 high-temperature series:**

| series | city | Kalshi station | NWS station | 24h vol |
|---|---|---|---|---|
| `KXHIGHLAX` | Los Angeles | CLILAX | KLAX | 433,192 |
| `KXHIGHMIA` | Miami | CLIMIA | KMIA | 185,926 |
| `KXHIGHNY` | New York City | CLINYC | KNYC (Central Park) | 150,159 |
| `KXHIGHAUS` | Austin | CLIAUS | KAUS | 60,070 |
| `KXHIGHTATL` | Atlanta | CLIATL | KATL | 58,554 |
| `KXHIGHCHI` | Chicago | CLIMDW | **KMDW (Midway)** | 49,454 |
| `KXHIGHTDAL` | Dallas | CLIDFW | KDFW | 46,074 |
| `KXHIGHPHIL` | Philadelphia | CLIPHL | KPHL | 33,667 |
| `KXHIGHTHOU` | Houston | CLIHOU | **KHOU (Hobby)** | 32,967 |
| `KXHIGHTOKC` | Oklahoma City | CLIOKC | KOKC | 26,597 |
| `KXHIGHDEN` | Denver | CLIDEN | KDEN | 23,397 |
| `KXHIGHTDC` | Washington DC | CLIDCA | KDCA | 20,334 |

That is 2 open events each (today + tomorrow) × 6 buckets = **~144 live markets** to track.

**Note:** the §2.7 basis logger should cover **all 24 stations**, not just these 12. It costs almost
nothing extra, it is off the trading path, and a wider basis dataset is more useful if the watchlist
later expands.

---

## 9. Phased Build Plan

**Phase 0 — Access & discovery — ✅ COMPLETE.**
Findings in `docs/phase0-discovery.md`; contract universe in `config/watchlist.json`. Confirmed: 48
series / 24 cities, TWC settlement, 6-bucket ladders, liquidity tiers, station mapping, sandbox
reachable, public reads unauthenticated. **Outstanding:** Kalshi account credentials (needed by
Phase 4), and fee coefficient + maker rate confirmation (needed by Phase 2).

**Phase 0.5 — Basis logging — START NOW, runs continuously.**
Stand up §2.7 immediately and let it accumulate while Phase 1 is built. Pursue TWC API access in
parallel. This phase never really "ends" — it keeps running through every later phase.

**Phase 1 — Data pipeline.**
NWS + ensemble ingestion for the §8 watchlist, Kalshi order-book polling, append-only storage.
Station-matching correctness is the gate here — it is the easiest place to build a model that is
confidently wrong, and the Midway/Hobby/Central Park cases are where it will happen.

**Phase 2 — Backtest the edge, fee-inclusive — the go/no-go.**
Test whether Tier 1 would have identified profitable trades **after the real fee formula** (§3,
confirmed coefficients) **and with the measured NWS↔TWC basis folded in** (§2.7). A strategy that
looks good gross and bad net of fees is not a strategy; one calibrated against the wrong settlement
source is not even a measurement. Also backtest the §2.6 coherence check independently — it has a
different risk profile and may survive fees where the forecast edge does not, or vice versa.
**Validation methodology is specified in §9.5 and is not optional** — it is the difference between a
go/no-go and a curve fit. **Score by lead-time bucket, with 0–12h as an explicit control** (§9.5):
the short-lead window is known-unwinnable, so performance there measures leakage and model error,
not edge. The go/no-go rests on the **24–48h** bucket alone.

**Phase 3 — Forecasting Agent, paper-trading mode.**
Run live against open contracts, log `p_model` vs. `p_market` and simulated fee-inclusive P&L, no
orders. Needs no credentials.

**Phase 4 — Risk & Execution Agents, sandbox.**
Fee-aware sizing, ladder-aware exposure bucketing, intraday enter/exit loop, kill switch. Requires
credentials.

**Phase 5 — Dashboards.**
Live dashboard and EOD report against Phase 3–4 data, fee-efficiency front and centre.

**Phase 5.5 — One-week live simulation (mock money) — mandatory gate.**
Run the full system against **real, live Kalshi market data** for a full week, mock money only.
Execution simulates fills against the **actual live order book**, not assumed mid-price fills. At
week's end review: net-of-fee simulated P&L, fee efficiency, how often signals fired and whether they
made sense in hindsight, coherence-check flag rate and profitability, measured basis to date, and any
station-matching or data-lag issues that only appear under live conditions. **Do not proceed to
Phase 6 unless the week is genuinely encouraging net of fees** — a breakeven or losing week is a
signal to revisit the model, not a formality to clear.

**Phase 6 — Small live capital.**
Production with an explicitly capped bankroll. Keep simulation running in parallel to catch
real-world slippage against model assumptions. **The 0–12h lead window stays closed to live trading**
(§2.3) until the 24–48h edge has been proven separately in Phase 2 and held up through Phase 5.5.
**Maker-only by default** (§3): resting orders are free, so Phase 6 should observe a fee-efficiency
figure near zero. A materially non-zero one means the system is crossing the spread more than
intended, and is the first thing to investigate.

**Phase 7 — Iterate.**
Expand city coverage, reconsider lows if their spreads have compressed, move to Tier 2, tune
thresholds — only once a real live track record exists.

---

## 9.5 Model Validation — train/validation/test discipline (new in v3)

Phase 2 is the go/no-go for the whole premise, so how the model is split and scored decides whether
that verdict means anything. Weather data is unusually easy to leak across a split, and the failure is
silent: it produces a backtest that looks excellent and a live system that loses money.

### Splitting

- **Split chronologically, never randomly.** Daily highs are strongly autocorrelated day to day. A
  random row split puts tomorrow in train and today in test, and the model scores well by having
  effectively seen the answer.
- **Split by date, not by row.** All 24 cities on a given day share a synoptic weather regime — this
  is the same correlation that makes the §2.7 sample effectively 7 days rather than 334. A row-level
  split puts LAX and SAN from the same afternoon on opposite sides of the boundary, which is
  near-duplicate information. **The date is the atomic unit.**
- **Embargo the boundary.** Leave a **3–7 day gap** between train and test. Weather systems span
  several days, so the days immediately after the cut still carry information from before it.
- **Walk-forward, not one split.** Use rolling-origin evaluation: train on window *n*, test on window
  *n+1*, advance, repeat. This matches how the system will actually run (always predicting forward
  from a fixed past) and it yields several test folds instead of one, which matters because the
  absolute amount of data here is small.
- **Hold out a final test set that is looked at exactly once**, at the go/no-go. All threshold
  tuning happens on validation folds. Every knob — minimum edge, Kelly fraction, exit triggers,
  maker/taker preference, spread gate — is a hyperparameter, and tuning any of them against the final
  test set converts the go/no-go into a fit.
- **Be explicit about seasonality.** A model trained on summer and tested on autumn is answering a
  different question than one trained and tested within a season. With limited history the backtest
  may only cover one regime; if so, **state that as a bound on the conclusion** rather than letting it
  pass silently. Forecast error structure in July convection is not forecast error structure in
  January advection.

### Scoring

Two scores, and they answer different questions. Report both — neither alone is sufficient.

**1. Statistical: is `p_model` calibrated?** For a trading model, calibration matters more than
accuracy — a model that says 70% and is right 70% of the time is tradeable; one that is right 85% of
the time but whose stated probabilities are meaningless is not.

- **Brier score, decomposed into reliability + resolution + uncertainty.** Reliability is the term
  that gates trading; resolution says whether the model is adding information over climatology.
- **Log loss**, which punishes confident wrongness — the failure mode that actually blows up a
  position.
- **Reliability diagrams, bucketed by lead time.** A model well-calibrated at 6h and badly calibrated
  at 48h is still usable; it just means the agent may only trade inside 6h.
- **Score the ladder jointly** — evaluate whether the predicted distribution assigned good probability
  to the realized bucket (ranked probability score is the right fit for ordered buckets), not six
  independent binary scores.
- **Bucket every score by lead time, and treat 0–12h as a control, not evidence.** Phase 1 measured
  the market at 12/12 correct buckets at 5–8h lead against our best input's 4/12, because the daily
  high has already occurred by then. Strong model performance in that window means the model is
  reading observations (fine, but not edge); strong *apparent edge* there means leakage or a broken
  estimate. **The go/no-go is decided on the 24–48h bucket.** Report 0–12h and 12–24h alongside it
  for diagnosis only.
- **Baseline against climatology and against the market.** Beating climatology proves the model works;
  beating `p_market` is the only thing that proves there is an edge. A model can be well-calibrated and
  have no edge because the market is equally well-calibrated.

**2. Economic: does it make money net of fees?** This is the one that decides Phase 2.

- Simulate fills against **historical order-book depth**, not mid prices.
- Apply the **real per-series fee formula** (§3) to every entry and exit.
- Report net-of-fee P&L, **fee efficiency** (% of gross consumed by fees), hit rate, and worst
  drawdown, **per test fold** — not pooled, so fold-to-fold variance is visible.

A model can pass (1) and fail (2). Passing (1) and failing (2) means the edge is real but smaller than
the cost of harvesting it, which is a no-go, not a "tune it harder."

### Guarding against fooling yourself

- **Pre-register the decision rule before looking at test results.** Write down the threshold for "go"
  — net-of-fee return, minimum number of profitable folds, maximum drawdown — and commit it to the
  repo *before* the final evaluation runs.
- **Count the comparisons.** 12 cities × several edge thresholds × two model tiers × multiple exit
  rules is a large search space, and some configuration will look profitable by chance. Either correct
  for it or prefer a single pre-committed configuration.
- **Per-city results are thin.** Do not conclude "the model works in Denver" from one city's slice; city
  count multiplies the comparison problem and each city's sample is small.
- **The §2.6 coherence check gets its own split and its own scoring.** It has no trained parameters, so
  the leakage concern is different, but the multiple-comparisons and fee-survival questions are identical.

---

## 10. Key Risks to Design Around

- **Settlement-source mismatch (NWS vs. TWC) — measured, currently benign, still monitored.** The
  system forecasts one thing and settles on another. Measured at **0 flips in 334 observations** over
  7 days (§2.7), which is a real de-risking. But the sample is effectively 7 independent days and
  covers a calm week; disagreement is likeliest on volatile days, which are exactly the days with the
  largest edges and biggest positions. Keep the daily logger running and re-check at Phase 2.
- **Measuring the basis against the wrong NWS product — a live, already-realized trap.** Using raw
  METAR observations instead of the final CLI product produced a spurious 49.4% flip rate. Anything
  that reads "NWS daily max" must mean the **final** CLI product, never the preliminary afternoon one
  and never a max over sampled observations (§2.7).
- **Leakage in the Phase 2 backtest.** Weather autocorrelates across days and across cities within a
  day. A random or row-level split produces an excellent backtest and a losing live system. §9.5 is
  the mitigation and it is not optional.
- **Fee drag from over-trading:** still the most likely operational failure mode. The per-contract
  daily round-trip cap (§2.3) and the fee-efficiency metric (§2.5) both exist to catch it early.
- **Unverified fee coefficients:** building Phase 2 on the assumed 0.07 / 25%-maker figures means the
  go/no-go decision rests on numbers nobody confirmed (§3).
- **Station mismatch within NWS:** Midway-not-O'Hare, Hobby-not-IAH, Central-Park-not-LGA. Fails
  silently and looks like model error.
- **Ladder correlation treated as diversification:** six buckets on one event are one bet. Sizing them
  as six independent positions would concentrate risk while appearing diversified (§2.3).
- **Correlated weather risk across cities:** a single front moves several cities together; ten cities
  are not ten independent bets.
- **Thin liquidity:** always limit orders, always depth-check before sizing. Also bounds how realistic
  Phase 5.5's simulated fills can be.
- **Forecast model risk near resolution:** skill improves sharply in the final hours before a daily
  high is set; exit logic must account for this rather than holding a stale-forecast position blindly.
- **Simulation-to-live gap:** a careful mock week cannot fully capture real execution risk — real
  fills move the book in ways a snapshot simulation won't reflect. Treat Phase 5.5 as a strong signal,
  not a guarantee, and keep Phase 6 capital small regardless of how good it looked.

---

## 11. Definition of Done (MVP)

- Data Collector pulling NWS + ensemble data for the §8 watchlist, correctly station-matched, with
  the NWS-vs-TWC distinction explicit in code and schema.
- **A running NWS↔TWC basis dataset with enough history to state the bucket-flip rate**, sourced from
  final CLI products, and Phase 2's go/no-go evaluated with it folded in. *(Logger shipped and
  running: `scripts/basis_logger.py`, 334 observations, 0 flips as of 2026-09-22.)*
- Tier 1 Forecasting Agent emitting a **continuous distribution integrated over the 6-bucket ladder**,
  probabilities summing to 1 by construction and asserted in code, calibrated in backtest.
- **Phase 2 validated per §9.5**: date-level chronological splits with an embargo, walk-forward folds,
  a once-only final test set, a pre-registered decision rule, and both calibration and net-of-fee
  economic scores reported per fold.
- Ladder coherence check running continuously, logging every flag and whether it survived the fee gate.
- Risk & Sizing Agent enforcing fee-aware filtering with **API-sourced per-series fee parameters**,
  ladder-aware exposure bucketing, all hard limits in code, mode-aware, with a working kill switch.
- Execution Agent running the intraday loop correctly in sandbox, with realistic simulated fills
  against live order-book depth.
- Live dashboard showing real-time positions, per-ladder edges and sums, trades, risk status, current
  basis estimate — clearly labeled by mode.
- Daily EOD report with fee efficiency, P&L gross and net of fees, positions, trades, risk status.
- A completed, reviewed one-week mock-money simulation, documented, before any real capital.
- Full audit log (forecast → model → fee check → decision → order) for every trade, tagged by mode.
