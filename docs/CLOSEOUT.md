# Kalshi Weather Day-Trading Agent — Project Closeout

**Status: STOPPED.** No capital was ever deployed. Five mechanisms were tested
against real historical prices; none supports a tradeable edge. The venue's only
liquid weather market is the one already tested and rejected.

Decision date: 2026-09-23. Elapsed: two days from spec to closeout.

---

## 1. The stop decision

The final question was whether any *other* Kalshi weather market could support the
strategy. Measured live, 24h volume:

| market group | 24h volume | vs benchmark | open interest | median spread |
|---|---|---|---|---|
| **Daily-high ladders (benchmark)** | **1,283,885** | 100% | 949,612 | **1¢** |
| Monthly rain/snow | 6,445 | **0.5%** | 51,715 | 1¢ |
| Heatwave | 318 | **0.02%** | 1,277 | **19¢** |
| Hourly temperature | 211 | **0.02%** | 1,310 | 3¢ |

- **`CITYTEMP` does not exist** on the API. `KXCITIESWEATHER` exists but has **0 open
  markets**.
- Monthly rain is the best alternative at **1/200th** the benchmark volume, and only
  **3 of 22** series have any open market.
- Heatwave markets quote a **19¢ median spread** — wider than any plausible edge,
  the same structural disqualifier that removed the low-temperature series in Phase 0.
- Hourly markets: 4 of 11 series live, 211 contracts in 24h.

There is no deeper pool to move to. The daily-high ladders *are* the weather market
on this venue, and they were tested exhaustively.

---

## 2. What was tested, and what happened

| # | mechanism | spec | result |
|---|---|---|---|
| 1 | Forecast edge, 24–48h lead | v3 §2.2 | **No detectable edge.** −0.67% on 395 trades, t = +0.64, CI [−0.137, +0.271] |
| 2 | Ladder coherence | v3 §2.6 | **~$110 / 9 months**, 61% of it from three stale-quote snapshots |
| 3 | Stale-quote detection | 2b §2 | **~$30 / 9 months.** Median window 2 min; 96% of persistent windows have a zero-volume leg |
| 4 | Market making | 2b §1 | **Spread capture −$51,150.** Mechanism falsified |
| 5 | Alternative markets | this doc | **0.02–0.5% of benchmark volume** |

Fees were **$0** in every test — maker fees on weather are genuinely zero. **Nothing
here failed on cost. Everything failed on edge.**

---

## 3. The five findings worth keeping

### 3.1 Aggregate calibration does not survive adversarial selection

The single most transferable result. The Tier 1 model was genuinely well-calibrated —
reliability 0.0023, CRPS skill 71.6% over climatology, PIT near-uniform on 8 of 12
stations. And it was **useless**, because on the trades it actually selected:

| | |
|---|---|
| Mean `p_model` | 0.743 |
| Mean market price | 0.464 |
| **Predicted edge** | **+27.8 points** |
| **Realized outcome** | 0.476 → **+1.2 points** |

A trade is selected precisely where the model disagrees most with the market. Those
disagreements are overwhelmingly *the model being wrong*, not the market. Being
calibrated on average says nothing about being calibrated on the subset you choose to
bet, and selecting on disagreement with a well-informed counterparty selects for your
own error.

**Any future project that validates a model with aggregate calibration and then trades
its largest disagreements has this bug.**

### 3.2 At short lead the market reads observations and you cannot beat it

At 5–8h before a daily high is final, the high has usually already occurred:

| predictor | correct bucket |
|---|---|
| Kalshi market | **12/12** |
| NWS gridpoint | 4/12 |
| Ensemble mean | 1/12 |

Worse, a forecast-only model reads this as enormous edge. Atlanta settled at 86°F with
the market bidding 99¢ on "≤86" while the gridpoint said 90°F — a naive model saw ~90
points of edge on a 1¢ contract that was a certain total loss. **The fee gate does not
catch this**, because fees are trivial at 1¢.

### 3.3 Persistence and liquidity are inversely related

Mispricings survive precisely when nobody is trading. 96% of windows lasting 15+
minutes had zero volume on at least one leg, against 85% of shorter windows. Faster
polling buys access to windows with nothing on the other side — **this is not an
infrastructure problem and speed does not fix it.**

### 3.4 A "GO" can come from a mechanism you did not test

Market making returned +$37,100, t = +21.93, stable across all four folds. Decomposed:

| | |
|---|---|
| Spread capture | **−$51,150** |
| Settlement of one-sided inventory | +$88,250 |

