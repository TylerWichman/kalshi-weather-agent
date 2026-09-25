# Sandbox development gates: both arms pass the early kill, and that is all

Run 2026-09-25. Reproduce: `python scripts/sandbox_gates.py import-dev`, then
`gate1 --arm fixed` and `gate1 --arm trigger`. Pre-registration: `docs/sandbox/0[0-3]*.md`
(1a5ba17). The gate script was committed before it was run (db299a4).

| arm | out-of-fold trades | mean net / contract | day-block 95% CI | verdict |
|---|---:|---:|---|---|
| 1 `baseline` | no gate: it is Gate 1 | (+0.45¢ at Gate 1) | [−4.42, +5.15] | control, not gated |
| 2 `fixed` | 623 (609 NO), 61 days | **+3.02¢** | [−0.07, +5.96] | PASS, frozen |
| 3 `trigger` | 338 (all NO), 61 days | **+3.54¢** | [−1.83, +8.96] | PASS, frozen |

The gate asks only whether out-of-fold mean ≤ 0, and neither arm fails it. **Neither
interval excludes zero even at 95%.** The forward bar is 99% (`00-common.md` §6), and at
28 days its interval is roughly ±9¢. Both estimates are a third of that. The honest prior is
still NO-GO for every arm.

## What the numbers do and do not say

- **Arm 2** by check (out of fold): D−1 12:00 had 210 trades at +5.0¢, D−1 18:00 had 179
  at −0.3¢, D 00:00 had 118 at +2.0¢, and D 04:00 had 116 at +5.6¢. The fitted curves all
  lean the same way (α −0.12 to −0.42, β 1.17–1.36, so YES is overpriced at mid-range
  prices). The steepest is at D−1 12:00, which fits the lead-time mechanism, but four
  thin, correlated slices are not evidence of it. The checks are **not** narrowed to the
  best ones. That would be selecting on development results, and the registration forbids
  it.
- **Arm 3** gave 1,736 evaluation points, about 1.3 per market. β is 0.92, flatter than the
  identity, and α is −0.33. So at move moments the market is again too high on YES, but by
  a different shape than at 00:00. The hour-by-hour split ranges from −12.7¢ to +37.8¢ on
  10–53 trades each. That is noise and is reported only because the arm file promised it.
- **Every trade in both arms is NO,** apart from 14 YES in arm 2. That is the same
  direction as Gate 1: YES overpriced. The three arms are therefore **not independent
  bets.** They are three ways of timing one mispricing. A bad forward month for the
  mispricing will sink all three together, and a good one will lift all three. That is
  why the comparison against baseline (§6) is a separate, paired claim.
- Arm 3's out-of-fold count (338) is above the 50-trade warning. Over 28 test days, at
  the development rate, expect roughly 150 trades, which is enough for criterion 2 if the
  rate holds.

## Development rows changed since Gate 1

Gate 2's own loader, run today on `data/candidates.sqlite`, returns 1,303 markets and 303
frozen-rule trades on the development set. Gate 1's report (09-24) has 1,297 and 302. So
the database gained a few development rows after Gate 1 ran. The sandbox copied today's
rows. Gate 2 is unaffected: its α and β were frozen on 09-24, and it scores only test
events.

## Frozen

`config/sandbox/fixed_frozen.json` and `config/sandbox/trigger_frozen.json`, committed with
this file, before the 2026-09-29 12:00 UTC deadline. `baseline_frozen.json` is a copy of
Gate 2's α and β. Nothing below changes before the verdict, which runs once, after
`26OCT27` settles.
