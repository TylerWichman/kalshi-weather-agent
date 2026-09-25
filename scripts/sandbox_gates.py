"""Sandbox gates -- implements docs/sandbox/00-common.md §5-§6 and each arm's file.

    python scripts/sandbox_gates.py import-dev                # once: copy dev rows (read-only)
    python scripts/sandbox_gates.py freeze-baseline           # arm 1: copy Gate 2's alpha, beta
    python scripts/sandbox_gates.py gate1 --arm fixed [--freeze]
    python scripts/sandbox_gates.py gate1 --arm trigger [--freeze]
    # after 26OCT27 settles -- run ONCE:
    python scripts/sandbox_gates.py load-test                 # candles into data/sandbox.sqlite
    python scripts/sandbox_gates.py import-state --arm A --state PATH   # each arm's snapshots
    python scripts/sandbox_gates.py verdict

Reads and writes only data/sandbox.sqlite and config/sandbox/. The one read of Gate 2's
data (import-dev) opens data/candidates.sqlite read-only.
"""

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timezone

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.kalshi import parse_event_date          # noqa: E402
from sandbox import rules as R                    # noqa: E402

DB = os.path.join(ROOT, "data", "sandbox.sqlite")
GATE2_DB = os.path.join(ROOT, "data", "candidates.sqlite")
GATE2_FROZEN = os.path.join(ROOT, "config", "kxrain_frozen.json")

DEV_FIRST, DEV_LAST = date(2026, 7, 15), date(2026, 9, 23)
TEST_FIRST, TEST_LAST, TEST_EVENTS = date(2026, 9, 30), date(2026, 10, 27), 28
FREEZE_DEADLINE = "2026-09-29T12:00:00Z"

# 00-common.md §6
CI_LEVEL = 0.99               # 5 claims, Bonferroni at 5% family-wise
BOOT = 20_000
MIN_TRADES = 100
MIN_DOLLARS_PER_DAY = 5.0
DEPTH_CAP = 100
BOOK_WINDOW = (60, 600)       # snapshot taken 60-600 s before the check
MAX_MISSING_BOOK = 0.10
MAX_DAY_SHARE, MAX_CITY_SHARE = 0.25, 0.40
SIDE_SHARE = 0.20
FIXED_OTHER_MIN_SHARE = 0.30  # 02-fixed-times.md
TRIGGER_WARN_OOF = 50         # 03-move-trigger.md, warning only


