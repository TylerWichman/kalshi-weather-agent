# Crypto 15m market-making test: pre-registration

Written 2026-11-21, before any ETH/SOL trade-tape data had been simulated. Code:
`crypto15m/maker.py`. Nothing below may change after the first train run; any change is
a new amendment with its own date and its own multiple-testing count.

## Question

Can a passive two-sided quoter on KXETH15M / KXSOL15M earn more than it loses to adverse
selection and fees?

## Data

The public trade tape of each settled window (`trade_blobs`: time to the millisecond,
YES price, size, taker side), ETH and SOL only, every settled window with trades from about Sept 15 to Nov 21 2026.
(Corrected before any run: an earlier draft said Oct 10 and ~40-day retention, a wrong
reading of the empty pre-launch windows.) Splits use the same ticker hash as every earlier test: **test = sha256(ticker) <
0.30, never yet scored**; validation 0.30–0.45; train >= 0.45. Strategies don't use
cross-coin features, so a per-ticker split is leakage-safe here.

## Strategy (per window, every 10 seconds from minute 1 to the stop minute)

1. Estimate the book from the tape: best bid = price of the last trade that hit the
   bid (taker bought NO) in the past 30 s; best ask = price of the last trade that lifted
   the ask (taker bought YES) in the past 30 s. Skip the step if either is missing.
2. Quote only if bid >= 0.10 and ask <= 0.90.
3. Quote price: **improve** = bid + 1c / ask - 1c, falling back to joining if that would
   cross; **join** = at bid / at ask.
4. Size 10 contracts each side per step; net position capped at ±50 YES; at the cap only
   the side that reduces it is quoted.
5. **Fill rule (conservative):** our bid at p fills only if, within the next 10 s, a
   trade hits the bid at a price **strictly below p**, so a seller went through our
   price. Fill size = min(remaining quote, that trade's size). The ask side mirrors this. Trades
   exactly at our price count as not filled, since queue position is unknown.
6. After the stop minute no new quotes; inventory is held to settlement ($1 / $0).
7. **Fees:** maker fee 0.0175·P·(1−P) per contract filled. This is an assumption, because
   the maker fee on these series must be checked against the account's fee schedule
   before any live trading. A zero-fee line is reported for context only, never for decisions.

## Variants: exactly 4

stop minute ∈ {8, 12} × quote ∈ {improve, join}.

## Decision rule

- Train: report all 4. No selection on train; all 4 go to validation.
- Validation: a variant passes if mean P&L per window > 0 with **both** the window-level
  and the day-block bootstrap 95% CI lower bounds > 0, after Bonferroni for 4 (alpha
  0.0125), with >= 300 windows quoted.
- Test (once): at most 2 passing variants, same criteria with Bonferroni for the number
  carried. **GO** = at least one passes on test.
- GO leads to 2 weeks of live paper trading on the collector's 1-second books before any
  real order. NO-GO on all 4 retires passive quoting at this specification.

## Known limits

- Our own quotes would change other traders' behavior; the simulation can't see that.
- A 30-second tape-based book estimate is cruder than the real book. The 1-second
  order-book data from the collector (from 2026-11-21) allows a sharper re-test later,
  as a new amendment.
