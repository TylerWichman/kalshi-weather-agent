# Kalshi Weather Day-Trading Agent — Build Spec

## 0. Read this first

This supersedes the earlier FDA/clinical-trial version of this project. New direction: **Kalshi's daily temperature high/low contracts** (e.g., "Will the high temp in NYC be above/below/between X°F today?"), traded actively throughout the day — not a buy-and-hold-to-resolution strategy, but a system that enters and exits positions multiple times as new forecast data and market prices move, closer to genuine day trading.

Why this niche, and why it's a better fit than what we looked at before:
- **Breadth:** dozens of cities × daily high/low contracts = many simultaneous markets to scan for mispricing, so there's usually *something* tradeable on any given day (the "moments" problem that killed the FDA/day-trading combo doesn't apply here).
- **Real forecast data most traders won't fully use:** NOAA/NWS and global ensemble models (GFS, ECMWF) update every 6 hours with genuine new information; a system that ingests and interprets these faster/better than the crowd has a real informational edge over casual retail traders.
- **Contracts resolve daily**, so there's a constant stream of fresh markets, unlike sparse and irregular FDA catalyst events.
- **Fees are a first-class design constraint, not an afterthought** (see §3) — this is the main way this strategy fails if built carelessly.

---

## 1. Objective

Build an automated system that:
1. Tracks all open Kalshi daily high/low temperature contracts across a defined set of cities.
2. Continuously (not just once/day) compares its own weather-model-based probability estimate to Kalshi's live market price.
3. Enters and exits positions intraday as new forecast model runs land and as market prices move — genuine day trading, not just "buy once and wait for resolution."
4. Filters every candidate trade through a **fee-aware profitability check** before acting — a trade only happens if the expected edge exceeds the real round-trip cost of trading it.
5. Manages risk automatically within hard limits (see §5).
6. Produces one end-of-day dashboard summarizing the day's activity — the only thing the user needs to check.

Non-goal: guaranteed daily profit. Expect variance day to day; the goal is positive expected value over time, with fees and slippage genuinely accounted for in every decision, not just in a spreadsheet after the fact.

---

## 2. System Architecture

Same five-agent shape as before, but the Forecasting and Execution agents run on a much tighter, intraday loop instead of a once-daily cycle.

```
┌─────────────────┐   ┌──────────────────┐   ┌───────────────────┐
│  1. Data         │──▶│  2. Forecasting   │──▶│  3. Risk & Sizing  │
│  Collector Agent │   │  Agent            │   │  Agent (fee-aware) │
│  (runs ~hourly,  │   │  (re-scores on    │   │                    │
│  triggers on new │   │  every new model  │   │                    │
│  model runs)     │   │  run or price move)│   │                    │
└─────────────────┘   └──────────────────┘   └─────────┬──────────┘
                                                          │
                                                          ▼
┌─────────────────┐   ┌──────────────────┐   ┌───────────────────┐
│  5. Reporting/   │◀──│  4. Execution     │◀──│  (trade decision) │
│  Dashboard Agent │   │  Agent (intraday  │   │                    │
│  (EOD only)      │   │  enter/exit loop) │   │                    │
└─────────────────┘   └──────────────────┘   └───────────────────┘
```

