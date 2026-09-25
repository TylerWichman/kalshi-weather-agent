# Retrospective check: fit on July and August, run through September

**Written and committed 2026-09-25, before any October data exists** (before the first
sandbox test event, `26SEP30`, and before the first Gate 2 test event, `26SEP27`, settles).

**Status: diagnostic only.** This is not a pre-registered hypothesis and not a forward
test. It is not evidence for or against Gate 2 or any sandbox arm the way a forward test
result would be. It changes no rule, parameter, date or verdict. September's monthly totals
had already been looked at earlier the same day, before this was run.

Reproduce: `python scripts/retro_check.py OUTDIR` on this branch (`retro-sep-check`, forked
from `sandbox` at 2cc6f89). Results: `docs/retro/2026-09-25-results.json`. The run reads only
`data/sandbox.sqlite`, the development copy. Sep 24–26 are Gate 2's embargo days and are not
used.

## What was done

1. For each rule, the recalibration was fit on **Jul 15 – Aug 31 only** and frozen, as if no
   later data existed. The rules are the Gate 2 rule (which is also arm 1), arm 2 (fixed
   times) and arm 3 (move trigger). The rule structures are unchanged from their
   pre-registrations.
2. The frozen rule ran through **Sep 1–23 one day at a time**. Each day's decision used only
   that day's own candle quotes at its check times.
3. The expected level is the July–August out-of-fold result: each week scored with a curve
   fit on the other July–August weeks.
4. **Edge realized** is the mean net per contract actually delivered in September on the trades
   the frozen curve chose, divided by the mean edge the curve predicted on those same trades.
   This measures exactly where the temperature model failed (CLOSEOUT §3.1: predicted +27.8,
   realized +1.2, a ratio of 0.04).

## Results (net per contract, 1 contract per trade)

| rule | Jul–Aug expected (OOF) | September actual | Sep 95% day-block CI | Sep trades | edge realized | Brier, market / frozen curve |
|---|---:|---:|---|---:|---:|---|
| Gate 2 rule (= arm 1) | −0.07¢ | +3.57¢ | [−2.69, +9.55] | 158 | +3.57 of +5.24 = **0.68** | 0.0953 / 0.0942 |
| Arm 2, fixed times | +2.62¢ | **−0.32¢** | [−4.66, +4.16] | 259 | −0.32 of +5.26 = **−0.06** | 0.0962 / 0.0967 |
| Arm 3, move trigger | +3.95¢ | +1.88¢ | [−4.43, +8.99] | 153 | +1.88 of +5.24 = **0.36** | 0.1856 / 0.1817 |

By September week (mean ¢ per contract, trades in brackets):

| rule | Sep 1–6 | Sep 7–13 | Sep 14–20 | Sep 21–23 |
|---|---:|---:|---:|---:|
| Gate 2 rule | +16.65 (37) | +5.25 (40) | +0.33 (46) | −7.91 (35) |
| Arm 2 | +1.29 (75) | +4.15 (78) | −1.15 (62) | −9.82 (44) |
| Arm 3 | +2.44 (54) | +11.71 (34) | −0.91 (47) | −11.06 (18) |

Arm 2 by check time in September: 8 AM ET −1.92¢ (131 trades), 2 PM ET −1.71¢ (66),
8 PM ET +0.31¢ (29), midnight ET +8.27¢ (33).

A $100 account through September, with at most $5 per trade from cash on hand and cash locked
until settlement: Gate 2 rule $146.11, arm 2 $51.38, arm 3 $53.94. Cash limits make these
differ from the per-contract results. Arm 2, for example, funds its early (losing) checks
first. Without cash limits, the $5-sized totals are +$46.11, +$9.65 and −$19.46.

## Reading (owner's, recorded 2026-09-25)

- **Arm 2 (−0.06):** a sign reversal. The frozen curves predicted edge on the trades they
  chose, and September delivered none. This is essentially the overfitting signature of the
  temperature model, and a real caution against prioritizing arm 2.
- **Arm 3 (0.36):** attenuated, but in the same direction as predicted.
- **Gate 2 rule / arm 1 (0.68):** the nominal ratio is not very interpretable, because the
  July–August base expectation was near zero (−0.07¢ OOF). The September CI still spans zero.
- All three rules lost money in the last partial week (Sep 21–23, three days). That is too
  few days to call a trend.

## What this does not change

Nothing. Gate 2 runs as registered (test `26SEP27`–`26OCT24`, verdict once after `26OCT24`
settles). The sandbox arms run as registered (test `26SEP30`–`26OCT27`, verdict once, 99%
bar). No arm is dropped, re-weighted or retuned on the basis of this check.
