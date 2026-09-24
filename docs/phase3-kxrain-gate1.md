# KXRAIN Gate 1 — PASS, but only just

Run 2026-09-24 14:07 UTC. Reproduce: `python scripts/rain_calibration.py gate1`.
Pre-registration: `docs/phase3-kxrain-preregistration.md` (51c7c16). Analysis script
committed before it was run (818b322). Frozen parameters: `config/kxrain_frozen.json`.

## The verdict against the rule

Pre-registered rule, §5 Gate 1: out-of-fold mean net P&L per contract ≤ 0 is NO-GO.

| | |
|---|---|
| Out-of-fold trades | 305 (all **NO**), on 57 of 65 days |
| Mean net per contract | **+0.45¢** |
| Day-block 95% CI | **[−4.42, +5.15]** |
| Folds positive | 6 of 11 (one fold had no trades) |

**PASS on the letter of the rule.** The rule was designed as an early kill, not as
evidence, and it has done that job: it did not kill. It says nothing more than that.
The confidence interval is centred almost exactly on zero and is ten times wider than
the estimate.

## What the market is doing

Model-free reliability at the decision time (1,297 markets, 65 days):

| mid band | n | mean mid | realized YES | gap |
|---|---:|---:|---:|---:|
| 0–10¢ | 552 | 0.040 | 0.009 | −0.031 |
| 30–40¢ | 86 | 0.347 | 0.198 | **−0.150** |
| 40–50¢ | 102 | 0.450 | 0.294 | **−0.156** |
| 70–80¢ | 74 | 0.749 | 0.676 | −0.074 |

Reliability term 0.0043 against resolution 0.0808: well calibrated in aggregate.
Where it is off, **YES is overpriced**, and most of all in the 30–50¢ band. That fits
the trace mechanism (§2.2), where visible drizzle settles NO, winning out over the
window mechanism (§2.1). The fitted curve (α −0.32, β 1.17) puts fair value 4–9¢
below the market mid from 10¢ to 70¢.

**Why so little of that survives:** the rule buys NO at 100 − bid, so it pays the full
spread plus the taker fee (up to 2¢), and the 3¢ margin must clear on top of that.
A 15-point gap in two narrow bands, averaged with near-zero gaps elsewhere, leaves
+0.45¢.

## Caveats, stated before Gate 2 rather than after it

- **Gate 2 is very unlikely to pass criterion 1.** A day-block CI of about ±4.8¢ on
  305 trades means the test's ~45 days would need a true effect several times larger
  than the development estimate to exclude zero. The honest prior is NO-GO.
- The 30–50¢ gap rests on 188 markets across correlated days in a single summer regime.
- The 12:00 UTC control is *more* miscalibrated in the 60–80¢ bands (−0.14 to
  −0.16). This is diagnostic only. It does not bear on the decision.
- 61 markets had no candle at 00:00 UTC (historical-tier markets with zero volume get
  no candles) and 47 had a one-sided quote. Both were skipped as §3(c) requires.

## One clarification made at freeze time

§5 Gate 2.5 said "the trade direction on the test set matches the frozen development
direction" without operationalising it. The frozen rule trades only NO, so it was fixed
in `config/kxrain_frozen.json`, **before any test-period price exists**, as: every
side with at least 20% of test trades must have mean net > 0.

## Next

Gate 2 runs once, after event `26NOV10` settles and is loaded. The rule is not changed
before then. That includes not stopping early because the Gate 1 margin is thin: an
early stop on discretion is a rule change too.

## Keeping the Gate 2 record intact (2026-09-24)

Gate 2 needs a book snapshot in the 10 minutes before 00:00 UTC on each of 45 days,
and candles for each test event. Each failure mode found, and what was done about it:

| failure mode | fix |
|---|---|
| Book horizon was 30h; KXRAIN closes exactly 30h after the decision time, so every rain market fell outside it | Horizon for KXRAIN set to 48h (818b322) |
| Idle sleep after 45 min on AC; lid close = sleep; Modern Standby does not run tasks | AC: never sleep, never hibernate, lid close = do nothing, wake timers on |
| Task ran only while logged in, so a Windows Update reboot stops it until the next login | Needs admin: re-register the data tasks as run-whether-logged-on-or-not (S4U) |
| Test events not loaded promptly lose zero-volume candles at the historical cutoff | `KalshiCandidateHistory` loads settled events daily at 14:00 local |
| Any of the above failing silently | `python -m src.candidates health` checks snapshot age, gaps, every decision-time window and every due event; `KalshiCandidateHealth` runs it at 09:00, 21:00 and at logon and shows a Windows notification on any problem |

**Battery behaviour is deliberately unchanged** (3 min idle sleep, lid = sleep). A
laptop that never sleeps on battery runs hot in a bag and dies flat anyway. **The
laptop needs to stay plugged in through 2026-11-11.** Time spent unplugged and idle
will show up as a health alert, not as silent loss.
