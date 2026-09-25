"""RETROSPECTIVE HISTORICAL CHECK -- diagnostic only.

Not a pre-registered hypothesis, not a forward test, and not evidence for or against
Gate 2 or any sandbox arm. September's aggregate numbers had already been looked at
(monthly breakdown, 2026-09-25) before this was run.

Fit each rule's recalibration on Jul 15 - Aug 31 only, freeze it, then run Sep 1 - 23
one day at a time. A day's decision uses only that day's own quotes at its check times
and the frozen parameters; nothing from later September days is visible to it.
Read-only use of data/sandbox.sqlite (the development copy). Sep 24-26 are Gate 2's
embargo days and are not used.

    python scripts/retro_check.py OUTDIR    # writes OUTDIR/retro.json
Results as run on 2026-09-25: docs/retro/2026-09-25-results.json.
"""
import json
import sys
from collections import defaultdict
from datetime import date

import numpy as np

sys.path.insert(0, ".")
sys.path.insert(0, "scripts")
import sandbox_gates as G                         # noqa: E402
from sandbox import rules as R                    # noqa: E402
from src.fees import trade_fee_cents              # noqa: E402

OUT = sys.argv[1]
TRAIN = (date(2026, 7, 15), date(2026, 8, 31))
TEST = (date(2026, 9, 1), date(2026, 9, 23))
RULES = {  # label -> arm structure in sandbox/rules.py
    "gate2": ("baseline", "Gate 2 rule (once daily, 8 PM ET)"),
    "baseline": ("baseline", "Arm 1: baseline (same rule as Gate 2)"),
    "fixed": ("fixed", "Arm 2: fixed times"),
    "trigger": ("trigger", "Arm 3: move trigger"),
}
week = lambda d: d.isocalendar()[:2]
c = G.connect()


def stats(trades):
    if not trades:
        return dict(n=0)
    pnl = [t["pnl"] for t in trades]
    lo, hi = G.trade_ci(trades, 0.95)
    return dict(n=len(trades), days=len({t["day"] for t in trades}), mean=round(float(np.mean(pnl)), 2),
                lo=round(lo, 2), hi=round(hi, 2), total=round(sum(pnl) / 100, 2),
                won=round(float(np.mean([p > 0 for p in pnl])), 3))


