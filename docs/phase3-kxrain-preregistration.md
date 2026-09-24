# KXRAIN — Pre-registration

Written and committed **2026-09-24, before any KXRAIN price or outcome was examined.**
The only KXRAIN facts consulted were contract metadata (rules text, city list, open and
close times) and aggregate volume (CLOSEOUT addendum 2026-09-24). No candle, trade,
book or `result` value has been read.

Same rules as spec v3 §9.5 and Phase 2b: the mechanism and the go/no-go threshold are
fixed here; nothing below is changed after results are seen; a negative result is not
followed by a loosened rule; a positive number from a mechanism other than the one
registered is not accepted (Hypothesis A precedent).

---

## 1. The contract

`KXRAIN-<date>-<city>` is 28 binary markets a day, one per city. Each resolves YES if
"total precipitation at CLI<station> in <city> on <date> is **strictly greater than 0
inches**." **Trace (T) and missing values count as 0.** Settlement is by The Weather
Company, which reproduced the final NWS CLI product in 334 of 334 checks on the
temperature series (CLOSEOUT §3.5).

Each market opens at 09:10 UTC on the day before and closes at 06:00 UTC the day after.
The NWS climate day runs midnight to midnight **local standard time**.

## 2. The mechanism

**Retail participants price "will it rain" from consumer forecasts whose definition
does not match the contract, so the market price is miscalibrated in a consistent,
structural direction.** There are three specific mismatches:

1. **Window.** Consumer apps headline a daytime or a 12-hour probability of
   precipitation. The contract covers a full 24-hour climate day, and the 24-hour
   probability is at least the larger of the two 12-hour ones. *Predicts YES
   underpriced.*
2. **Threshold.** A trace of rain, which people see and feel, counts as NO. *Predicts
   YES overpriced where light showers are common.*
3. **Point versus area.** The contract is one airport gauge. Apps show a city-wide
   impression. *Direction ambiguous.*

The net direction is **not** asserted in advance. It is estimated on the development
set and then must hold, in the same direction, on data that does not yet exist (§4).

**What would make this real and not the forecast-edge mechanism that already failed:**
the test uses *no weather model at all*. It uses only the market's own price and
Kalshi's own `result`. Any edge found is a property of how the market maps price to
outcome, not a claim that we forecast rain better than the market. That matters
because of CLOSEOUT §3.1: trading where a model disagrees with a well-informed market
selects for the model's own errors. Here there is no model to disagree.

## 3. The single configuration

Everything is fixed now. The only quantities estimated from data are the two
recalibration parameters in (e).

| | |
|---|---|
| (a) Universe | Every city listed on each event. No city selection, before or after. |
| (b) Decision time | **00:00 UTC on the contract date** (20:00 EDT / 19:00 EST the evening before). This is before the climate day begins in every city, so no observation of the day can be in the price. |
| (c) Price | The hourly candle ending at the decision time: `yes_bid_close`, `yes_ask_close`. A market missing either side is skipped. Mid = (bid + ask) / 2. |
| (d) Execution | **Taker only.** Buy YES at the ask or NO at 100 − bid, pay the real quadratic taker fee (`src/fees.py::trade_fee_cents`, `is_maker=False`). This avoids the unvalidated maker queue assumption that every earlier backtest rested on. |
| (e) Recalibration | Logistic: `p = σ(α + β · logit(mid/100))`. Two parameters, fit by maximum likelihood on the development set only. |
| (f) Entry rule | Buy YES if `p − ask/100 ≥ fee/100 + 0.03`. Buy NO if `(1 − p) − (100 − bid)/100 ≥ fee/100 + 0.03`. At most one position per market. |
| (g) Price band | Only enter when the side bought costs **5¢ to 95¢**. This excludes the cheap-tail short-volatility pattern that Hypothesis A found and that CLOSEOUT §7 left deliberately unregistered. |
| (h) Exit | Held to settlement. No exit rule, so no exit hyperparameters. |
| (i) Unit | 1 contract per trade for the primary statistic. Dollar sizing in §5. |

The 3¢ margin in (f) is fixed here and is **not** tuned.

## 4. Data split

| set | events | status at registration |
|---|---|---|
| **Development** | `KXRAIN-26JUL15` through `KXRAIN-26SEP23` (66 events) | loaded, **unexamined** |
| Embargo | `26SEP24` through `26SEP26` | never used |
| **Test** | `26SEP27` onward, first **45 settled events** (through `26NOV10`) | **does not exist yet** |

The test set is prospective: its prices have not been quoted yet, so it cannot have
been looked at. It is evaluated **exactly once**, after its last event settles.

**Regime bound.** Development is summer convection (July–September). Test is autumn
frontal weather, and it crosses the end of DST on 2026-11-01. A mispricing that holds
across that change is stronger evidence than one within a single season. One that does
not hold is a NO-GO, not a reason to split by season afterward.

