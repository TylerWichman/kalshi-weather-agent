# Phase 0 — Access & Discovery: Findings

Snapshot taken 2026-09-22 ~21:36 UTC against Kalshi's production public API.
Reproduce with `scripts/discover_kalshi_weather.py`. Machine-readable output: `config/watchlist.json`.

## 1. The spec's settlement-source assumption is wrong

The spec (§2.1, §4, §5) assumes **NWS/NOAA is "typically Kalshi's settlement source."** It is not,
for the contracts this strategy targets.

Every one of the 48 daily high/low temperature series resolves against **The Weather Company**
(weather.com/kalshi). From the live market rules text:

> "If the maximum temperature recorded at New York City (CLINYC) for Sep 23, 2026, is greater than
> 72° fahrenheit **according to The Weather Company**, then the market resolves to Yes."

> "While checking a source like AccuWeather or Google Weather may help guide your decision, the
> official and final value used to determine this market is the maximum/minimum temperature as
> reported by the Weather Company."

Across all 409 Climate-and-Weather series, settlement sources split roughly: The Weather Company 136,
NWS ~60 (various regional offices), NOAA 29, NWS Climatological Report ~20, others long-tail. The
NWS-settled temperature series that do exist (`HIGHNY`, `HIGHCHI`, `HIGHAUS`, `HIGHMIA`, `KXHIGHHOU`,
`KXDENHIGH`) are **legacy — all have zero open markets.** They are the delisted predecessors of the
KX* series. So there is no NWS-settled daily temp market to trade instead.

This is §9's "station mismatch" risk, and it is live right now, one layer up from where the spec
expected it: not wrong station, wrong *agency*. Consequences in §5 below.

## 2. Contract universe (confirmed)

48 active daily series across **24 cities**, each with a high and a low series:

| | |
|---|---|
| Cities | NYC, LA, Chicago, Miami, Austin, Atlanta, Dallas, Philadelphia, Houston, Oklahoma City, Denver, Washington DC, Las Vegas, Boston, Phoenix, San Francisco, Seattle, Minneapolis, New Orleans, San Antonio, San Diego, Newark, Trenton, Louisville |
| Series per city | 2 (`KXHIGHT*`/`KXHIGH*` and `KXLOWT*`) |
| Events open at once | 2 per series (today + tomorrow) |
| Markets per event | 6 |
| Total live markets | ~576 |

Ticker naming is inconsistent (`KXHIGHNY`, `KXHIGHTATL`, `KXHIGHAUS`, `KXHIGHTHOU`) — do not derive
tickers from city codes, read them from the series endpoint.

## 3. Market structure — better than the spec assumed

Each event is a **mutually exclusive, exhaustive ladder**, not independent binaries. Example,
`KXHIGHNY-26SEP23`:

| ticker | type | range | bid | ask | 24h vol |
|---|---|---|---|---|---|
| `-T65` | less | ≤64° | 0.06 | 0.07 | 621 |
| `-B65.5` | between | 65–66° | 0.26 | 0.28 | 255 |
| `-B67.5` | between | 67–68° | 0.47 | 0.48 | 972 |
| `-B69.5` | between | 69–70° | 0.13 | 0.14 | 584 |
| `-B71.5` | between | 71–72° | 0.02 | 0.03 | 181 |
| `-T72` | greater | ≥73° | 0.01 | 0.02 | 898 |

Two consequences the spec doesn't account for:

- **The Tier 1 model should produce a full predictive distribution over the ladder, not six
  independent P(threshold) estimates.** Fitting a distribution to the ensemble members and
  integrating over each bucket is the natural fit, and it's the same amount of work.
- **The ladder must sum to 1, which is a free consistency signal.** The mids above summed to 0.985.
  When a ladder sums meaningfully off 1, that is a mispricing detectable without any weather model at
  all. Worth adding as a signal source in Phase 2.

Buckets are 2° wide; tails are open-ended. Prices are 1¢ ticks, `price_level_structure: linear_cent`.

## 4. Liquidity — concentrated, and high/low is a 10:1 split

Point-in-time 24h volume, all 48 series: **~1,355,000 contracts.** But it is top-heavy:

| tier | series | 24h vol | median spread |
|---|---|---|---|
| Top 3 (LAX, MIA, NY highs) | 3 | 769k (57%) | 1¢ |
| Highs, top 21 cities | 21 | ~1,280k | 1–2¢ |
| All lows | 24 | ~72k (5%) | 3–11¢ |
| Tail (SAN, SDF, TTN, EWR) | 8 | <4k each | 8–11¢ |

**Highs are ~18× the volume of lows.** The spec treats high and low contracts interchangeably; they
are not. Low-temperature contracts have spreads of 7–11¢, which against the fee math in spec §3 is
fatal — an 8¢ spread near mid-range pricing swamps any plausible model edge. Recommend the initial
watchlist be **highs only, top ~12 cities**, with lows excluded until there's evidence their spreads
compress during active hours.

Order book depth is real on the liquid names (`KXHIGHNY-26SEP23-T72` showed 10 price levels on the
no side, 116–629 contracts per level).

## 5. Open problem: we cannot currently read the settlement source

weather.com/kalshi is a client-rendered Next.js app; a plain fetch returns a 25KB JS shell with no
data and no API key in the markup. So right now there is **no programmatic path to the values these
contracts actually settle on.**

This blocks more than it first appears:

- **Phase 2 backtest** — calibrating a model against NWS observations measures the wrong target if
  TWC and NWS disagree even occasionally. A 1° disagreement at a bucket boundary flips a contract.