The profit was a short-tail directional bet, not spread capture. Cause is structural:
a resting bid at 1¢ can never fill (it needs a trade *below* 1¢), so on the cheap
buckets that dominate a 6-bucket ladder the strategy can only sell. Sells exceeded
buys 1.65× in the 1–5¢ band.

Measured adverse selection — **−0.0898¢ mean mid-move per fill across 102,225 fills**,
44.8% adverse — is what turns spread capture negative against a 1.8¢ spread.

### 3.5 Get the measurement source right before believing the measurement

The NWS↔TWC settlement basis looked like a project-killer, then looked fine, and the
difference was entirely methodology:

- Max over **sampled observations** → apparent **49.4%** bucket-flip rate.
- **Final CLI product** (which is what Kalshi's station IDs literally name — `CLINYC`
  *is* the Central Park climate report) → **0 flips in 334**.

The preliminary afternoon CLI product and the final morning one differ by a full
bucket (NYC 2026-09-20: 67 vs 69).

---

## 4. Errors made and caught

Recorded because the catch rate matters more than the error rate:

| error | effect | how it surfaced |
|---|---|---|
| Wrong API field names (`volume` vs `volume_fp`) | Every market read as zero volume | Uniform zeros looked impossible |
| `less` tail off by one (`cap` vs `cap−1`) | Bucket bounds shifted 1°F | Ladder contiguity check |
| Sampled-obs vs final CLI product | Fake 49.4% flip rate | Implausible 10–20°F misses |
| Backtest bought YES only | Fake +20.67% on a 17.2% hit rate | Hit rate below breakeven |
| LAX/NYC skipped, not shadow-scored | No measurement of excluded stations | Gate fired before measurement |
| Sell-ladder payout off by ~400¢ | Sell-side arbs all showed −402¢ | Suspiciously constant value |
| Flat 100-lot arb sizing | Ignored 15–33 contract thin legs | Depth check |
| "All series present = load finished" | Reported a running load as complete | Count still climbing |
| Collector killed on battery | Silent partial data loss | Exit code `0xC000013A` |

Two of these (fields, product choice) produced *confident, plausible, wrong* numbers
that were only caught by sanity-checking against an independent source.

---

## 5. What was built (all working, all reusable)

```
src/db.py          storage schema, append-only where it matters
src/kalshi.py      market data client; station + ladder verification
src/weather.py     NWS gridpoint, Open-Meteo ensemble, station observations
src/collector.py   Data Collector Agent (contracts/books/forecasts/observations)
src/fees.py        confirmed fee model; maker $0 guard
src/risk.py        hard gates: station, short-lead, implausible-edge, spread, fee bar
src/fillsim.py     maker fill simulation with stated queue assumptions
src/history.py     historical loader, routed across the live/historical cutoff

scripts/basis_logger.py          NWS↔TWC basis (daily, scheduled)
scripts/calibrate.py             Tier 1 calibration scoring (§9.5 methodology)
scripts/backtest.py              economic backtest
scripts/coherence.py             ladder-coherence check
scripts/staleness.py             stale-quote persistence
scripts/marketmake.py            two-sided market making
scripts/liquidity_inventory.py   cross-market liquidity measurement
```

Data collected: **539,943 candles** across 14,400 settled markets, **26,124**
forecast/actual pairs spanning a full seasonal cycle, plus live order books and
station observations accumulating every 15 minutes.

---

## 6. Still running

Three scheduled tasks remain active. They cost nothing and their data is
**unrecoverable if paused** — Kalshi serves no historical order-book depth, and NWS
CLI products age out in ~7 days.

| task | cadence |
|---|---|
| `KalshiWeatherBasisLogger` | daily 15:00 |
| `KalshiWeatherCollectorFast` | every 15 min |
| `KalshiWeatherCollectorSlow` | every 6 h |

To stop them: `schtasks /Delete /TN "KalshiWeatherBasisLogger" /F` (and likewise for
the other two).

Worth keeping if there is any chance of revisiting, because the full-depth order-book
record is precisely what all four backtests lacked — every one of them rested on an
unvalidated queue-position assumption.

---

## 7. The one hypothesis left unregistered

Selling the cheap tails of these ladders was profitable in-sample: stable across folds,
+$88,250 of settlement P&L. **It should not be adopted on this evidence.** It is a
short-volatility strategy — 22.9% losing days, worst −$183 — measured over **nine calm
months containing no extreme weather event**. The loss that defines its risk is almost
certainly not in the sample, and it depends entirely on the unvalidated queue
assumption.

If it is ever revisited it needs its own pre-registration, a sample containing a
genuine weather shock, and honesty that it is premium-selling held to resolution — not
the day-trading system this project set out to build.

