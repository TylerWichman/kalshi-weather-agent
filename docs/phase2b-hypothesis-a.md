# Hypothesis A — Market Making: **NO-GO** (the mechanism is falsified)

Run 2026-09-23. Reproduce: `python scripts/marketmake.py`.

**The pre-registered test returns GO on net P&L. The decomposition falsifies the
hypothesis anyway.** Both statements are true and the second one governs.

Universe: 10 of 12 cities. LAX and NYC stay hard-gated (~17% of ladder-days,
**~43% of watchlist volume**).

## The pre-registered result (§1.3)

| | |
|---|---|
| Ladder-days traded | 1,036 |
| Total fills | 107,151 |
| Fees paid | **$0.00** |
| **Net P&L** | **+$37,100** |
| Mean per ladder-day | **+$35.81** |
| 95% CI | **[+$32.61, +$39.01]** |
| t-statistic | +21.93 |

CI excludes zero. By the letter of §1.3 that is a GO, and it is stable across folds
(+$41.13, +$33.72, +$31.45, +$35.05 per ladder-day).

## Why it is not a GO for *this* hypothesis

§1.1 defines the mechanism precisely: earn the bid-ask spread **without needing to be
right about the weather**. Decompose the P&L against that definition:

| component | P&L |
|---|---|
| **Spread capture (cash from round-trips)** | **−$51,150** |
| Settlement of residual inventory | **+$88,250** |
| Net | +$37,100 |

**Spread capture loses money.** Every cent of profit comes from holding one-sided
inventory to resolution — which is the directional bet the hypothesis was explicitly
designed to avoid, and which §1.2 identified as the risk the inventory controls exist
to prevent.

Median residual inventory at settlement: **306 contracts**. That is a position, not a
market-making book.

## Root cause: the ladder makes two-sided quoting structurally impossible

A resting bid at 1¢ can only fill if the market trades *below* 1¢, which cannot
happen. On a 6-bucket ladder most buckets sit at a few cents, so on those buckets the
strategy can only ever **sell**.

Measured over 300 ladders with inventory limits removed:

| fill price | buy contracts | sell contracts |
|---|---|---|
| 1–5¢ | 126,429 | **208,816** |
| 6–15¢ | 173,165 | 230,711 |
| 16–40¢ | 274,728 | 304,384 |
| 41–60¢ | 152,103 | 159,425 |
| 61–99¢ | 115,247 | 88,051 |
| **total** | 841,672 | **991,387 (1.18×)** |

The book fills asymmetrically by construction, so inventory accumulates short the
cheap tails. Cheap tails usually settle NO. The "edge" is selling out-of-the-money
options and collecting premium.

## Adverse selection, measured

§2.3 required this be measured rather than assumed, and it does not have to wait for
Phase 5.5 — historical candles can price it even though queue position cannot be
observed:

| | |
|---|---|
| Fills measured | 102,225 |
| Mean mid-move after a fill | **−0.0898¢** (against us) |
| Share adverse | 44.8% |

A ~0.09¢ average adverse move against a median 1.8¢ spread consumes roughly a tenth
of the gross spread per fill — and that is enough, compounded over 107,151 fills, to
turn spread capture negative. **This is the direct measurement of the cost that
`src/fillsim.py` cannot model, and it is the thing that kills the mechanism.**

## Tail risk (§1.3 — visible, not averaged away)

| percentile | P&L per ladder-day |
|---|---|
| p1 | −$104.99 |
| p5 | −$58.86 |
| median | +$42.57 |
| p95 | +$113.44 |
| p99 | +$150.73 |
| worst | −$182.96 |

Losing ladder-days: 237 of 1,036 (22.9%). Max one-sided inventory: median 128, max 149
contracts (the caps bind).

This is the classic short-volatility profile — frequent small gains, occasional larger
losses — and the sample is **nine months with no extreme weather event in it**. The
loss that defines this strategy's risk is very likely not in the data.

## Verdict

**NO-GO on Hypothesis A as specified.** The mechanism — spread capture independent of
directional views — is falsified: it lost $51,150, and adverse selection is the
measured reason.

§4 says do not loosen a rule after a negative result. The symmetric obligation applies
here: **do not accept a positive number produced by a mechanism other than the one
pre-registered.** Reporting +$37,100 as "market making works" would be exactly the
error this project has avoided four times now.

## The incidental finding, and why it should not be adopted yet

Systematically selling the cheap tails of these ladders was profitable in-sample, with
stable fold-to-fold returns. That is a **different hypothesis** with a different risk
profile, and it was not pre-registered. Before it could be taken seriously it needs:

1. Its own pre-registration with a go/no-go rule fixed in advance.
2. A sample containing at least one genuine tail event — a surprise heat wave or cold
   snap that sends an unlikely bucket to settlement. Nine calm months cannot price
   that risk, and short-volatility strategies are precisely the ones that look
   excellent until the day they do not.
3. Honesty that it is not the day-trading system in the original spec. It is
   premium-selling on weather ladders, held to resolution.

It also rests entirely on the unvalidated queue assumption (§1.4), and — per that same
section — market making is *more* queue-sensitive than the directional test was, so
this evidence is weaker still.

## Status after Phase 2b

| mechanism | result |
|---|---|
| Forecast edge 24–48h (v3 §2.2) | No detectable edge |
| Ladder coherence (v3 §2.6) | ~$110/9mo, stale-quote artifacts |
| Stale-quote detection (2b §2) | ~$30/9mo, windows close in 2 min |
| Market making (2b §1) | Spread capture −$51,150; mechanism falsified |

Four mechanisms tested against real historical prices. None supports the premise.