def connect():
    conn = sqlite3.connect(DB)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS markets (ticker TEXT PRIMARY KEY, event_ticker TEXT, result TEXT);
    CREATE TABLE IF NOT EXISTS candles (ticker TEXT, period_ts INTEGER, bid INTEGER,
        ask INTEGER, PRIMARY KEY (ticker, period_ts));
    CREATE TABLE IF NOT EXISTS books (arm TEXT, ticker TEXT, snap_ts INTEGER,
        yes_levels TEXT, no_levels TEXT, PRIMARY KEY (arm, ticker, snap_ts));
    """)
    return conn


def midnight(d):
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


# --------------------------------------------------------------------------- #
# Data

def cmd_import_dev(conn):
    src = sqlite3.connect(f"file:{GATE2_DB}?mode=ro", uri=True)
    n_m = n_c = 0
    for ticker, event, result in src.execute(
            "SELECT ticker, event_ticker, result FROM markets WHERE series_ticker=?", (R.SERIES,)):
        d = parse_event_date(event)
        if d is None or not (DEV_FIRST <= d <= DEV_LAST):
            continue
        conn.execute("INSERT OR REPLACE INTO markets VALUES (?,?,?)", (ticker, event, result))
        rows = src.execute("SELECT ticker, period_ts, yes_bid_close, yes_ask_close FROM candles "
                           "WHERE ticker=? AND interval_min=60", (ticker,)).fetchall()
        conn.executemany("INSERT OR REPLACE INTO candles VALUES (?,?,?,?)", rows)
        n_m += 1
        n_c += len(rows)
    conn.commit()
    src.close()
    print(f"copied {n_m} development markets and {n_c} hourly candles into "
          f"{os.path.relpath(DB, ROOT)} (source opened read-only)")


def cmd_load_test(conn):
    """Test candles straight from Kalshi into data/sandbox.sqlite, via the candidates
    loader pointed at a scratch file -- never at Gate 2's database."""
    from src import candidates as cand
    scratch = os.path.join(ROOT, "data", "sandbox_load.sqlite")
    cand.DB_PATH = scratch
    c2 = cand.connect()
    days = (datetime.now(timezone.utc).date() - TEST_FIRST).days + 3
    cand.cmd_history(c2, [R.SERIES], days, with_trades=False)
    for ticker, event, result in c2.execute(
            "SELECT ticker, event_ticker, result FROM markets WHERE series_ticker=?", (R.SERIES,)):
        d = parse_event_date(event)
        if d is None or not (TEST_FIRST <= d <= TEST_LAST):
            continue
        conn.execute("INSERT OR REPLACE INTO markets VALUES (?,?,?)", (ticker, event, result))
        conn.executemany("INSERT OR REPLACE INTO candles VALUES (?,?,?,?)", c2.execute(
            "SELECT ticker, period_ts, yes_bid_close, yes_ask_close FROM candles "
            "WHERE ticker=? AND interval_min=60", (ticker,)).fetchall())
    conn.commit()
    print(f"test events loaded into {os.path.relpath(DB, ROOT)}")


def cmd_import_state(conn, arm, state_dir):
    path = os.path.join(state_dir, "books.jsonl")
    rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    conn.executemany("INSERT OR IGNORE INTO books VALUES (?,?,?,?,?)",
                     [(arm, r["ticker"], r["snap_ts"], r["yes_levels"], r["no_levels"])
                      for r in rows])
    conn.commit()
    print(f"{arm}: {len(rows)} book rows imported from {path}")


def load_markets(conn, arm, first, last):
    """One dict per settled market: evals under the arm's rule, outcome, and ids."""
    offsets = R.ARMS[arm]["checks"]
    out, skipped = [], defaultdict(int)
    for ticker, event, result in conn.execute("SELECT ticker, event_ticker, result FROM markets"):
        d = parse_event_date(event)
        if d is None or not (first <= d <= last):
            continue
        if result not in ("yes", "no"):
            skipped["unsettled"] += 1
            continue
        m0 = midnight(d)
        obs = []
        for off in offsets:
            c = conn.execute("SELECT bid, ask FROM candles WHERE ticker=? AND period_ts=?",
                             (ticker, m0 + off * 3600)).fetchone()
            if c and R.valid(*c):
                obs.append((off, c[0], c[1]))
        if not obs:
            skipped["no valid quote at any check"] += 1
            continue
        out.append(dict(ticker=ticker, event=event, day=d, city=ticker.rsplit("-", 1)[1],
                        m0=m0, y=1 if result == "yes" else 0,
                        evals=R.evaluations(arm, obs)))
    return out, dict(skipped)


def trades_for(arm, params, markets):
    out = []
    for m in markets:
        t = R.trade(arm, params, m["evals"])
        if t:
            t.update(ticker=m["ticker"], day=m["day"], city=m["city"], m0=m["m0"],
                     mid=(t["bid"] + t["ask"]) / 2.0, pnl=R.settle_pnl(t, m["y"]))
            out.append(t)
    return out


# --------------------------------------------------------------------------- #
# Statistics

def day_boot(by_day_sum, by_day_cnt, level, seed):
    days = list(by_day_sum)
    s = np.array([by_day_sum[d] for d in days], float)
    c = np.array([by_day_cnt[d] for d in days], float)
    idx = np.random.default_rng(seed).integers(0, len(days), size=(BOOT, len(days)))
    means = s[idx].sum(1) / c[idx].sum(1)
    q = (1 - level) / 2 * 100
    return float(np.percentile(means, q)), float(np.percentile(means, 100 - q))


