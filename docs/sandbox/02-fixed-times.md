# Sandbox arm 2: `fixed` (four fixed check times)

Pre-registered 2026-09-25, together with `00-common.md`, whose rules all apply here.

## Mechanism

The same definitional mismatch as the main pre-registration §2. The claim here is that
**the mismatch depends on lead time.** The day before, a consumer app shows its least
specific product: a daily icon and a daytime percentage chance of rain. Retail money
priced from that is most exposed to the window and trace mismatches. Closer to the day,
better-specified forecasts and better-informed traders arrive. So the market's miscalibration
should be at least as large the day before as at 00:00 UTC. Checking at several fixed leads
catches a mispricing when it is largest, and does not see it only after it has closed.

What would make this false: the curves fitted at the earlier times sit on the identity (the
market is already calibrated the day before), or the earlier checks' trades lose money on
their own (criterion 5 below).

## Rule

- **Check times** (UTC; D = contract date): **D−1 12:00, D−1 18:00, D 00:00, D 04:00.**
  All four come before any climate day begins (`00-common.md` §3). They are fixed here and
  are not chosen from data.
- **One recalibration curve per check time**, `p_t = σ(α_t + β_t·logit(mid/100))`, which
  is 8 parameters in all. Each is fit by maximum likelihood on every development market with
  a two-sided quote at that time, whether or not a position would be held by then.
- **Order.** The checks run in time order. At each check, a market with no position yet is
  tested with the main §3(f)–(g) entry rule, using that check's curve and that check's
  candle. **The first check that qualifies takes the trade.** No later check touches that
  market again.
- Margin 3¢, band 5–95¢, taker fee, held to settlement: all unchanged.

## Development gate (`00-common.md` §5)

Leave one calendar week out. Fit the four curves on the other weeks and run the sequential
rule on the held-out week. **Out-of-fold mean net per contract ≤ 0 is NO-GO**, and the arm
is not run forward. Otherwise refit on all development days, freeze the 8 parameters and the
traded sides in `config/sandbox/fixed_frozen.json`, and commit before 2026-09-29 12:00 UTC.

## Arm-specific mechanism check (added to criterion 5)

The arm must not be the baseline in disguise. Both of these must hold on the test:

- trades taken at checks **other than D 00:00** make up **at least 30%** of the arm's
  trades, **and**
- those trades have **mean net > 0 on their own**.

## Reported for diagnosis, never for the decision

Trades and mean net per contract for each check time. The fitted (α_t, β_t) set against the
identity, which shows how the calibration gap changes with lead time. Both are labelled
thin.
