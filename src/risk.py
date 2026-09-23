"""Risk & Sizing gates (spec v3 section 2.3).

Hard gates run before sizing. Each returns a blocking reason or None, and a blocked
candidate is logged to `risk_events` rather than silently dropped -- every one of
these exists because something was measured, and the log is how we learn whether the
gate is still earning its place.

The gates are ordered cheapest-first, so an excluded station never reaches the
arithmetic.

## The three measurement-driven gates

**1. Station exclusion -- LAX and NYC.** Phase 2 calibration found the PIT failure
concentrated in coastal stations: KLAX KS 0.2910 (mean PIT 0.305), KNYC 0.2000,
against a 0.05 target. Excluding both moves pooled KS from 0.0893 to 0.0717. The
per-station bias correction is already applied, so what remains is **non-stationary**
marine bias that a rolling residual window does not track.

This is a HARD GATE, not a confidence weight. A soft down-weighting would still take
positions using probabilities known to be wrong, just smaller ones -- and being
miscalibrated at LAX means the errors are systematic, so smaller repeated bets lose
steadily rather than averaging out.

The cost is real and should not be soft-pedalled: **LAX is ~32% of watchlist volume**,
so this removes the deepest market. Revisit as a Tier 2 item (marine-layer feature, or
a much shorter residual window for coastal sites) once the economic backtest shows the
core edge is real on the other cities.

**2. Short-lead block -- 0-12h.** Phase 1 measured the market at 12/12 correct buckets
at 5-8h lead against the best forecast input's 4/12. The daily high has already
occurred; the market reads observations and we do not. Blocked for live trading until
the 24-48h edge is proven separately.

**3. Implausible-edge breaker.** A large edge against a confidently-priced market means
the model is broken, not that money is lying around. Atlanta 2026-09-22 settled at 86F
with the market at 99c on "<=86" while the gridpoint said 90F -- a naive model saw ~90
points of edge on a 1c contract that was a certain total loss. **The fee gate does not
catch this**: fees are trivial at 1c, so a fee-aware filter passes it straight through
and Kelly sizing on a 90-point edge would size it enormously.
"""

from . import fees

# Gate 1 -- see module docstring. Data loading is unaffected; these keep being scored.
EXCLUDED_STATIONS = {"KLAX", "KNYC"}
EXCLUSION_REASON = {
    "KLAX": "PIT KS 0.2910 (mean PIT 0.305) -- non-stationary marine bias",
    "KNYC": "PIT KS 0.2000 -- non-stationary marine bias",
}

# Gate 2
MIN_LEAD_HOURS = 12.0

# Gate 3
IMPLAUSIBLE_EDGE = 0.40          # probability points
CONFIDENT_MARKET_CENTS = 95      # a market at/above this is "confidently priced"

# Ordinary limits (section 2.3)
MAX_SPREAD_CENTS = 5
REQUIRED_MARGIN_CENTS = 2        # profit margin demanded above fees


class Blocked(Exception):
    """A candidate trade failed a hard gate."""

    def __init__(self, gate, reason):
        super().__init__(f"[{gate}] {reason}")
        self.gate = gate
        self.reason = reason


def check_station(nws_station):
    if nws_station in EXCLUDED_STATIONS:
        return ("station_excluded",
                f"{nws_station} excluded from sizing: "
                f"{EXCLUSION_REASON.get(nws_station, 'calibration failure')}")
    return None


def check_lead_time(lead_hours):
    if lead_hours is None:
        return ("short_lead", "lead time unknown")
    if lead_hours < MIN_LEAD_HOURS:
        return ("short_lead",
                f"lead {lead_hours:.1f}h below {MIN_LEAD_HOURS:.0f}h floor: the high is "
                f"likely already set and the market can see it")
    return None


def check_implausible_edge(edge, p_market_cents):
    if p_market_cents is None:
        return None
    confident = (p_market_cents >= CONFIDENT_MARKET_CENTS
                 or p_market_cents <= 100 - CONFIDENT_MARKET_CENTS)
    if abs(edge) >= IMPLAUSIBLE_EDGE and confident:
        return ("implausible_edge",
                f"edge {edge:+.2f} against a market at {p_market_cents}c indicates "
                f"model failure, not opportunity")
    return None


def check_spread(bid_cents, ask_cents, edge=None):
    if bid_cents is None or ask_cents is None:
        return ("no_quote", "no two-sided quote")
    spread = ask_cents - bid_cents
    if spread > MAX_SPREAD_CENTS:
        return ("spread", f"spread {spread}c exceeds {MAX_SPREAD_CENTS}c cap")
    if edge is not None and spread >= abs(edge) * 100:
        return ("spread", f"spread {spread}c exceeds the modeled edge "
                          f"{abs(edge)*100:.1f} points")
    return None