def trade_ci(trades, level=CI_LEVEL, seed=20260925):
    s, c = defaultdict(float), defaultdict(int)
    for t in trades:
        s[t["day"]] += t["pnl"]
        c[t["day"]] += 1
    return day_boot(s, c, level, seed)


def summarize(label, trades, level=CI_LEVEL):
    if not trades:
        print(f"  {label}: no trades")
        return
    pnl = [t["pnl"] for t in trades]
    lo, hi = trade_ci(trades, level)
    n_yes = sum(t["side"] == "yes" for t in trades)
    print(f"  {label}: {len(trades)} trades ({n_yes} YES / {len(trades) - n_yes} NO) on "
          f"{len({t['day'] for t in trades})} days")
    print(f"    mean net {np.mean(pnl):+.2f}c/contract   day-block {level:.0%} CI "
          f"[{lo:+.2f}, {hi:+.2f}]   total {sum(pnl):+,.0f}c")


def by_offset(trades):
    g = defaultdict(list)
    for t in trades:
        g[t["offset"]].append(t["pnl"])
    return "  ".join(f"{o:+d}h: {len(v)}/{np.mean(v):+.1f}c" for o, v in sorted(g.items()))


# --------------------------------------------------------------------------- #
# Development gate (00-common.md §5)

def cmd_gate1(conn, arm, freeze):
    assert arm in ("fixed", "trigger"), "arm 1 has no development gate (01-baseline.md)"
    markets, skipped = load_markets(conn, arm, DEV_FIRST, DEV_LAST)
    n_eval = sum(len(m["evals"]) for m in markets)
    print(f"DEVELOPMENT GATE -- arm `{arm}`, {DEV_FIRST} .. {DEV_LAST}")
    print(f"  {len(markets)} markets with a valid quote at a check, {n_eval} evaluation "
          f"points, {len({m['event'] for m in markets})} events; skipped {skipped}")

    week = lambda d: d.isocalendar()[:2]
    oof = []
    print(f"\n  Leave-one-week-out folds:")
    for w in sorted({week(m["day"]) for m in markets}):
        train = [m for m in markets if week(m["day"]) != w]
        test = [m for m in markets if week(m["day"]) == w]
        t = trades_for(arm, R.fit_params(arm, train), test)
        oof += t
        print(f"    {w[0]}-W{w[1]:02d}  markets {len(test):>4}  trades {len(t):>4}  "
              f"net {sum(x['pnl'] for x in t):>+7.0f}c")
    print()
    summarize("OUT-OF-FOLD (95% shown for comparison with Gate 1)", oof, level=0.95)
    mean_oof = float(np.mean([t["pnl"] for t in oof])) if oof else 0.0
    passed = bool(oof) and mean_oof > 0
    if oof:
        print(f"    by check offset (trades/mean): {by_offset(oof)}")
    if arm == "trigger" and len(oof) < TRIGGER_WARN_OOF:
        print(f"  WARNING: {len(oof)} < {TRIGGER_WARN_OOF} out-of-fold trades; criterion 2 "
              "(>= 100 test trades) is unlikely to be met. The rule is not changed.")

    params = R.fit_params(arm, markets)
    full = trades_for(arm, params, markets)
    print(f"\n  Full-sample fit (in-sample, NOT the gate): {json.dumps(params)}")
    summarize("IN-SAMPLE (diagnostic)", full, level=0.95)

    print("\n" + "=" * 78)
    print(f"DEVELOPMENT GATE `{arm}`: out-of-fold mean net {mean_oof:+.2f}c over {len(oof)} "
          f"trades -> {'PASS (freeze and run forward)' if passed else 'NO-GO (not run forward)'}")
    print("=" * 78)
    if freeze and passed:
        write_frozen(arm, dict(params, dev=dict(
            first=str(DEV_FIRST), last=str(DEV_LAST), markets=len(markets),
            eval_points=n_eval, oof_trades=len(oof), oof_mean_net_c=mean_oof,
            insample_trades=len(full)),
            sides_traded=sorted({t["side"] for t in full})))
    elif freeze:
        print("Not freezing: NO-GO.")