### 2.1 Data Collector Agent
- Pulls the live list of open Kalshi daily high/low temperature contracts (filtered by weather category/series ticker) across your city watchlist.
- For each city/contract, pulls:
  - **NWS/NOAA official forecast** for the relevant station (this is also typically Kalshi's settlement source — confirm exact resolution station per contract's rules, since settlement station and forecast station must match or your edge is measuring the wrong thing).
  - **Ensemble model data** (GFS, ECMWF via a provider like Open-Meteo's free API, or NOAA's NOMADS) — multiple forecast runs per day (GFS updates every 6 hours), giving a spread/uncertainty range, not just a single number.
  - **Live Kalshi order book** for each contract (bid/ask/depth) — critical, since thin contracts mean your fill price can differ meaningfully from the quoted mid.
  - **Historical station climatology** (how often does this station's actual high land within X° of the morning forecast, by lead time) — used to calibrate how much to trust the forecast at a given point in the day.
- Runs on a schedule tied to real information events, not just wall-clock time: trigger a refresh on each new GFS/ECMWF run (every ~6 hours) and poll Kalshi order books more frequently (e.g., every 5-15 minutes) during active trading hours.
- Append-only storage, timestamped, same as before — needed to reconstruct "what was known when" for backtesting and auditing.

### 2.2 Forecasting Agent
- For each open contract, produce `p_model`: probability the temperature lands above/below/between the contract's threshold, with a confidence band derived from ensemble spread and lead-time-calibrated historical accuracy (a forecast made at 6am for today's high is more reliable than one made 5 days out).
- **Tier 1 (ship first):** blend the NWS point forecast with ensemble spread using a simple statistical distribution (e.g., treat the ensemble members as a sample, fit a normal/skew-normal around them, compute P(threshold) directly) plus a calibration adjustment learned from historical station accuracy at each lead time.
- **Tier 2 (after backtesting Tier 1):** a proper trained model (gradient boosting or similar) using ensemble spread, day-of-year seasonality, recent station bias, and time-to-resolution as features, calibrated against realized outcomes.
- Re-run `p_model` for a contract whenever new forecast data lands (new model run) **or** whenever the Kalshi price moves meaningfully — this is what makes the system trade intraday rather than once.
- Output per contract per update: `{p_model, confidence_band, p_market, edge = p_model - p_market, timestamp, lead_time_hours}`.

### 2.3 Risk & Sizing Agent (fee-aware — this is the core design change)
**Every candidate trade must clear a fee-aware profitability bar before sizing, not just an edge threshold.**

Kalshi's fee formula: `fee = round_up(0.07 × contracts × price × (1 − price))` for a taker order, and ~25% of that for a maker (resting limit) order. This peaks at price = 50¢ (~1.75¢/contract, ~3.5% of cost) and shrinks toward the extremes (~0.63¢/contract, ~0.7% of cost near 10¢/90¢).

