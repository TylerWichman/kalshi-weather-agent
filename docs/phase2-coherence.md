# Ladder-Coherence Check (spec §2.6) — **also NO-GO**

Run 2026-09-23. Reproduce: `python scripts/coherence.py`.

The last untested edge source in the spec, and the only model-free one: pure
arithmetic on the order book, no weather forecast involved. **It fails too.** The
ladders are efficiently priced.

## The test

Each event is a mutually exclusive, exhaustive 6-bucket ladder, so true probabilities
sum to exactly 1. Only two conditions are tradeable:

- **sum of asks < 100¢** → buy every bucket for less than the guaranteed $1 payout
- **sum of bids > 100¢** → sell every bucket for more than the $1 you must pay out

The sum of *mids* is a monitoring signal, not an opportunity — a mid is not a price
anyone trades at.

## How coherent are they?

**81,231 complete 6-bucket snapshots** across 12 cities, Jan–Sep 2026:

| | mean | median | p1 | p99 |
|---|---|---|---|---|
| sum of bids | 96.58 | 98.00 | 77.00 | 105.00 |
| sum of mids | 102.47 | 102.00 | 91.50 | 113.00 |
| sum of asks | 108.37 | 107.00 | 98.00 | 130.00 |

Bids sitting just under 100 and asks just over is exactly what bid/ask friction
predicts, applied six times. There is no systematic mispricing here.

## Executable gaps, after fees and realistic sizing

| | buy-side | sell-side |
|---|---|---|
| Gaps before fees | 1,154 (1.42% of snapshots) | 7,663 (9.43%) |
| Median raw gap | 2¢/ladder | 2¢/ladder |
| Median tradeable size (thinnest leg) | 15 contracts | 33 contracts |
| **Survives 6 taker legs** | **79 (6.8%)** | **343 (4.5%)** |
| Median surviving arb | **$0.29** | **$0.24** |
| Total (upper bound) | $341.82 | $177.64 |

**422 fee-surviving opportunities across 81,231 snapshots — 0.5%.**

## The headline total is an artifact

`$341.82` on the buy side is **61% attributable to three snapshots of one event**,
`KXHIGHPHIL-26MAY13`, where the six asks were `[1, 1, 10, 1, 1, 1]` — the entire
ladder offered at 15¢ for a guaranteed 100¢ payout. That is a stale or broken quote
during an illiquid moment, not a standing offer.

Only **14 snapshots out of 81,231** have sum-of-asks below 90¢, and 10 of those are
below 50¢. Strip them and the realistic picture is ~420 opportunities worth a median
of **$0.25 each** — roughly **$110 over nine months across twelve cities**, before
any competition for them.

And that is still an upper bound: it assumes top-of-book size is real, that all six
legs fill simultaneously at the quote, and that nobody else is racing for the same
gap. Every one of those assumptions moves the number down.

## Two bugs fixed in this script

Both produced badly wrong numbers on the first run:

1. **The sell-side payout was wrong by ~400¢ per ladder.** Selling the ladder means
   buying six NO contracts, and that basket pays out **500¢**, not 100¢ — five of six
   buckets settle NO. Treating it as 100¢ produced a suspiciously constant −402¢ on
   every sell-side gap, which is what exposed it.
2. **Sizing assumed a flat 100 lots per leg.** A six-leg capture is limited by its
   thinnest leg, and the median thinnest leg printed 15–33 contracts. Assuming 100
   isn't a proxy, it's fiction.

A third line — "survives as maker (100%)" — was removed as incoherent: capturing an
ask-side gap requires *taking*. A resting order is not lifting that offer.

## Verdict

Both edge mechanisms in the spec have now been tested against real prices:

| mechanism | result |
|---|---|
| Forecast edge, 24–48h (§2.2) | No detectable edge. −0.67% on 395 trades, t = +0.64 |
| Ladder coherence (§2.6) | ~$110/9 months realistic, dominated by stale quotes |

**Recommendation: stop.** Spec §8 is explicit that Phase 2 validates or kills the
premise. It has not validated it, and there is no third mechanism in the design to
fall back on.

What was actually learned is worth keeping:

- The market at 0–24h is unwinnable (it reads observations; we don't).
- At 24–48h the market is already efficient with respect to ECMWF-derived forecasts.
- Aggregate calibration does not survive adversarial selection — the model claimed
  +27.8 points of edge on selected trades and delivered +1.2.
- The ladders themselves are coherently priced.

Keep the basis logger and collectors running regardless: they cost nothing, the data
is unrecoverable if paused, and if the premise is revisited the accumulated
full-depth record is exactly what both backtests lacked.