def cmd_freeze_baseline():
    fz = json.load(open(GATE2_FROZEN))
    write_frozen("baseline", dict(alpha=fz["alpha"], beta=fz["beta"],
                                  copied_from="config/kxrain_frozen.json",
                                  sides_traded=fz["direction"]["sides_traded"]))


def write_frozen(arm, body):
    os.makedirs(R.CONFIG_DIR, exist_ok=True)
    body = dict(arm=arm, registered_in=f"docs/sandbox/ (00-common.md + arm file)",
                frozen_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                commit_before=FREEZE_DEADLINE, margin=R.MARGIN, band_cents=list(R.BAND),
                checks_h=R.ARMS[arm]["checks"],
                trigger_c=R.TRIGGER_C if arm == "trigger" else None, **body)
    json.dump(body, open(R.frozen_path(arm), "w"), indent=2)
    print(f"Frozen -> {os.path.relpath(R.frozen_path(arm), ROOT)}. "
          f"Commit before {FREEZE_DEADLINE}.")


# --------------------------------------------------------------------------- #
# Verdict (00-common.md §6), run once after 26OCT27 settles

def book_size(conn, arm, t):
    check = t["m0"] + t["offset"] * 3600
    r = conn.execute("SELECT yes_levels, no_levels FROM books WHERE arm=? AND ticker=? AND "
                     "snap_ts BETWEEN ? AND ? ORDER BY snap_ts DESC LIMIT 1",
                     (arm, t["ticker"], check - BOOK_WINDOW[1], check - BOOK_WINDOW[0])).fetchone()
    if r is None:
        return None
    levels = json.loads(r[1] if t["side"] == "yes" else r[0])
    return min(DEPTH_CAP, levels[0][1]) if levels else 0