Design requirements:
- **Round-trip cost estimator:** before evaluating any trade, compute the expected fee cost of entering *and* later exiting (or holding to resolution, whichever the strategy calls for) at the current price level, using the actual formula above — not a flat assumed percentage.
- **Minimum-edge threshold, computed dynamically per trade, not a fixed number:** a trade is only eligible if `edge (in probability terms) × position size > estimated round-trip fee + a required minimum profit margin`. Near 50¢, this bar is much higher than near 10¢/90¢ — the agent should naturally prefer contracts priced away from the expensive middle, all else equal.
- **Prefer maker orders where the model's edge and market pace allow it** (resting limit orders cost ~¼ of taker fees) — but never let a maker-only strategy miss a genuinely large, fast-moving edge; make this a configurable tradeoff, not a hard rule.
- **Position sizing:** fractional-Kelly (e.g., 25% of full Kelly) on the *net-of-fees* edge, not the raw model edge.
- **Hard limits (all enforced in code):**
  - Max % of capital in any single contract.
  - Max % of capital in any single city/region at once (weather across nearby cities is correlated — a single storm system can move several contracts together, so this isn't truly independent risk).
  - Max number of open positions at once.
  - Max number of round trips per contract per day (prevents fee bleed from over-trading a single thin market).
  - Daily loss limit — halts new trading for the day, requires manual review to resume.
  - Max slippage tolerance per order — limit orders only, reject if the book is too thin to fill near fair value.
- **Kill switch:** immediate, trivial to trigger, flattens or freezes positions on command. Surfaced in every EOD report.

### 2.4 Execution Agent (intraday loop)
- Runs continuously during active trading hours (not just once/day): checks for new trade signals from the Forecasting/Risk agents, places/cancels/replaces limit orders, manages open positions.
- **Exit logic is as important as entry logic here** — define rules for when to close a position early rather than hold to resolution: e.g., if a new forecast model run moves `p_model` against the position by more than X points, if the edge has been captured (market price has converged to `p_model`) and holding further only adds fee/resolution risk for no extra expected gain, or as the contract's close/resolution time approaches and liquidity thins out.
- Every order (submitted/filled/cancelled/rejected) logged with the full context that triggered it — model estimate, fee calculation, edge after fees — for both the dashboard and later backtesting.

### 2.5 Reporting/Dashboard Agent
One EOD artifact, generated daily:
- **Summary:** realized + unrealized P&L, total fees paid (call this out explicitly — it's easy to lose track of), P&L net of fees, capital deployed vs. available.
- **Trades today:** every entry/exit, price, size, fee paid per trade, and the edge that triggered it — including round trips within the same contract if the system traded it multiple times in one day.
- **Open positions:** current holdings, entry price, current market price, `p_model` vs. `p_market`, unrealized P&L, hours to resolution.
- **Fee efficiency:** what % of gross P&L was consumed by fees today and over the trailing 30 days — this is the single most important health metric for a fee-sensitive day-trading strategy and should be front and center, not buried.
- **Risk status:** exposure vs. limits, kill-switch state, any halted-trading events and why.
- **Model health:** rolling calibration check — are `p_model` estimates tracking realized station outcomes over time, by lead time?

---

## 3. Fees — Design This In From the Start

Restating because it's the difference between a working strategy and a fee-bleeding one:

- Fee = `round_up(0.07 × contracts × price × (1 − price))` per taker order; ~25% of that for maker fills.
- **Worst case:** trading repeatedly near 50¢ as a taker. A single round trip there costs ~3.5% of position value in fees alone — your model edge has to clear that just to break even, before any profit.
- **Best case:** trading near the extremes (10¢/90¢) and/or as a maker. Costs drop toward ~0.5-1% round trip.
- **Practical implication for the Risk & Sizing Agent:** build a live fee-cost calculator as a first-class function, called before every trade decision, not a static assumption baked into a backtest once and forgotten.

---

## 4. Kalshi API Integration

- Auth: API key + signed requests, credentials in environment variables/secrets manager, never in code or logs.
- Build and test against Kalshi's sandbox environment first.
- Key endpoints: market/series discovery (weather category, filtered to your city watchlist), order book detail (bid/ask/depth — essential given thin books), order placement/cancel/status, positions/balance, fills history.
- Confirm the exact settlement station and rules text for each contract at build time — Kalshi's weather contracts specify a particular official station (e.g., a specific NWS/airport station per city); your forecast data must be pulled for that *exact* station, not just "the city generally," or your model is scoring the wrong thing.
- Respect documented rate limits; build in backoff/retry logic.

---

## 5. Data Sources Reference

| Source | Use | Access |
|---|---|---|
| NWS/NOAA API (api.weather.gov) | Official point forecasts, matches Kalshi's likely settlement source | Free, public REST API |
| Open-Meteo or NOAA NOMADS | GFS/ECMWF ensemble model data, multiple runs/day | Free/public |
| Historical station climatology (build in-house) | Calibrate forecast-to-actual accuracy by lead time, per station | Derived from historical NWS station data |
| Kalshi Markets API | Live contract list, prices, order book | Kalshi developer API (auth required) |

---

## 6. Tech Stack (suggested)

- **Language:** Python.
- **Scheduling:** a proper scheduler (APScheduler or similar) that can trigger on both wall-clock intervals (order book polling) and external events (new model run available) — this needs to support the intraday loop, not just a daily cron job.
- **Storage:** SQLite to start; move to Postgres if data volume/frequency grows past what SQLite handles comfortably (likely, given intraday polling across many contracts).
- **Modeling:** scipy/statsmodels for the Tier 1 distributional model; scikit-learn for Tier 2.
- **Dashboard:** static HTML report regenerated daily — simplest and most reliable for "I just check one page at end of day."
- **Secrets:** `.env`/secrets manager, gitignored.
- **Logging:** structured (JSON lines) for every decision, including the fee calculation that gated it — needed for debugging *and* for the fee-efficiency metric in the dashboard.

---

## 7. Data Model (minimum tables)

- `contracts` — Kalshi ticker, city, settlement station, threshold, open/close/resolution times.
- `forecast_snapshots` — timestamped NWS + ensemble pulls per contract, append-only.
- `market_prices` — timestamped Kalshi order book snapshots per contract.
- `model_estimates` — timestamped `p_model`, confidence band, features used, linked to contract.
- `trades` — every order (submitted/filled/cancelled), entry or exit, price, size, **fee paid**, linked to the model estimate that triggered it.
- `positions` — current and historical, with entry/exit details and net-of-fee P&L.
- `risk_events` — every limit hit, kill-switch trigger, or blocked trade, with reason.

---

## 8. Phased Build Plan

**Phase 0 — Access & discovery**
- Kalshi sandbox credentials. Confirm current weather contract list, exact settlement stations, and city coverage.

**Phase 1 — Data pipeline**
- NWS + ensemble ingestion for a handful of watchlist cities. Get station-matching right (§4) before anything else — this is the single easiest place to build a model that's confidently wrong.

**Phase 2 — Backtest the edge, fee-inclusive**
- Using historical forecast data and historical Kalshi price data (or, if Kalshi history is too short/thin, historical forecast-vs-actual accuracy as a proxy), test whether the Tier 1 model would have identified profitable trades **after the real fee formula**, not before it. This is the step that validates or kills the whole premise — a strategy that looks good gross and bad net of fees is not a strategy.

**Phase 3 — Forecasting Agent, paper-trading mode**
- Run live against open Kalshi contracts, log `p_model` vs. `p_market` and simulated fee-inclusive P&L, no real orders yet.

**Phase 4 — Risk & Execution Agents, sandbox**
- Build the fee-aware sizing logic, intraday enter/exit loop, kill switch. Test against sandbox.

**Phase 5 — Dashboard**
- Build the EOD report against Phase 3-4 data, with fee-efficiency front and center.

**Phase 6 — Small live capital**
- Move to production with an explicitly capped bankroll. Run paper-trading in parallel to catch real-world slippage vs. model assumptions.

**Phase 7 — Iterate**
- Expand city coverage, move to Tier 2 model, tune thresholds — only once a real track record exists.

---

## 9. Key Risks to Design Around

- **Fee drag from over-trading:** the single most likely failure mode for a day-trading version of this. The per-contract daily round-trip cap (§2.3) and the fee-efficiency dashboard metric (§2.5) both exist specifically to catch this early.
- **Station mismatch:** if your forecast data isn't for the exact station Kalshi settles against, your "edge" is an illusion.
- **Correlated weather risk:** nearby cities/regions move together during a single weather system — the category/region exposure cap (§2.3) exists for this; don't treat 10 cities as 10 independent bets if a cold front is moving through all of them.
- **Thin liquidity:** smaller-city contracts may have very few resting orders — always limit orders, always check depth before sizing.
- **Forecast model risk near resolution:** accuracy improves a lot in the final hours before a daily high is set; the Execution Agent's exit logic should account for this rather than holding a stale-forecast-based position blindly to resolution.

---

## 10. Definition of Done (MVP)

- Data Collector Agent pulling NWS + ensemble data for the full city watchlist, correctly station-matched to each Kalshi contract's settlement source.
- Tier 1 Forecasting Agent producing calibrated (in backtest) probability estimates, re-scoring on new model runs.
- Risk & Sizing Agent enforcing fee-aware trade filtering and all hard limits in code, with a working kill switch.
- Execution Agent running the intraday enter/exit loop correctly in sandbox, validated against a paper-trading track record.
- Daily report with fee-efficiency, P&L (gross and net of fees), positions, trades, and risk status.
- Full audit log (forecast → model → fee check → decision → order) for every trade.