def check_fee_bar(edge, contracts, entry_cents, exit_cents, entry_is_maker,
                  exit_is_maker, fee_multiplier=1.0,
                  fee_type=fees.FEE_TYPE_TAKER_ONLY):
    """Section 2.3: edge must clear round-trip fees plus a required margin."""
    need = fees.min_edge_to_clear_fees(
        contracts, entry_cents, exit_cents, entry_is_maker, exit_is_maker,
        REQUIRED_MARGIN_CENTS, fee_multiplier, fee_type)
    if abs(edge) < need:
        return ("fee_bar",
                f"edge {abs(edge)*100:.2f} points below the "
                f"{need*100:.2f}-point round-trip bar")
    return None


def gate(candidate):
    """Run every hard gate. Returns a list of (gate, reason); empty means clear.

    candidate keys: nws_station, lead_hours, edge, p_market_cents, bid_cents,
    ask_cents, contracts, entry_cents, exit_cents, entry_is_maker, exit_is_maker,
    fee_multiplier, fee_type.
    """
    c = candidate
    checks = [
        check_station(c.get("nws_station")),
        check_lead_time(c.get("lead_hours")),
        check_implausible_edge(c.get("edge", 0.0), c.get("p_market_cents")),
        check_spread(c.get("bid_cents"), c.get("ask_cents"), c.get("edge")),
        check_fee_bar(
            c.get("edge", 0.0), c.get("contracts", 1),
            c.get("entry_cents"), c.get("exit_cents"),
            c.get("entry_is_maker", True), c.get("exit_is_maker", True),
            c.get("fee_multiplier", 1.0),
            c.get("fee_type", fees.FEE_TYPE_TAKER_ONLY),
        ) if c.get("entry_cents") is not None else None,
    ]
    return [x for x in checks if x]


def log_block(conn, blocks, ticker, mode="simulation", detail=None):
    """Record blocked candidates so the gates can be audited (section 2.5)."""
    import json as _json
    from . import db
    for gate_name, reason in blocks:
        conn.execute(
            "INSERT INTO risk_events (occurred_at, mode, kind, ticker, reason, detail_json) "
            "VALUES (?,?,?,?,?,?)",
            (db.utcnow(), mode, "blocked_trade", ticker, f"{gate_name}: {reason}",
             _json.dumps(detail) if detail else None))
    conn.commit()


if __name__ == "__main__":
    print("Hard gates (spec v3 section 2.3)\n")
    cases = [
        ("LAX, clean signal otherwise", dict(
            nws_station="KLAX", lead_hours=36, edge=0.08, p_market_cents=40,
            bid_cents=39, ask_cents=41, contracts=100, entry_cents=40)),
        ("Chicago, 36h, good edge", dict(
            nws_station="KMDW", lead_hours=36, edge=0.08, p_market_cents=40,
            bid_cents=39, ask_cents=41, contracts=100, entry_cents=40)),
        ("Chicago, 5h lead", dict(
            nws_station="KMDW", lead_hours=5, edge=0.08, p_market_cents=40,
            bid_cents=39, ask_cents=41, contracts=100, entry_cents=40)),
        ("Atlanta 2026-09-22 replay", dict(
            nws_station="KATL", lead_hours=30, edge=0.90, p_market_cents=1,
            bid_cents=0, ask_cents=1, contracts=100, entry_cents=1)),
        ("Wide spread", dict(
            nws_station="KMDW", lead_hours=36, edge=0.08, p_market_cents=40,
            bid_cents=36, ask_cents=44, contracts=100, entry_cents=40)),
        ("Thin edge vs taker fees", dict(
            nws_station="KMDW", lead_hours=36, edge=0.01, p_market_cents=50,
            bid_cents=49, ask_cents=51, contracts=100, entry_cents=50,
            exit_cents=50, entry_is_maker=False, exit_is_maker=False)),
    ]
    for label, c in cases:
        blocks = gate(c)
        if blocks:
            print(f"  BLOCKED  {label}")
            for g, r in blocks:
                print(f"           -> [{g}] {r}")
        else:
            print(f"  ALLOWED  {label}")
    print("\nStation exclusions:", ", ".join(sorted(EXCLUDED_STATIONS)))
    print("These are sizing gates only -- both stations keep being loaded and scored.")