---

## 8. Closing assessment

The premise was that ingesting NOAA/ECMWF data faster and better than retail traders
would yield an edge on daily temperature contracts. **It does not.** Kalshi's
daily-high ladders are efficiently priced at every horizon tested: the market reads
observations faster than we can at short lead, prices forecasts as well as we do at
long lead, quotes coherent ladders, and corrects real mispricings within about two
minutes.

The project ends where spec §8 said it would — "this is the step that validates or
kills the whole premise" — having done exactly that, before any capital was risked.
The infrastructure is sound, the negative results are well-measured, and the reasoning
is documented well enough that someone revisiting this can start from what was learned
rather than repeating it.

---

## Addendum (2026-09-23): site-wide liquidity survey

`scripts/site_liquidity.py`: every open non-combo market on Kalshi (121,182), taken
from Kalshi's own API as a single 24h snapshot. Sports is left out of the ranking.

**Correction to §1.** The claim that the daily-high ladders *are* the weather market
was wrong. **`KXRAIN` (daily "where will it rain") traded 197,456 contracts in 24h**,
which is more than any daily-high series in this snapshot. It was never tested: the
earlier inventory only covered *monthly* rain. If weather is revisited, test this first.
It reuses the stations, observations and ensemble pipeline already built.

- **Health: 96 series, zero open markets.** FDA markets sit under Science and
  Technology, and all of them combined trade about 4,900 contracts/24h. The largest,
  Compass Pathways, trades 1,897.
- **Weather ranks #6 of 16 categories**, at 3.8% of non-sports volume.
- A one-day snapshot is noisy. KXHIGHLAX traded 508k the day before and 136k on this day.

## Addendum (2026-09-24): the survey undercounts short-lived markets

**Correction to the 2026-09-23 addendum.** `site_liquidity.py` sums `volume_24h` over
markets that are *open at the moment of the sweep*. Every market that closed in the
previous 24h is missing from it. For a series whose contracts live an hour, that is
nearly all of its volume. `python -m src.candidates volume` measures the same thing
from the other side: the lifetime volume of every market that *settled* on each UTC
day, over 30 days.

| series | 1-day snapshot | settled/day, median (IQR) | life of one contract |
|---|---:|---:|---|
| `KXBTCD` BTC above/below | 1,591,762 | **38.7M** (33.1M–45.3M) | 1 hour |
| `KXETHD` ETH above/below | 722,994 | 1.51M (1.12M–1.88M) | 1 hour |
| `KXRAIN` daily rain | 197,456 | 683k (630k–862k) | ~44 hours |
| `KXHIGHLAX` (tested) | 135,900 | 507k (321k–693k) | ~2 days |
| `KXWTI` daily WTI | 162,281 | 456k (373k–528k) | ~2 days |
| `KXETH` ETH range | 682,269 | 176k (159k–219k) | 1 hour |
| `KXNATGASW` (weekly) | 180,897 | 71k per week | 1 week |

`KXBTCD` is about 75 times larger than the snapshot showed, and larger than every
weather series combined. Contract counts overstate money traded, though. In
`KXBTCD-26SEP2408` the busiest strike (244k contracts) was a 1c far-out-of-the-money
line. `data/candidates.sqlite` stores candle mean prices, so dollar volume can be
computed before any claim is made about depth.

**Crypto is out of scope.** `KXBTCD` is the largest short-dated volume on the site,
but it settles on a live, heavily arbitraged spot index. That makes it the most
researched market available and the least plausible place for a forecasting edge.
Collection of crypto data was started and then stopped.

Data collected for a pre-registered test (`src/candidates.py`, `data/candidates.sqlite`):

| series | settled markets | events | hourly candles | trade prints | span |
|---|---:|---:|---:|---:|---|
| `KXRAIN` | 1,405 | 66 | 59,294 | 1,340,412 | 2026-07-16 to 09-24 (series start) |
| `KXWTI` | 2,163 | 83 | 128,823 | 469,146 | 2026-05-27 to 09-23 |
| `KXNATGASW` | 1,029 | 25 weekly | 68,827 | 6,272 | 2026-04-03 to 09-18 |

Each market row carries strikes, result and the settled underlying
(`expiration_value`). Trade prints exist only after the 2026-07-25 cutoff.

Order-book snapshots (10 levels, strikes with a midpoint between 3c and 97c) run every
10 minutes through the `KalshiCandidateBooks` scheduled task. This is the one dataset
that cannot be backfilled.
To stop it: `schtasks /Delete /TN "KalshiCandidateBooks" /F`.

The three weather collectors listed in §6 are no longer registered on this machine.
