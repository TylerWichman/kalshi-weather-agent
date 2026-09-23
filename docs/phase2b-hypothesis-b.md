# Hypothesis B — Stale-Quote Detection: **NO-GO**

Run 2026-09-23. Reproduce: `python scripts/staleness.py --events 150`.

Phase 2b §3 said to answer the cheap measurement question first, because it could rule
the hypothesis out before any trading logic was written. It does. **§2.4 named the
right constraint — polling cadence, not modelling — and the reality is worse than
that.**

## The measurement

Hourly candles cannot resolve how long a mispricing lasts: a gap visible in one hourly
bar might have lived 40 seconds or 40 minutes. So 1-minute candles were reloaded in
±2h windows around every deep gap (sum of asks < 95¢ or sum of bids > 105¢) and the
ladder reconstructed minute by minute.

**149 events, 24,895 minute-ladders, 2,321 incoherent windows.**

## Result 1 — windows close far faster than we can poll

| persistence | windows | share |
|---|---|---|
| ≤ 1 min | 1,006 | **43.3%** |
| 1–5 min | 755 | 32.5% |
| 5–15 min | 337 | 14.5% |
| 15–60 min | 182 | 7.8% |
| > 60 min | 41 | 1.8% |

**Median 2 minutes. Only 10.2% outlive a single 15-minute poll.**

This sample is biased **in favour** of the hypothesis: it starts from gaps already
visible in hourly bars, which oversamples long-lived ones — a 40-minute gap is far
likelier to land in an hourly snapshot than a 40-second one. The true distribution is
shorter still.

## Result 2 — the persistent windows are persistent *because* nobody can trade them

| | windows < 15 min | windows ≥ 15 min |
|---|---|---|
| Share with a zero-volume leg | 85% | **96%** |

This is the finding that closes the hypothesis, and it is not a cadence problem that
faster infrastructure would fix. **Persistence and liquidity are inversely related.**
A mispricing survives precisely when no one is trading the ladder; as soon as real
volume arrives it is corrected within minutes. Buying faster polling buys access to
windows that have nothing on the other side.

## Result 3 — what survives is negligible

Strict test: window persists ≥ 15 min **and** every leg actually trades in some minute
**and** the gap pays six taker legs at the size that printed.

| | |
|---|---|
| Persistent windows | 236 |
| With a tradeable minute | **62** |
| Median net per window | **$0.12** |
| Total across 149 events | **$15.46** |
| Extrapolated to all 294 deep-gap events | **~$30** |

**~$30 over nine months across twelve cities**, and that is before competition, before
slippage, and using a sample deliberately biased toward the best cases.

## Verdict against the pre-registered rule

§2.3 required "a systematic, repeatable pattern of exploitable staleness … in a large
enough and frequent enough sample … net profitable after the real taker fee formula,
with a 95% CI excluding zero", and §2.3 further required frequency be reported:

> a strategy that fires twice a year isn't a day-trading system

**62 tradeable windows across 149 event-days ≈ 0.4 per event-day**, worth $0.12 each.
Across the 12-city watchlist that is a few dollars a month. The rule is not met on
frequency, on magnitude, or on profitability.

**NO-GO.** Not revisited (§4: do not loosen the rule after a negative result).

## What carries forward

The Philadelphia `[1,1,10,1,1,1]` example that motivated this hypothesis was real, but
it was real *because* that ladder was untraded at that moment. That is the general
case, not an exception — and it is a useful thing to know about this venue: its
mispricings are illiquidity artifacts, not information lags.

This also retires the idea that faster infrastructure would unlock anything here. It
would not. The constraint is not reaction time.
