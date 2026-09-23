# Phase 2, Economic Half — Does the Edge Survive? **NO-GO**

Run 2026-09-23. Reproduce: `python scripts/backtest.py`.

**Verdict: no detectable edge at 24–48h.** The Tier 1 model is well-calibrated
(calibration half passed) but does **not** beat Kalshi's prices. This is the step spec
§8 said "validates or kills the whole premise", and on current evidence it does not
validate it.

This is not a fee-drag failure. Maker fees are $0, so **fees paid were exactly $0**.
The strategy failed on edge, not on cost.

---

## The headline number, with its universe attached

| | tradeable (10 cities, **~57% of volume**) | shadow: LAX+NYC (**~43% of volume**) |
|---|---|---|
| Trades | 395 | 114 |
| Capital staked | $4,244 | $3,499 |
| Gross P&L | −$28 | −$57 |
| Fees paid | **$0** | $0 |
| **Net P&L** | **−$28** | −$57 |
| Return on stake | **−0.67%** | −1.62% |
| Hit rate | 47.6% | 40.4% |

LAX and NYC are hard-gated out of sizing (§2.3) but shadow-scored here. They would
have done **worse**, which supports the exclusion.

## It is statistically indistinguishable from zero

| | |
|---|---|
| Mean return / trade | +0.0672 |
| SD return / trade | 2.0714 |
| t-statistic | **+0.64** |
| 95% CI on mean return | **[−0.137, +0.271]** |

Per fold: **+12.18%, −18.27%, −8.76%, +16.08%.** Two up, two down. The honest
statement is *no detectable edge*, not *a proven loss* — but nothing here supports
deploying capital.

---

## The actual finding: the model's edge evaporates exactly where it trades

This is the part that matters, and it is not visible in the P&L alone.

| on the 395 trades actually taken | |
|---|---|
| Mean `p_model` | **0.743** |
| Mean market price | 0.464 |
| **Mean predicted edge** | **+0.278** |
| **Mean realized outcome** | **0.476** |
| **Realized edge vs price** | **+0.012** |

**The model claimed +27.8 points of edge and delivered +1.2.**

The calibration half measured reliability at 0.0023 — the probabilities are honest
*on average*. But trade selection is not an average: a trade is taken precisely where
`p_model` disagrees most with `p_market`. **Conditional on being selected, the model
is badly miscalibrated**, because the large disagreements are overwhelmingly the
model being wrong rather than the market being wrong.

Said plainly: aggregate calibration does not survive adversarial selection. Selecting
on disagreement with a well-informed counterparty selects for your own error. The
Phase 2 calibration pass was real but did not imply what it appeared to imply, and
that gap is the single most useful thing this backtest produced.

## Gate activity

| gate | rejections |
|---|---|
| spread | 2,210 |
| station_excluded | 2,018 |
| fee_bar | 1,271 |
| no_fill | 681 |
| implausible_edge | 156 |

`spread` dominating is the correct behaviour: 62% of candles quote a 1¢ spread, so
these are overwhelmingly "modeled edge smaller than the spread" — the gate working.

---

## Two bugs found and fixed in the harness itself

Both would have produced a confidently wrong answer:

1. **The first version only ever bought YES.** In a 6-bucket ladder most buckets sit
   at a few cents, so resting a bid is nearly always the cheap-tail side. That
   produced a fake +20.67% on a 17.2% hit rate. Adding the NO side (buying NO at *n*
   rests as a YES offer at 100−*n*) moved the result to −0.67% on a 47.6% hit rate.
2. **LAX and NYC were being skipped, not shadow-scored.** The station gate blocked
   them before any measurement, contradicting "scored but not traded". They are now
   run through the full pipeline with only the station gate bypassed.

## What this does not rule out

The no-go applies to **this signal, at this lead, with this model** — not to the
venue:

- **The ladder-coherence check (§2.6) is untested.** It is model-independent,
  arithmetic on the order book, and has a completely different risk profile. It could
  survive where the forecast edge does not. It should be the next thing tried, and it
  is cheap.
- **Tier 2 / coastal correction** would improve calibration, but the selection effect
  above suggests the problem is not primarily model quality. A better model still gets
  selected against. Expect this to help less than it looks.
- **Other lead times.** 0–24h is structurally unwinnable (Phase 1). 48–72h+ has worse
  forecast skill. 24–48h was the best candidate and it is flat.

## Recommendation

**Do not proceed to Phase 3–6 on the forecast-edge premise.** Spec §8 is explicit that
Phase 2 is where the premise gets killed if it is going to be, and refusing to act on
that is how a fee-sensitive strategy bleeds slowly instead of stopping.

Concretely, in order:

1. **Test the §2.6 ladder-coherence check.** Cheap, model-free, uses data already
   loaded, and is the one remaining untested source of edge in the spec.
2. If that also fails, **stop.** The infrastructure is sound and reusable; the
   forecast-edge hypothesis is not supported.
3. Keep the basis logger and collector running regardless — they cost nothing and the
   data is unrecoverable if paused.

## Caveats on the result itself

- **Queue position is assumed, not measured** (`src/fillsim.py`): trade-through
  required, 10% participation cap, no queue credit. Conservative on fill rate, silent
  on adverse selection. A more permissive fill model would add trades, not edge — the
  realized-vs-predicted gap above is independent of fill assumptions.
- **395 trades is a modest sample.** The CI is wide. But a real edge of the claimed
  +27.8 points would be unmissable at this n; what is excluded is a *large* edge, and
  that is the relevant exclusion.
- Entry is maker-only at the resting side, held to resolution. Intraday exits were
  deliberately not modeled, to avoid compounding an exit-timing assumption onto the
  fill assumption.
