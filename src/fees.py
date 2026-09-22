"""Fee calculation (spec v3 section 3).

Section 3 requires this be a first-class function called before every trade
decision, real or simulated -- never a static assumption baked into a backtest.

## Confirmed 2026-09-22

Taker fee, from Kalshi's published fee schedule:

    fee = ceil_to_cent(0.07 * contracts * price * (1 - price))

Quadratic in price, so it peaks at 50c (1.75c/contract, ~3.5% of cost) and falls
toward the extremes (~0.63c/contract, ~0.7% near 10c/90c). That peak is the natural
maximum of the parabola, not a separate cap.

**Maker fee is $0 for weather.** Confirmed two independent ways:

1. Kalshi's fee schedule lists no maker fee for "Most markets", which weather is.
   The 50%-of-taker maker rate applies only to Combos.
2. The API encodes this as a `fee_type` enum with exactly two values. Weather is
   **409 of 409** series on plain `quadratic`; `quadratic_with_maker_fees` appears
   only on 34 Financials and 10 Economics series (CPI, Fed, GDP, GPU pricing).
   Weather: **0 of 409.**

That is positive confirmation, not merely an absent field -- the distinction exists
in the API and weather is explicitly on the non-maker side of it.

## Consequence, and its limit

Resting orders are free. Taker fees are the entire transaction cost, so a maker fill
costs nothing and maker-only execution is the default (section 2.3).

But **free is not costless**, and the model must not confuse the two:

- **Adverse selection.** A resting order fills preferentially when the market moves
  against it -- you get hit precisely when you were wrong. This implicit cost is
  real and can exceed a taker fee. It is not in any fee schedule.
- **Non-fill risk.** The edge can evaporate before the order fills, which converts a
  good trade into no trade, or worse, leaves one leg of a ladder position filled.

So maker-preference is a strong default, not a free lunch. Section 2.3 keeps the
taker escape hatch for genuinely large, fast-moving edges.

## Guard

`fee_type` and `fee_multiplier` are read from `/series` and stored per contract. If
Kalshi ever moves a weather series to `quadratic_with_maker_fees`, the maker-only
strategy's core economics change silently. `assert_no_maker_fee()` exists to make
that loud.
"""

import math

# From Kalshi's published fee schedule. Kept as a named constant rather than a
# literal so there is exactly one place to change it if the schedule moves.
TAKER_COEFFICIENT = 0.07

FEE_TYPE_TAKER_ONLY = "quadratic"
FEE_TYPE_WITH_MAKER = "quadratic_with_maker_fees"


class FeeScheduleChanged(Exception):
    """A watchlist series is no longer on the taker-only fee schedule."""


def assert_no_maker_fee(fee_type, ticker=""):
    """Raise if a series has moved onto the maker-fee schedule.

    Called during contract discovery. The maker-only execution strategy assumes
    resting orders are free; if that stops being true it must not fail quietly.
    """
    if fee_type == FEE_TYPE_WITH_MAKER:
        raise FeeScheduleChanged(
            f"{ticker}: fee_type is now {FEE_TYPE_WITH_MAKER!r}. Maker orders are no "
            f"longer free and the maker-preference logic in section 2.3 must be "
            f"re-derived before trading this series."
        )
    if fee_type not in (FEE_TYPE_TAKER_ONLY, None):
        raise FeeScheduleChanged(f"{ticker}: unrecognized fee_type {fee_type!r}")