def sized_account(trades, test_days):
    """$100 account through September, sequential: <= $5 per trade incl. fee from cash on
    hand; a rain day's cash returns the morning after it (two rounds of buying later)."""
    by = defaultdict(list)
    for t in trades:
        by[t["day"]].append(t)
    cash, queue, path = 10_000, [0, 0], []
    for d in test_days:
        cash += queue.pop(0)
        payout = spent = 0
        for t in sorted(by.get(d, []), key=lambda x: x["offset"]):
            k = min(100, min(500, cash) // t["price"])
            while k > 0 and t["price"] * k + trade_fee_cents(k, t["price"], is_maker=False) > min(500, cash):
                k -= 1
            if k < 1:
                continue
            cost = t["price"] * k + trade_fee_cents(k, t["price"], is_maker=False)
            cash -= cost
            spent += cost
            payout += 100 * k if t["pnl"] > 0 else 0
        queue.append(payout)
        path.append(dict(day=str(d), settled=round((cash + sum(queue)) / 100, 2)))
    return path


out = dict(train=[str(x) for x in TRAIN], test=[str(x) for x in TEST], rules={})
for key, (arm, label) in RULES.items():
    if key == "baseline":          # identical to gate2 by construction; reported once, reused
        out["rules"][key] = dict(out["rules"]["gate2"], label=label, same_as="gate2")
        continue
    train, _ = G.load_markets(c, arm, *TRAIN)
    test, _ = G.load_markets(c, arm, *TEST)
    params = R.fit_params(arm, train)                       # frozen from here on

    # What Jul-Aug honestly predicted: out-of-fold within Jul-Aug only.
    oof = []
    for w in sorted({week(m["day"]) for m in train}):
        oof += G.trades_for(arm, R.fit_params(arm, [m for m in train if week(m["day"]) != w]),
                            [m for m in train if week(m["day"]) == w])

    # September, one day at a time, frozen parameters, that day's quotes only.
    sep, daily = [], []
    test_days = sorted({m["day"] for m in test})
    for d in test_days:
        todays = [m for m in test if m["day"] == d]
        t = G.trades_for(arm, params, todays)
        for x in t:
            a, b = R.curve(arm, params, x["offset"])
            p = R.p_model(x["mid"], a, b)
            x["pred_edge"] = 100 * ((p if x["side"] == "yes" else 1 - p)) - x["price"] - x["fee"]
        sep += t
        daily.append(dict(day=str(d), trades=len(t), net=round(sum(x["pnl"] for x in t) / 100, 2)))

    # Where the temperature model broke: predicted edge on the trades it chose vs what arrived.
    pred = float(np.mean([x["pred_edge"] for x in sep])) if sep else 0.0
    real = float(np.mean([x["pnl"] for x in sep])) if sep else 0.0

    # Calibration of the frozen curve on every September quote the rule looked at, vs the market.
    pts = [(m["y"], o) for m in test for o in m["evals"]]
    y = np.array([p[0] for p in pts], float)
    mid = np.array([(o[1] + o[2]) / 200 for _, o in pts])
    pm = np.array([R.p_model((o[1] + o[2]) / 2, *R.curve(arm, params, o[0])) for _, o in pts])
    bands = []
    for lo, hi in ((0, .1), (.1, .2), (.2, .3), (.3, .4), (.4, .5), (.5, .6), (.6, .8), (.8, 1.01)):
        sel = (mid >= lo) & (mid < hi)
        if sel.sum() >= 15:
            bands.append(dict(band=f"{int(lo*100)}-{min(100,int(hi*100))}c", n=int(sel.sum()),
                              market=round(float(mid[sel].mean()), 3), model=round(float(pm[sel].mean()), 3),
                              rained=round(float(y[sel].mean()), 3)))
    weeks = defaultdict(list)
    for x in sep:
        weeks[str(week(x["day"])[1])].append(x)
    out["rules"][key] = dict(
        label=label, params=params,
        train_in=stats(G.trades_for(arm, params, train)), train_oof=stats(oof), sep=stats(sep),
        pred_edge=round(pred, 2), real_edge=round(real, 2),
        brier_market=round(float(np.mean((mid - y) ** 2)), 4), brier_model=round(float(np.mean((pm - y) ** 2)), 4),
        n_quotes=len(pts), bands=bands, daily=daily,
        by_week=[dict(week=f"ISO week {w}", **stats(v)) for w, v in sorted(weeks.items(), key=lambda kv: int(kv[0]))],
        account=sized_account(sep, test_days))
    r = out["rules"][key]
    print(f"\n{label}\n  params {json.dumps(params)}")
    print(f"  Jul-Aug in-sample : {r['train_in']}")
    print(f"  Jul-Aug out-of-fold: {r['train_oof']}")
    print(f"  SEPTEMBER (frozen) : {r['sep']}")
    print(f"  predicted edge on Sep trades {pred:+.2f}c vs realized {real:+.2f}c "
          f"(ratio {real / pred if pred else float('nan'):.2f})")
    print(f"  Sep Brier: market {r['brier_market']} vs frozen curve {r['brier_model']} on {len(pts)} quotes")
    for bnd in bands:
        print(f"    {bnd}")
    print(f"  weeks: {[(w['week'], w.get('n'), w.get('mean')) for w in r['by_week']]}")
    print(f"  $100 account end of Sep: ${r['account'][-1]['settled']}")
json.dump(out, open(OUT + "/retro.json", "w"), default=str)