## 5. Decision rules

### Gate 1 — development (early kill; can stop the test, cannot start trading)

Fit (e) using **leave-one-calendar-week-out** cross-validation over the 66 development
days, and apply (f)–(g) out of fold.

**If the out-of-fold mean net P&L per contract is ≤ 0, the verdict is NO-GO** and the
test period is not run. Otherwise, refit (e) on all 66 days, freeze α, β and the
implied trade direction, record them in a commit **before 2026-09-27 00:00 UTC**, and
proceed to the test.

### Gate 2 — test (the go/no-go)

Apply the frozen rule to the 45 test events. **GO only if all of the following hold:**

1. **Profitable per contract.** Mean net P&L per trade > 0, and the 95% CI from a
   **day-block bootstrap** excludes zero. Days are resampled as units because cities
   on the same day share weather; 10,000 resamples.
2. **Frequent enough to be a trading system.** At least **100 trades** in the test
   period. If there are fewer by `26NOV10`, the period extends to the first of
   `26DEC10` or 100 trades. Still fewer means NO-GO on frequency.
3. **Worth operating.** Net P&L of at least **$5 per settled day** on average, with
   each trade sized to the displayed depth at the best price in the
   `KalshiCandidateBooks` snapshot nearest before the decision time, capped at 100
   contracts. If more than 10% of trades lack a snapshot within 10 minutes, the period
   extends until 45 events have coverage.
4. **Stable.** Net P&L is positive in both halves of the test period, split at the
   median date.
5. **The registered mechanism, not another one.** The trade direction on the test set
   matches the frozen development direction. No single day contributes more than 25%
   of total net P&L, and no single city more than 40%.

Any failure is **NO-GO**. There is no partial GO, no "works in city X", and no re-run
at a different decision time, margin or price band.

### Reported for diagnosis, never for the decision

- Market reliability diagram and Brier decomposition at the decision time, for both
  sets.
- The same statistics at 12:00 UTC on the contract date, when observations exist. The
  market is expected to read them (CLOSEOUT §3.2), so apparent edge there indicates
  leakage or a bug, not opportunity.
- Per-city and per-region breakdown, labelled thin.

## 6. Explicitly not registered

Any of these would need its own pre-registration:

- **Forecast edge from the ensemble or NWS probability of precipitation.** The same
  approach failed on temperatures (CLOSEOUT §3.1). It is the obvious next step only if
  this test finds the market miscalibrated.
- **The DST climate-day boundary.** From March to November the climate day runs 01:00
  to 01:00 local daylight time, so rain between 00:00 and 01:00 daylight time counts
  toward the *previous* date. This is a real definitional trap, but it is narrow (one
  hour a day), observation-driven, and likely read by the market as fast as the
  short-lead temperature signal was. The test set loses the effect after 2026-11-01
  anyway.
- **Intraday "rain already fell" detection.** Once 0.01 in. is measured, YES is
  locked. Hypothesis B showed the market closes such gaps within minutes.
- **Maker execution.** It becomes relevant only after a GO, and only with the queue
  assumption validated against the forward books.

## 7. After the verdict

- **NO-GO:** rain is closed on the same terms as the daily-high ladders. The finding is
  recorded in CLOSEOUT.
- **GO:** spec v3 Phase 3, paper trading against live books. No capital, and the
  Phase 5.5 one-week live simulation gate still applies.

The analysis script (`scripts/rain_calibration.py`) is written after this document is
committed, and must implement §3–§5 exactly as written. Any discrepancy between this
document and the script is resolved in favour of this document.

---

## Amendment 1 (2026-09-24, before any test-period price exists)

**Additional analysis only. It does not change what is traded or how the verdict is
reached.**

Gate 1 found YES most overpriced in the 30–50¢ mid band (`docs/phase3-kxrain-gate1.md`).
That band was found by looking at development results, so it is **not** added to the
trading rule. The frozen rule in §3 is traded unchanged on the test set.

After the Gate 2 verdict is printed, `scripts/rain_calibration.py gate2` also reports:

1. The frozen rule's test trades broken out by market mid at the decision time, in
   10¢ bands, with the mean net per contract and a day-block 95% CI for each band with
   at least 10 trades.
2. The flagged 30–50¢ band on its own, against all trades.
3. The market reliability tables at 00:00 and 12:00 UTC on the test set, which §5
   already promised and which the first version of the script left out.

**What a good 30–50¢ result would mean, fixed now.** If that band has at least 30
trades and a mean net per contract at least 2¢ above the rule as a whole, it
qualifies as **a new hypothesis**. That hypothesis needs its own pre-registration,
fixed before any further data is seen, and its own forward test period starting after
that registration. The Gate 2 test data **cannot** be reused to confirm it, because it
would then have been used to select it. It is never a route into this test's verdict.
Below that trigger, no new hypothesis is drawn from the band.