- **§2.5 model-health calibration** — same problem, ongoing.
- **§2.1 climatology** — "how often does the actual land within X° of forecast" needs the *settled*
  actual, not the NWS actual.

The size of the NWS-vs-TWC basis is the most important unknown going into Phase 1. Options, in rough
order of preference:

1. Get a TWC/weather.com API key (their v3 API is commercially licensed; there may be a free tier).
2. Headless-browser scrape of weather.com/kalshi daily — fragile, but cheap and enough to *measure*
   the basis even if not to depend on it.
3. Log both NWS observations and Kalshi's settled outcome per contract from day one, and back the
   basis out empirically. Slowest (needs ~1–2 months before it says anything) but zero dependencies.

Worth doing (3) immediately regardless of which of the others lands, and attempting (1) in parallel.

### UPDATE (2026-09-22, same day): measured — and it is benign

Option (3) was built and run the same day (`scripts/basis_logger.py`). Two corrections to the above:

**The right NWS source is the CLI climatological product, not observations.** Kalshi's station IDs
*are* CLI product IDs — `CLINYC` is the NWS climate report for Central Park, served at
`api.weather.gov/products/types/CLI/locations/NYC`. Each location issues a preliminary product each
afternoon and a **final** one the next morning; only the final one is valid. On NYC 2026-09-20 the
preliminary said max 67 and the final said 69 — a 2° gap, one full bucket, from product choice alone.

**This made the basis measurable without any TWC access, and it is zero.** Against final CLI products
over 2026-09-15 → 09-21, all 24 cities, highs and lows: **334 observations, 0 bucket flips, 100%
agreement, no city with any flip.**

A first pass that used max-over-sampled-observations instead produced an apparent **49.4% flip rate** —
entirely methodology artifact, since sampled observations systematically understate true highs.

Caveats that keep this from being a closed question: n=334 spans only **7 distinct days**, and days
(not rows) are the unit of correlation, so the effective sample is nearer 7. Agreement is at 2° bucket
resolution. A calm week is the easy case, and disagreement is likeliest on volatile days — which are
also the days with the largest edges and biggest positions.

So: **the top risk from §1 is substantially de-risked, not eliminated.** The logger runs daily; CLI
retention is only ~7 days, so a missed week is unrecoverable. Chasing exact TWC values via (1) or (2)
drops to opportunistic priority.

## 6. Forecast inputs — confirmed working, no blockers

- **api.weather.gov**: all 24 stations resolve. Observations and gridpoint forecasts available for
  every one. Free, no key, requires a User-Agent header. Station and gridpoint IDs are recorded in
  `config/watchlist.json`.
- **Kalshi station IDs map cleanly to NWS stations.** Two are worth flagging because the obvious
  guess is wrong: **Chicago is `CLIMDW` = Midway (KMDW), not O'Hare.** **Houston is `CLIHOU` = Hobby
  (KHOU), not Bush/IAH.** NYC is Central Park (KNYC). Getting either of those wrong would be exactly
  the §9 failure mode.
- **Open-Meteo ensemble API**: works, free, no key. Returns **82 members** for a single point
  (GEFS 31 + ECMWF IFS 51) at `ensemble-api.open-meteo.com/v1/ensemble`, and accepts
  `temperature_unit=fahrenheit` so there's no conversion rounding. Good Tier 1 input.

## 7. Kalshi API access

- Production public read endpoints (`/series`, `/markets`, `/orderbook`) work **unauthenticated** —
  enough to build and test the entire Data Collector and Forecasting agent without credentials.
- **Sandbox is reachable**: `https://demo-api.kalshi.co/trade-api/v2` returns healthy status.
- **Credentials do not exist yet** — no `KALSHI_*` env vars, no `~/.kalshi`. This is the one Phase 0
  item that needs a human login. Required before Phase 4, not before Phases 1–3.
- Exchange runs ~24/7 (one Thursday 03:00–05:00 UTC maintenance window).

## 8. Fees — partially confirmed, one number still unverified

The series records expose fees as **structured fields**: `fee_type: "quadratic"`,
`fee_multiplier: 1`. So the quadratic `price × (1 − price)` shape in spec §3 is confirmed, and the
multiplier is a per-series value the code should **read from the API rather than hardcode**.

Not confirmed: the **0.07 coefficient** and the **maker = 25% of taker** assumption. The fee schedule
PDF returned 429 and 404 on the two URLs I tried. The maker figure matters most — spec §2.3 leans on
cheap maker fills as the main way this strategy survives its own cost structure, and Kalshi has
revised maker fees before. **Verify both against your account's fee schedule before Phase 2**: if
maker fees are higher than assumed, the Phase 2 go/no-go moves against the strategy.

## 9. Recommended changes to the build plan

1. **Fix the settlement-source assumption throughout the spec** (§2.1, §4, §5, §9) — NWS is a
   forecast *input*, TWC is the settlement *target*. The spec currently conflates them.
2. **Add NWS-vs-TWC basis measurement to Phase 1** as a first-class task, and start logging for it
   now. It is a potential premise-killer and should surface before Phase 2's go/no-go, not after.
3. **Restrict the initial watchlist to high-temperature contracts in the top ~12 cities.** Lows fail
   the fee/spread bar as things stand.
4. **Model the ladder jointly** (predictive distribution → bucket probabilities) rather than as six
   independent binaries, and add ladder-sum-to-1 as a second, model-independent signal.
5. **Verify the 0.07 coefficient and the maker fee rate** before building the Phase 2 backtest on them.