def verdict_arm(conn, arm, days):
    fz = json.load(open(R.frozen_path(arm)))
    markets, skipped = load_markets(conn, arm, TEST_FIRST, TEST_LAST)
    trades = trades_for(arm, fz, markets)
    print(f"\nARM `{arm}` -- {len(markets)} markets; skipped {skipped}")
    summarize("TEST", trades)
    pnl = [t["pnl"] for t in trades]
    checks = {}
    lo, _ = trade_ci(trades) if trades else (0, 0)
    checks["1 mean > 0 and 99% CI lower > 0"] = bool(trades) and np.mean(pnl) > 0 and lo > 0
    checks["2 >= 100 trades"] = len(trades) >= MIN_TRADES

    sizes = [book_size(conn, arm, t) for t in trades]
    missing = sum(s is None for s in sizes) / max(len(trades), 1)
    per_day = sum(t["pnl"] * s for t, s in zip(trades, sizes) if s) / 100.0 / len(days)
    print(f"  depth-sized ${per_day:.2f}/day; {missing:.1%} of trades lack a snapshot")
    checks["3 >= $5/day at depth (<=10% missing)"] = (missing <= MAX_MISSING_BOOK
                                                     and per_day >= MIN_DOLLARS_PER_DAY)

    mid = days[len(days) // 2]
    h1 = sum(t["pnl"] for t in trades if t["day"] < mid)
    h2 = sum(t["pnl"] for t in trades if t["day"] >= mid)
    print(f"  halves split at {mid}: {h1:+,.0f}c / {h2:+,.0f}c")
    checks["4 both halves positive"] = h1 > 0 and h2 > 0

    total = sum(pnl)
    bd, bc = defaultdict(float), defaultdict(float)
    for t in trades:
        bd[t["day"]] += t["pnl"]
        bc[t["city"]] += t["pnl"]
    day_share = max(bd.values()) / total if total > 0 else float("inf")
    city_share = max(bc.values()) / total if total > 0 else float("inf")
    side_ok = all(np.mean([t["pnl"] for t in trades if t["side"] == s]) > 0
                  for s in ("yes", "no")
                  if sum(t["side"] == s for t in trades) >= SIDE_SHARE * len(trades))
    mech = side_ok and day_share <= MAX_DAY_SHARE and city_share <= MAX_CITY_SHARE
    print(f"  largest day {day_share:.1%}, largest city {city_share:.1%}, sides ok {side_ok}")
    if arm == "fixed":
        other = [t for t in trades if t["offset"] != 0]
        share = len(other) / max(len(trades), 1)
        om = float(np.mean([t["pnl"] for t in other])) if other else float("nan")
        print(f"  non-00:00 trades: {len(other)} ({share:.0%}), mean {om:+.2f}c")
        mech = mech and share >= FIXED_OTHER_MIN_SHARE and bool(other) and om > 0
    checks["5 mechanism"] = mech
    if trades:
        print(f"  diagnostic by check offset: {by_offset(trades)}")

    go = all(checks.values())
    for k, v in checks.items():
        print(f"    {'PASS' if v else 'FAIL'}  {k}")
    print(f"  ARM `{arm}`: {'GO' if go else 'NO-GO'}")
    daily = defaultdict(float)
    for t in trades:
        daily[t["day"]] += t["pnl"]
    return go, daily


def cmd_verdict(conn):
    days = sorted({parse_event_date(e) for (e,) in conn.execute(
        "SELECT DISTINCT event_ticker FROM markets WHERE result IN ('yes','no')")
        if parse_event_date(e) and TEST_FIRST <= parse_event_date(e) <= TEST_LAST})
    if len(days) < TEST_EVENTS:
        sys.exit(f"Only {len(days)}/{TEST_EVENTS} test events settled and loaded.")
    print(f"SANDBOX VERDICT -- test {TEST_FIRST} .. {TEST_LAST}, {len(days)} days; "
          f"every interval is two-sided {CI_LEVEL:.0%} (5 claims, Bonferroni)")
    res = {}
    for arm in R.ARMS:
        if not os.path.exists(R.frozen_path(arm)):
            print(f"\nARM `{arm}`: not frozen (development NO-GO) -- NO-GO, family stays 5")
            continue
        res[arm] = verdict_arm(conn, arm, days)

    print("\nCOMPARISONS against baseline (paired day-block, all 28 days, 1 contract/trade)")
    base = res.get("baseline", (False, defaultdict(float)))[1]
    for arm in ("fixed", "trigger"):
        if arm not in res:
            continue
        go, daily = res[arm]
        diff = {d: daily.get(d, 0.0) - base.get(d, 0.0) for d in days}
        lo, hi = day_boot(diff, {d: 1 for d in days}, CI_LEVEL, 20260926)
        better = go and lo > 0
        print(f"  {arm} - baseline: mean {np.mean(list(diff.values())):+.2f}c/day, "
              f"99% CI [{lo:+.2f}, {hi:+.2f}] -> "
              + ("BETTER THAN BASELINE" if better else
                 "not shown better than baseline" + ("" if go else " (arm is NO-GO)")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["import-dev", "freeze-baseline", "gate1", "load-test",
                                    "import-state", "verdict"])
    ap.add_argument("--arm", choices=list(R.ARMS))
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--state")
    a = ap.parse_args()
    conn = connect()
    if a.cmd == "import-dev":
        cmd_import_dev(conn)
    elif a.cmd == "freeze-baseline":
        cmd_freeze_baseline()
    elif a.cmd == "gate1":
        cmd_gate1(conn, a.arm, a.freeze)
    elif a.cmd == "load-test":
        cmd_load_test(conn)
    elif a.cmd == "import-state":
        cmd_import_state(conn, a.arm, a.state)
    else:
        cmd_verdict(conn)


if __name__ == "__main__":
    main()
