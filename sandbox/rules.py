"""The three sandbox arms -- implements docs/sandbox/*.md.

Those documents are the authority; any discrepancy is a bug here. One implementation
serves both the candle-based gates (scripts/sandbox_gates.py) and the live paper
accounts (sandbox/live.py), so the two cannot drift apart.

Times are offsets in hours from 00:00 UTC on the contract date D: -12 is D-1 12:00.
"""

import math
import os

import numpy as np

from src.fees import trade_fee_cents

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT, "config", "sandbox")

SERIES = "KXRAIN"
FEE_MULTIPLIER = 1.0
MARGIN = 0.03                 # main §3(f), unchanged
BAND = (5, 95)                # main §3(g), unchanged
TRIGGER_C = 10                # 03-move-trigger.md: |mid - ref| >= 10c

ARMS = {
    # checks: offsets (h) from D 00:00 UTC; snap_lead_s: live snapshot fetched this long
    # before each check (00-common.md §1, staggered around Gate 2's 23:51/23:56/00:00:30).
    "baseline": dict(checks=[0], snap_lead_s=150),
    "fixed":    dict(checks=[-12, -6, 0, 4], snap_lead_s=120),
    "trigger":  dict(checks=list(range(-12, 5)), snap_lead_s=90),
}


def frozen_path(arm):
    return os.path.join(CONFIG_DIR, f"{arm}_frozen.json")


# --------------------------------------------------------------------------- #
# Recalibration: p = sigmoid(a + b * logit(mid/100))

def logit(p):
    return math.log(p / (1 - p))


def sigmoid(z):
    return 1.0 / (1.0 + math.exp(-z))


def fit(points):
    """Maximum likelihood on [(mid_cents, y)], Newton from the identity."""
    x = np.array([logit(m / 100.0) for m, _ in points])
    y = np.array([v for _, v in points], dtype=float)
    X = np.column_stack([np.ones_like(x), x])
    w = np.array([0.0, 1.0])
    for _ in range(100):
        p = 1.0 / (1.0 + np.exp(-(X @ w)))
        H = -(X.T * (p * (1 - p))) @ X
        step = np.linalg.solve(H, X.T @ (y - p))
        w = w - step
        if np.max(np.abs(step)) < 1e-10:
            break
    return float(w[0]), float(w[1])


def curve(arm, params, offset):
    """(alpha, beta) the arm uses at a check offset."""
    if arm == "fixed":
        c = params["curves"][str(offset)]
        return c["alpha"], c["beta"]
    return params["alpha"], params["beta"]


def p_model(mid, a, b):
    return sigmoid(a + b * logit(mid / 100.0))


# --------------------------------------------------------------------------- #
# Entry rule, main §3(d)(f)(g): taker, margin, band

def decide(bid, ask, a, b):
    """(side, price_cents, fee_cents_per_contract) or None."""
    p = p_model((bid + ask) / 2.0, a, b)
    no_price = 100 - bid
    fee_yes = trade_fee_cents(1, ask, is_maker=False, fee_multiplier=FEE_MULTIPLIER)
    fee_no = trade_fee_cents(1, no_price, is_maker=False, fee_multiplier=FEE_MULTIPLIER)
    yes = BAND[0] <= ask <= BAND[1] and p - ask / 100.0 >= fee_yes / 100.0 + MARGIN
    no = BAND[0] <= no_price <= BAND[1] and \
        (1 - p) - no_price / 100.0 >= fee_no / 100.0 + MARGIN
    assert not (yes and no), "both sides qualify: impossible unless crossed"
    if yes:
        return "yes", ask, fee_yes
    if no:
        return "no", no_price, fee_no
    return None


def valid(bid, ask):
    """00-common.md §3: a missing, one-sided or crossed quote is no check."""
    return bid is not None and ask is not None and 0 < bid and ask < 100 and bid <= ask


# --------------------------------------------------------------------------- #
# The arms, as a pass over one market's observations

class Trigger:
    """03-move-trigger.md steps 1-4, one market. Feed valid grid points in time order."""

    def __init__(self, ref=None):
        self.ref = ref

    def observe(self, mid):
        """True if this grid point is an evaluation (never the anchor)."""
        if self.ref is None:
            self.ref = mid                      # step 2: anchor, no trade
            return False
        if abs(mid - self.ref) >= TRIGGER_C:    # step 3
            self.ref = mid
            return True
        return False


def evaluations(arm, obs):
    """Grid points at which the arm evaluates the market. `obs` = [(offset, bid, ask)]
    valid quotes only, in time order, restricted to the arm's check offsets. The set does
    not depend on the curve, so curves can be fit on it without circularity."""
    if arm != "trigger":
        return list(obs)
    trig, out = Trigger(), []
    for o in obs:
        if trig.observe((o[1] + o[2]) / 2.0):
            out.append(o)
    return out


def trade(arm, params, evals):
    """First evaluation where the entry rule qualifies (one position per market).
    Returns dict(offset, side, price, fee, bid, ask) or None."""
    for offset, bid, ask in evals:
        a, b = curve(arm, params, offset)
        d = decide(bid, ask, a, b)
        if d:
            return dict(offset=offset, side=d[0], price=d[1], fee=d[2], bid=bid, ask=ask)
    return None


def settle_pnl(t, y):
    won = (y == 1) if t["side"] == "yes" else (y == 0)
    return (100 if won else 0) - t["price"] - t["fee"]


def fit_params(arm, markets):
    """markets: [dict(evals=[...], y=0|1)]. Returns the arm's params dict."""
    if arm == "fixed":
        curves = {}
        for off in ARMS["fixed"]["checks"]:
            pts = [((o[1] + o[2]) / 2.0, m["y"]) for m in markets for o in m["evals"]
                   if o[0] == off]
            a, b = fit(pts)
            curves[str(off)] = dict(alpha=a, beta=b, n=len(pts))
        return dict(curves=curves)
    pts = [((o[1] + o[2]) / 2.0, m["y"]) for m in markets for o in m["evals"]]
    a, b = fit(pts)
    return dict(alpha=a, beta=b, n=len(pts))
