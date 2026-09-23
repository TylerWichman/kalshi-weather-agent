"""Maker fill simulation (spec v3 sections 2.4, 2.3).

Maker fees are $0 for weather (section 3), so the strategy rests orders by default
and **fill probability, not fee, is the binding constraint.** That makes this module
the most assumption-laden part of the backtest, so the assumptions are stated here
rather than buried.

## THE QUEUE-POSITION ASSUMPTION -- unvalidated, deliberately conservative

**Queue position is not observable in any Kalshi historical data available to us.**

- Candlesticks give bid/ask OHLC, traded price OHLC and volume per period. They do
  not give resting size, let alone where in the queue an order sits.
- Trade prints (post-cutoff only) give price, size and which side took. They do not
  give how many contracts rested ahead of ours at that price.
- The live pipeline captures full book depth, but only from 2026-09-22 forward.

So every maker fill in this backtest rests on an assumption. Three conservative
choices, each biasing *against* the strategy:

1. **Trade-through required, not trade-at.** A resting YES buy at P fills only if the
   market traded strictly BELOW P. Trading exactly at P may only have consumed the
   queue ahead of us. This is the single most important conservatism: on a 1c-tick
   market, "at" versus "through" is the difference between assuming front-of-queue
   and assuming back-of-queue.
2. **Participation cap.** Even on a trade-through we take at most
   `MAX_PARTICIPATION` (default 10%) of that period's volume, so the simulation
   cannot fill size the market never printed.
3. **No queue credit across periods.** Resting through a quiet period earns no
   improved position; each period is judged on its own.

**What this is NOT:** a claim that these are the true fill dynamics. A resting order
that never fills costs nothing but also earns nothing, and one that fills only on
adverse moves is the adverse-selection cost section 2.3 requires be measured. The
conservative rule above understates fill rate, which *flatters* nothing -- but it
cannot capture adverse selection, which flatters the strategy.

**Validation required before Phase 6.** The live pipeline records full depth every
15 minutes. Phase 5.5 must compare realized maker fills against what this module
predicts and report both fill rate and adverse selection (fill price versus mid at
fill time). Until that happens, any P&L from this module carries the caveat.

## Taker fills

A taker fill is simulated at the quoted opposing side (ask for a buy, bid for a
sell) and charged the taker fee from `src/fees.py`. Taker fills are assumed to
always fill, capped by participation, which is optimistic in thin books -- another
reason the spread and depth gates in `src/risk.py` exist.
"""

from . import fees

MAX_PARTICIPATION = 0.10     # of a period's printed volume
REQUIRE_TRADE_THROUGH = True


class Fill:
    __slots__ = ("filled", "contracts", "price_cents", "fee_cents", "is_maker", "reason")

    def __init__(self, filled, contracts=0, price_cents=None, fee_cents=0,
                 is_maker=True, reason=""):
        self.filled = filled
        self.contracts = contracts
        self.price_cents = price_cents
        self.fee_cents = fee_cents
        self.is_maker = is_maker
        self.reason = reason

    def __repr__(self):
        if not self.filled:
            return f"<no fill: {self.reason}>"
        kind = "maker" if self.is_maker else "taker"
        return (f"<{kind} {self.contracts}@{self.price_cents}c "
                f"fee={self.fee_cents}c>")


def simulate_maker(candle, side, limit_cents, want_contracts,
                   fee_multiplier=1.0, fee_type=fees.FEE_TYPE_TAKER_ONLY):
    """Would a resting limit order have filled during this candle period?

    candle          dict with price_low, price_high, volume (cents / contracts)
    side            'buy_yes' or 'sell_yes'
    limit_cents     our resting price
    want_contracts  desired size

    Returns a Fill. Maker fee is $0 for weather, asserted via src/fees.py.
    """
    vol = float(candle.get("volume") or 0)
    if vol <= 0:
        return Fill(False, reason="no volume in period")

    lo, hi = candle.get("price_low"), candle.get("price_high")
    if lo is None or hi is None:
        return Fill(False, reason="no traded prices in period")

    if side == "buy_yes":
        # Someone must have sold through our bid.
        crossed = lo < limit_cents if REQUIRE_TRADE_THROUGH else lo <= limit_cents
    elif side == "sell_yes":
        crossed = hi > limit_cents if REQUIRE_TRADE_THROUGH else hi >= limit_cents
    else:
        raise ValueError(f"bad side {side!r}")

    if not crossed:
        rule = "through" if REQUIRE_TRADE_THROUGH else "at"
        return Fill(False, reason=f"market did not trade {rule} {limit_cents}c")

    contracts = int(min(want_contracts, vol * MAX_PARTICIPATION))
    if contracts <= 0:
        return Fill(False, reason=f"participation cap: {vol:.0f} printed")

    fee = fees.trade_fee_cents(contracts, limit_cents, is_maker=True,
                               fee_multiplier=fee_multiplier, fee_type=fee_type)
    return Fill(True, contracts, limit_cents, fee, True, "trade-through")


def simulate_taker(candle, side, want_contracts,
                   fee_multiplier=1.0, fee_type=fees.FEE_TYPE_TAKER_ONLY,
                   max_slippage_cents=None):
    """Cross the spread. Fills at the quoted opposing side, pays the taker fee."""
    price = candle.get("yes_ask_close") if side == "buy_yes" else candle.get("yes_bid_close")
    if price is None:
        return Fill(False, reason="no quote on the opposing side")

    if max_slippage_cents is not None:
        bid, ask = candle.get("yes_bid_close"), candle.get("yes_ask_close")
        if bid is not None and ask is not None and (ask - bid) > max_slippage_cents:
            return Fill(False, reason=f"spread {ask-bid}c exceeds tolerance")

    vol = float(candle.get("volume") or 0)
    contracts = int(min(want_contracts, max(vol, 1) * MAX_PARTICIPATION))
    if contracts <= 0:
        return Fill(False, reason="participation cap")

    fee = fees.trade_fee_cents(contracts, price, is_maker=False,
                               fee_multiplier=fee_multiplier, fee_type=fee_type)
    return Fill(True, contracts, price, fee, False, "crossed spread")


def assumptions():
    """Machine-readable record of what the simulation assumed, for the report."""
    return {
        "queue_position": "UNOBSERVABLE -- not in candles, trades, or any historical feed",
        "maker_rule": ("trade-through required" if REQUIRE_TRADE_THROUGH
                       else "trade-at sufficient"),
        "max_participation": MAX_PARTICIPATION,
        "queue_credit_across_periods": False,
        "adverse_selection_modeled": False,
        "validation_status": "UNVALIDATED -- requires Phase 5.5 live comparison",
        "bias": "conservative on fill rate; silent on adverse selection",
    }
