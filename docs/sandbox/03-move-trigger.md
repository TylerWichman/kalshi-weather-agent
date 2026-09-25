# Sandbox arm 3: `trigger` (evaluate a market only after its price moves)

Pre-registered 2026-09-25, together with `00-common.md`, whose rules all apply here.

This is **not** "trade wherever it looks good." The arm evaluates a market only at a
precisely defined event: its mid has moved **at least 10¢ since that market's last
evaluation**, observed on a fixed hourly grid. Between those events it does nothing.

## Mechanism

The definitional mismatch of the main pre-registration §2 enters the price when retail
money reprices. Retail reprices when the consumer forecast it reads changes. Consumer
forecasts update in steps after each new model cycle, so retail repricing shows up as
**large, discrete moves in the mid.** The claim is that **right after such a move the price
carries a fresh, larger dose of the mismatch** than it does at a quiet time, because the
move was made by the participants whose forecasts do not match the contract. A curve fitted
at move moments should therefore depart from the identity more than the 00:00 UTC curve
does, and trades at those moments should be profitable.

The rival explanation is that large moves are informed (new information, correctly
priced). Then the curve fitted at move moments sits on the identity and the arm finds
nothing. The test decides between the two.

## Rule, stated exactly

For each market (D = contract date, all times UTC):

1. **Grid.** The hourly candle closes at D−1 12:00, 13:00, …, 23:00, D 00:00, …, 04:00.
   That is 17 grid points, all before the climate day begins. A grid point where the
   market has no candle, or a one-sided or crossed quote, is **skipped**: it is neither a
   check nor a reference.
2. **Anchor.** The first valid grid point sets the reference `ref = mid`. **No trade can
   be taken at the anchor.**
3. **Trigger.** At each later valid grid point, if `|mid − ref| ≥ 10¢`, this is an
   **evaluation**: set `ref = mid`. If the market has no position, apply the main §3(f)–(g)
   entry rule at this candle using the arm's curve. If the move is below 10¢, nothing
   happens and `ref` is kept.
4. **One position per market.** After a trade, later triggers still update `ref`, but they
   trade nothing.
5. Margin 3¢, band 5–95¢, taker fee, held to settlement: all unchanged.

The threshold (10¢), the grid (hourly, D−1 12:00 to D 04:00) and the anchor rule are fixed
here and are **not tuned.** 10¢ is chosen to sit well above the 1–2¢ jitter that a spread
change alone produces in the mid.

**Recalibration.** One curve, `p = σ(α + β·logit(mid/100))`, fit by maximum likelihood on
**every evaluation point** in the development set (step 3), including those in markets
already held.

## Development gate (`00-common.md` §5)

Leave one calendar week out. Fit the curve on the other weeks' evaluation points and run the
rule on the held-out week. **Out-of-fold mean net per contract ≤ 0 is NO-GO**, and the arm
is not run forward. Otherwise refit on all development days, freeze α, β and the traded
sides in `config/sandbox/trigger_frozen.json`, and commit before 2026-09-29 12:00 UTC.

The development gate also reports the number of evaluation points and trades. If it
produces fewer than 50 out-of-fold trades, that is reported as a warning that criterion 2
(≥ 100 test trades) is unlikely to be met. **It does not change the rule.**

## Live trading uses the same rule

In the paper account, the grid point is the book snapshot taken 90 s before each hour, and
the mid is computed from its best bid and ask. The paper account keeps its own `ref` per
market. A missed hour is skipped, exactly as in step 1. The verdict uses candles, so the
paper account's `ref` path can differ slightly. That affects only the display.

## Arm-specific mechanism check (added to criterion 5)

None beyond the common one. Every trade is at a trigger by construction.

## Reported for diagnosis, never for the decision

Evaluation points and trades per test day. Trades split by the direction of the move
(up or down) and by hour. The fitted curve set against the identity and against the
baseline curve. All labelled thin.