def trade_fee_cents(contracts, price_cents, is_maker, fee_multiplier=1.0,
                    fee_type=FEE_TYPE_TAKER_ONLY):
    """Fee in whole cents for one order.

    contracts     -- number of contracts
    price_cents   -- execution price, 1..99
    is_maker      -- True for a resting limit order that provided liquidity
    fee_multiplier-- per-series, read from /series (never hardcoded)
    fee_type      -- per-series, read from /series

    Returns an integer number of cents, rounded up, as Kalshi charges it.
    """
    if contracts <= 0:
        return 0
    if not 0 < price_cents < 100:
        # A contract at 0 or 100 has no fee because it has no uncertainty left.
        return 0

    if is_maker and fee_type == FEE_TYPE_TAKER_ONLY:
        return 0  # Confirmed $0 for weather.
    if is_maker and fee_type == FEE_TYPE_WITH_MAKER:
        raise FeeScheduleChanged(
            "maker fee schedule applies to this series; rate not modeled here"
        )

    p = price_cents / 100.0
    dollars = TAKER_COEFFICIENT * fee_multiplier * contracts * p * (1.0 - p)
    return int(math.ceil(dollars * 100.0 - 1e-9))


def round_trip_fee_cents(contracts, entry_price_cents, exit_price_cents,
                         entry_is_maker, exit_is_maker,
                         fee_multiplier=1.0, fee_type=FEE_TYPE_TAKER_ONLY):
    """Total fee for entering and later exiting a position (section 2.3).

    Holding to resolution rather than exiting costs no exit fee: settlement is not
    a trade. Pass exit_price_cents=None for that case.
    """
    total = trade_fee_cents(contracts, entry_price_cents, entry_is_maker,
                            fee_multiplier, fee_type)
    if exit_price_cents is not None:
        total += trade_fee_cents(contracts, exit_price_cents, exit_is_maker,
                                 fee_multiplier, fee_type)
    return total


def min_edge_to_clear_fees(contracts, entry_price_cents, exit_price_cents,
                           entry_is_maker, exit_is_maker, required_margin_cents=0,
                           fee_multiplier=1.0, fee_type=FEE_TYPE_TAKER_ONLY):
    """Minimum edge, in probability points, for a trade to be worth doing.

    Section 2.3 requires this be computed per trade rather than fixed: because the
    fee is quadratic in price, the bar near 50c is several times the bar near the
    extremes. Returns probability points (0..1), not cents.
    """
    fee = round_trip_fee_cents(contracts, entry_price_cents, exit_price_cents,
                               entry_is_maker, exit_is_maker, fee_multiplier, fee_type)
    return (fee + required_margin_cents) / (100.0 * contracts)


def fee_table(contracts=100):
    """Taker cost across the price range -- the shape section 3 describes."""
    rows = []
    for p in (1, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99):
        taker = trade_fee_cents(contracts, p, is_maker=False)
        maker = trade_fee_cents(contracts, p, is_maker=True)
        cost = contracts * p
        rows.append((p, taker, maker, 100.0 * taker / cost if cost else 0.0))
    return rows


if __name__ == "__main__":
    n = 100
    print(f"Fee per {n}-contract order (weather: fee_type=quadratic, multiplier=1)\n")
    print(f"{'price':>6}{'taker (c)':>11}{'maker (c)':>11}{'taker % of cost':>18}")
    print("-" * 46)
    for p, taker, maker, pct in fee_table(n):
        print(f"{p:>5}c{taker:>11}{maker:>11}{pct:>17.2f}%")
    print("\nMaker is $0 at every price -- confirmed via fee schedule and the API's")
    print("fee_type enum (weather: 409/409 on plain 'quadratic').")
    print("\nRound-trip taker at 50c on 100 contracts:",
          round_trip_fee_cents(100, 50, 50, False, False), "cents")
    print("Round-trip maker/maker, same trade:      ",
          round_trip_fee_cents(100, 50, 50, True, True), "cents")
    print("\nMin edge to clear fees (100 contracts, enter+exit at 50c):")
    print(f"  taker/taker: {min_edge_to_clear_fees(100,50,50,False,False)*100:.2f} points")
    print(f"  maker/maker: {min_edge_to_clear_fees(100,50,50,True,True)*100:.2f} points")
    print(f"  maker/taker: {min_edge_to_clear_fees(100,50,50,True,False)*100:.2f} points")
