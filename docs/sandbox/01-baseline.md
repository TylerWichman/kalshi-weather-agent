# Sandbox arm 1: `baseline` (once daily, 00:00 UTC)

Pre-registered 2026-09-25, together with `00-common.md`, whose rules all apply here.

## Mechanism

Same as the main pre-registration §2. Retail prices "will it rain" from consumer
forecasts whose definition (window, trace threshold, point versus area) does not match the
contract, so the market's price-to-outcome mapping is off in a consistent direction. A
fixed recalibration curve read at one pre-climate-day time captures it.

## Rule

It is **the frozen Gate 2 rule, unchanged.** The only check is 00:00 UTC on the contract
date. The recalibration is `p = σ(α + β·logit(mid/100))` with α = −0.31947630832803087 and
β = 1.17062863218865, **copied** from `config/kxrain_frozen.json` into
`config/sandbox/baseline_frozen.json`. It is not refit. Entry, band, margin, fee and hold
to settlement are as in the main §3(d)–(h).

## Why it is here

It is the control. Arms 2 and 3 can claim to be **better than baseline** only against this
arm, measured on the same days, under the same sandbox rules and the same corrected bar
(`00-common.md` §6). It has no development gate: its development result is Gate 1
(+0.45¢), which has already been seen.

## Arm-specific mechanism check (criterion 5)

None beyond the common one. The frozen direction is NO only, so every side with ≥ 20% of
test trades must have mean net > 0, as in Gate 2.

## Its verdict does not touch Gate 2

This arm's GO or NO-GO is a statement about the sandbox program only. Gate 2 decides the
original rule. If the two disagree, the gap is explained by the three days that differ,
the 99% level against 95%, and the lack of an extension. It is **not** a reason to revisit
either verdict.
