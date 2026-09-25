"""Live paper account for ONE sandbox arm, on GitHub Actions (docs/sandbox/00-common.md §7).

Display only: the verdict (scripts/sandbox_gates.py verdict) never reads the ledger. It
does read this arm's book snapshots, for criterion 3's depth sizing.

    python -m sandbox.live serve  --arm trigger   # serve every check due in the next 5 h
    python -m sandbox.live dryrun --arm trigger   # one snapshot now, no trade, no push
    python -m sandbox.live render --arm trigger   # redraw the dashboard only

State is JSON-lines on the arm's own branch sbx-state-<arm>, checked out at ./sbx_state.
The arm never reads or writes Gate 2's `state` branch or data/candidates.sqlite, nor any
other arm's branch.

Timing (00-common.md §7): each check's book is fetched `snap_lead_s` before the check and
must finish before it, or the fetch is discarded. A job that cannot start the fetch at
least 60 s before the check records the check as MISSED. Nothing is ever traded late.
"""

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone

from src.fees import trade_fee_cents
from src.history import get, _num, _cents
from src.candidates import book_levels
from sandbox import rules as R

ROOT = R.ROOT
STATE = os.path.join(ROOT, "sbx_state")
TEMPLATE = os.path.join(ROOT, "sandbox", "dashboard_template.html")
REPO = "TylerWichman/kalshi-weather-agent"

PAUSE = 0.15                   # ~6 req/s: leaves Gate 2 its rate limit (00-common.md §1)
HORIZON_S = 300 * 60           # serve checks up to 5 h ahead; the job's timeout is 330 min
GUARD_S = 60
START_BANKROLL_C = 10_000
MAX_TRADE_C = 500
DEPTH_CAP = 100
# The paper account runs live from the first check after it was switched on (Amendment 1
# in 00-common.md) and keeps running past the test. The dashboard shows it as one live
# account. The shakeout-vs-scored split exists only in the verdict, which scores events
# 26SEP30..26OCT27 from candles (scripts/sandbox_gates.py) and never reads this ledger.
LIVE_SINCE = datetime(2026, 9, 25, 18, 28, tzinfo=timezone.utc)   # first live serve run
PAPER_FIRST = date(2026, 9, 26)
PAPER_LAST = date(2026, 12, 31)

TEXT = {
    "baseline": dict(
        title="Sandbox arm 1: baseline",
        rule="Checks once a day at 00:00 UTC on the contract date. This is the frozen "
             "Gate 2 rule re-run in the sandbox as the control.",
        next="The next check is at 00:00 UTC (8 PM Eastern).",
        stale_min=26 * 60),
    "fixed": dict(
        title="Sandbox arm 2: fixed times",
        rule="Checks at 12:00 and 18:00 UTC the day before, then 00:00 and 04:00 UTC on the "
             "contract date, with one curve per time. The first check that qualifies takes "
             "the trade.",
        next="Checks run at 12:00, 18:00, 00:00 and 04:00 UTC.",
        stale_min=10 * 60),
    "trigger": dict(
        title="Sandbox arm 3: move trigger",
        rule="Watches every hour from 12:00 UTC the day before to 04:00 UTC on the contract "
             "date. It evaluates a market only after its mid has moved 10¢ or more since "
             "that market's last evaluation.",
        next="Checks run every hour from 12:00 to 04:00 UTC.",
        stale_min=8 * 60),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (ticker TEXT, snap_ts INTEGER, check_ts INTEGER,
    bid INTEGER, ask INTEGER, yes_levels TEXT, no_levels TEXT, PRIMARY KEY (ticker, snap_ts));
CREATE TABLE IF NOT EXISTS checks (check_ts INTEGER PRIMARY KEY, day TEXT, offset_h INTEGER,
    status TEXT, snap_ts INTEGER, n_markets INTEGER, n_evals INTEGER, n_trades INTEGER,
    note TEXT);
CREATE TABLE IF NOT EXISTS trades (ticker TEXT PRIMARY KEY, day TEXT, city TEXT,
    offset_h INTEGER, side TEXT, price_c INTEGER, contracts INTEGER, fee_c INTEGER,
    p_model REAL, bid_c INTEGER, ask_c INTEGER, entered_ts INTEGER, status TEXT,
    settled_ts INTEGER, mark_c INTEGER, marked_ts INTEGER);
CREATE TABLE IF NOT EXISTS refs (ticker TEXT PRIMARY KEY, ref_mid REAL, ref_ts INTEGER);
CREATE TABLE IF NOT EXISTS equity (ts INTEGER PRIMARY KEY, equity_c INTEGER, cash_c INTEGER,
    open_c INTEGER);
"""
TABLES = {"books": "ticker, snap_ts", "checks": "check_ts", "trades": "ticker",
          "refs": "ticker", "equity": "ts"}
REPLACE = ("trades", "refs")      # rows that change after they are first written


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def midnight(d):
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def event_for(d):
    return f"{R.SERIES}-{d:%y%b%d}".upper()


def schedule(arm):
    """Every (check_ts, contract date, offset) in the paper window, in time order."""
    out, d = [], PAPER_FIRST
    while d <= PAPER_LAST:
        out += [(midnight(d) + h * 3600, d, h) for h in R.ARMS[arm]["checks"]]
        d += timedelta(days=1)
    return sorted(out)


# --------------------------------------------------------------------------- #
# State <-> SQLite

def load_state(conn, state_dir):
    for table in TABLES:
        path = os.path.join(state_dir, f"{table}.jsonl")
        if not os.path.exists(path):
            continue
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
        verb = "REPLACE" if table in REPLACE else "IGNORE"
        conn.executemany(f"INSERT OR {verb} INTO {table} VALUES ({','.join('?' * len(cols))})",
                         [[r.get(c) for c in cols] for r in rows])
    conn.commit()


def dump_state(conn, state_dir):
    os.makedirs(state_dir, exist_ok=True)
    for table, order in TABLES.items():
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        tmp = os.path.join(state_dir, f"{table}.jsonl.tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            for row in conn.execute(f"SELECT * FROM {table} ORDER BY {order}"):
                f.write(json.dumps(dict(zip(cols, row)), separators=(",", ":")) + "\n")
        os.replace(tmp, os.path.join(state_dir, f"{table}.jsonl"))


def save(conn, arm, state_dir, msg):
    dump_state(conn, state_dir)
    render(conn, arm, state_dir)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        subprocess.run(["bash", os.path.join(ROOT, ".github", "scripts", "sbx_save_state.sh"),
                        state_dir, f"sbx-state-{arm}", msg], check=False)


# --------------------------------------------------------------------------- #
# Ledger

def ledger(conn):
    cash, open_val = START_BANKROLL_C, 0
    for price, n, fee, status, mark in conn.execute(
            "SELECT price_c, contracts, fee_c, status, mark_c FROM trades"):
        cash -= price * n + fee
        if status == "won":
            cash += 100 * n
        elif status == "open":
            open_val += (mark if mark is not None else price) * n
    return cash, open_val


def settle_and_mark(conn):
    try:
        _settle_and_mark(conn)
    except Exception as e:              # marks are display only; never lose a check to them
        log(f"settle/mark failed, will retry next time: {e}")


def _settle_and_mark(conn):
    now = int(time.time())
    for ticker, side in conn.execute(
            "SELECT ticker, side FROM trades WHERE status='open'").fetchall():
        m = (get(f"/markets/{ticker}") or {}).get("market") or {}
        if m.get("result") in ("yes", "no"):
            won = m["result"] == side
            conn.execute("UPDATE trades SET status=?, settled_ts=?, mark_c=?, marked_ts=? "
                         "WHERE ticker=?", ("won" if won else "lost", now, 100 if won else 0,
                                            now, ticker))
        else:
            yb, ya = _cents(_num(m, "yes_bid")), _cents(_num(m, "yes_ask"))
            mark = yb if side == "yes" else (100 - ya if ya else None)
            if mark is not None:
                conn.execute("UPDATE trades SET mark_c=?, marked_ts=? WHERE ticker=?",
                             (mark, now, ticker))
        time.sleep(PAUSE)
    cash, open_val = ledger(conn)
    conn.execute("INSERT OR REPLACE INTO equity VALUES (?,?,?,?)",
                 (now, cash + open_val, cash, open_val))
    conn.commit()


# --------------------------------------------------------------------------- #
# One check

def fetch_books(event, check_ts):
    """(snap_ts, [(ticker, bid, ask, yes, no)], status, note). Discarded if the fetch
    starts less than GUARD_S before the check or is still running at it."""
    started = time.time()
    if check_ts - started < GUARD_S:
        return int(started), [], "missed", f"fetch would start {check_ts - started:.0f}s before the check"
    rows = []
    try:
        markets = (get(f"/markets?event_ticker={event}&limit=100") or {}).get("markets", [])
        for m in markets:
            r = get(f"/markets/{m['ticker']}/orderbook?depth=10") or {}
            ob = r.get("orderbook_fp") or r.get("orderbook") or {}
            yes = book_levels(ob.get("yes_dollars") or ob.get("yes"))
            no = book_levels(ob.get("no_dollars") or ob.get("no"))
            rows.append((m["ticker"], yes[0][0] if yes else None,
                         (100 - no[0][0]) if no else None, yes, no))
            time.sleep(PAUSE)
    except Exception as e:              # an API outage is a gap, never a crash mid-night
        return int(started), [], "missed", f"API error: {e}"[:200]
    if time.time() >= check_ts:
        return int(started), [], "discarded", f"fetch still running {time.time() - check_ts:.0f}s after the check"
    return int(started), rows, "ok", None


def run_check(conn, arm, params, check_ts, day, offset):
    snap_ts, rows, status, note = fetch_books(event_for(day), check_ts)
    if status != "ok":
        conn.execute("INSERT OR REPLACE INTO checks VALUES (?,?,?,?,?,?,?,?,?)",
                     (check_ts, day.isoformat(), offset, status, snap_ts, None, None, None, note))
        conn.commit()
        log(f"check {offset:+d}h {day}: {status.upper()} ({note})")
        return
    conn.executemany("INSERT OR REPLACE INTO books VALUES (?,?,?,?,?,?,?)",
                     [(t, snap_ts, check_ts, b, a, json.dumps(y), json.dumps(n))
                      for t, b, a, y, n in rows])
    wait_until(check_ts)          # the rule acts at the check time, on the pre-check book
    a, b = R.curve(arm, params, offset)
    cash, _ = ledger(conn)
    n_evals, new = 0, []
    for ticker, bid, ask, yes, no in rows:
        if not R.valid(bid, ask):
            continue                             # no check: neither evaluation nor reference
        mid = (bid + ask) / 2.0
        if arm == "trigger":
            ref = conn.execute("SELECT ref_mid FROM refs WHERE ticker=?", (ticker,)).fetchone()
            trig = R.Trigger(ref[0] if ref else None)
            fire = trig.observe(mid)
            if trig.ref != (ref[0] if ref else None):
                conn.execute("INSERT OR REPLACE INTO refs VALUES (?,?,?)",
                             (ticker, trig.ref, check_ts))
            if not fire:
                continue
        n_evals += 1
        if conn.execute("SELECT 1 FROM trades WHERE ticker=?", (ticker,)).fetchone():
            continue                             # one position per market
        d = R.decide(bid, ask, a, b)
        if not d:
            continue
        side, price, _ = d
        shown = no[0][1] if side == "yes" else yes[0][1]   # YES lifts NO bids, and vice versa
        n = int(min(DEPTH_CAP, shown, MAX_TRADE_C // price))
        fee = trade_fee_cents(n, price, is_maker=False)
        while n > 0 and price * n + fee > min(MAX_TRADE_C, cash):
            n -= 1
            fee = trade_fee_cents(n, price, is_maker=False)
        if n < 1:
            continue
        cash -= price * n + fee
        conn.execute("INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (ticker, day.isoformat(), ticker.rsplit("-", 1)[1], offset, side, price,
                      n, fee, R.p_model(mid, a, b), bid, ask, check_ts, "open", None, price,
                      check_ts))
        new.append(f"BUY {n} {side.upper()} {ticker.rsplit('-', 1)[1]} @ {price}c")
    conn.execute("INSERT OR REPLACE INTO checks VALUES (?,?,?,?,?,?,?,?,?)",
                 (check_ts, day.isoformat(), offset, "ok", snap_ts, len(rows), n_evals,
                  len(new), None))
    conn.commit()
    log(f"check {offset:+d}h {day}: {len(rows)} markets, {n_evals} evaluated, "
        f"{len(new)} trades " + "; ".join(new))


def wait_until(ts):
    delay = ts - time.time()
    if delay > 0:
        log(f"waiting {delay / 60:.1f} min until "
            f"{datetime.fromtimestamp(ts, timezone.utc):%m-%d %H:%M:%S} UTC")
        time.sleep(delay)


# --------------------------------------------------------------------------- #

def cmd_serve(conn, arm, params, state_dir):
    start = time.time()
    settle_and_mark(conn)
    lead = R.ARMS[arm]["snap_lead_s"]
    done = {r[0] for r in conn.execute("SELECT check_ts FROM checks")}
    first_seen = conn.execute("SELECT MIN(check_ts) FROM checks").fetchone()[0]
    for check_ts, day, offset in schedule(arm):
        if check_ts in done or check_ts > start + HORIZON_S:
            continue
        if time.time() > check_ts - GUARD_S:
            # Passed with no run: log it as missed, but only once the arm is live, so the
            # dashboard does not fill with checks from before it was deployed.
            if first_seen is not None and check_ts > first_seen:
                conn.execute("INSERT OR IGNORE INTO checks VALUES (?,?,?,?,?,?,?,?,?)",
                             (check_ts, day.isoformat(), offset, "missed", None, None, None,
                              None, "no run was in progress at the check time"))
            continue
        save(conn, arm, state_dir, "waiting")
        wait_until(check_ts - lead)
        run_check(conn, arm, params, check_ts, day, offset)
        first_seen = first_seen or check_ts
        settle_and_mark(conn)
        save(conn, arm, state_dir, f"check {day} {offset:+d}h")
    save(conn, arm, state_dir, "serve")
    step_summary(conn, arm)


def cmd_dryrun(conn, arm):
    now = datetime.now(timezone.utc)
    day = now.date() + timedelta(days=1) if now.hour >= 5 else now.date()
    _, rows, status, note = fetch_books(event_for(day), time.time() + 3600)
    ok = sum(R.valid(b, a) for _, b, a, _, _ in rows)
    log(f"dryrun {event_for(day)}: {status}, {len(rows)} books, {ok} two-sided; nothing stored")
    settle_and_mark(conn)


# --------------------------------------------------------------------------- #
# Dashboard: one page per arm, on the arm's own branch

def problems(conn):
    out = []
    for status, label in (("missed", "missed"), ("discarded", "discarded by the time guard")):
        rows = conn.execute("SELECT check_ts FROM checks WHERE status=? ORDER BY check_ts",
                            (status,)).fetchall()
        if rows:
            last = ", ".join(datetime.fromtimestamp(r[0], timezone.utc).strftime("%m-%d %H:%M")
                             for r in rows[-4:])
            out.append(f"{len(rows)} check(s) {label} (latest: {last} UTC)")
    return out


def render(conn, arm, state_dir):
    t = TEXT[arm]
    trades = [dict(zip(("ticker", "day", "city", "side", "price", "contracts", "fee",
                        "p_model", "entered", "status", "settled", "mark"), r))
              for r in conn.execute(
                  "SELECT ticker, day, city, side, price_c, contracts, fee_c, p_model, "
                  "entered_ts, status, settled_ts, mark_c FROM trades ORDER BY entered_ts")]
    checks = [dict(zip(("ts", "day", "status", "markets", "evals", "trades"), r))
              for r in conn.execute("SELECT check_ts, day, status, n_markets, n_evals, n_trades "
                                    "FROM checks ORDER BY check_ts DESC LIMIT 120")][::-1]
    cash, open_val = ledger(conn)
    probs = problems(conn)
    data = dict(
        title=t["title"], rule=t["rule"], next_text=t["next"],
        updated=int(time.time()), start=START_BANKROLL_C, cash=cash, open=open_val,
        trades=trades, checks=checks,
        equity=[dict(t=a, v=b) for a, b in conn.execute("SELECT ts, equity_c FROM equity ORDER BY ts")],
        health=dict(ok=not probs, summary="", problems=probs),
        live=dict(since=int(LIVE_SINCE.timestamp()), checks=conn.execute(
            "SELECT COUNT(*) FROM checks WHERE status='ok'").fetchone()[0]),
        stale_min=t["stale_min"],
        footer=[
            "Mock money only. No orders are placed.",
            t["rule"] + " Taker fills at the best price on a book fetched just before each "
            "check, with the real taker fee, held to settlement. The account started at $100, "
            "and each trade spends at most $5. Open positions are valued at what they could "
            "be sold for now.",
            "This is a sandbox arm, separate from Gate 2 and from the other two arms. Its "
            "go/no-go comes from the pre-registered scoring in docs/sandbox/, at a 99% bar "
            "because three arms are tested at once. Nothing seen here changes a rule.",
        ],
        note=f"Updated after every check and at the start of each run. Branch "
             f"sbx-state-{arm}. Reloads itself every minute.",
    )
    html = open(TEMPLATE, encoding="utf-8").read().replace(
        "/*__DATA__*/null", json.dumps(data).replace("</", "<\\/"))
    os.makedirs(state_dir, exist_ok=True)
    out = os.path.join(state_dir, "index.html")
    if script_ok(html, state_dir):
        open(out + ".tmp", "w", encoding="utf-8").write(html)
        os.replace(out + ".tmp", out)
    else:
        log("DASHBOARD SCRIPT FAILED ITS SYNTAX CHECK: keeping the last good page")
    readme(conn, arm, state_dir, cash + open_val, probs)
    return out


def script_ok(html, scratch_dir):
    """A page whose script does not parse shows as bare HTML. Check it with node (present
    on GitHub's runners) before publishing; without node, publish as before."""
    node = shutil.which("node")
    if not node:
        return True
    js = os.path.join(scratch_dir, ".dashboard_check.js")
    open(js, "w", encoding="utf-8").write(html[html.index("<script>") + 8:html.rindex("</script>")])
    try:
        return subprocess.run([node, "--check", js], capture_output=True).returncode == 0
    finally:
        os.remove(js)


def readme(conn, arm, state_dir, equity, probs):
    """The branch's front page on GitHub: a plain summary and the dashboard link."""
    url = f"https://raw.githack.com/{REPO}/sbx-state-{arm}/index.html"
    rows = conn.execute("SELECT day, city, offset_h, side, contracts, price_c, fee_c, status, "
                        "mark_c FROM trades ORDER BY entered_ts DESC LIMIT 30").fetchall()
    lines = [f"# {TEXT[arm]['title']}", "", TEXT[arm]["rule"], "",
             f"**Dashboard:** {url}", "",
             f"Mock account **${equity / 100:,.2f}** (started at $100). "
             f"Updated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.", ""]
    lines += [f"- ⚠ {p}" for p in probs] + ([""] if probs else [])
    if rows:
        lines += ["| Event | City | Check | Side | Contracts | Paid | Status | P&L |",
                  "|---|---|--:|---|--:|--:|---|--:|"]
        for day, city, off, side, n, price, fee, status, mark in rows:
            v = 100 if status == "won" else 0 if status == "lost" else (mark or price)
            lines.append(f"| {day[5:]} | {city} | {off:+d}h | {side.upper()} | {n} | {price}¢ | "
                         f"{status} | {(v * n - price * n - fee) / 100:+.2f} |")
    lines += ["", "Pre-registration: `docs/sandbox/` on branch `sandbox`. Display only; "
              "not Gate 2."]
    open(os.path.join(state_dir, "README.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def step_summary(conn, arm):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    cash, open_val = ledger(conn)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"## {TEXT[arm]['title']}\n\nMock account ${(cash + open_val) / 100:,.2f}. "
                f"Dashboard: https://raw.githack.com/{REPO}/sbx-state-{arm}/index.html\n")
        for p in problems(conn):
            f.write(f"- ⚠ {p}\n")


ARM = None


def main():
    global ARM
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["serve", "dryrun", "render"])
    ap.add_argument("--arm", required=True, choices=list(R.ARMS))
    ap.add_argument("--state", default=STATE)
    args = ap.parse_args()
    ARM = args.arm
    params = json.load(open(R.frozen_path(args.arm)))
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    load_state(conn, args.state)
    if args.cmd == "serve":
        cmd_serve(conn, args.arm, params, args.state)
    elif args.cmd == "dryrun":
        cmd_dryrun(conn, args.arm)
        save(conn, args.arm, args.state, "dryrun")
    else:
        print(render(conn, args.arm, args.state))


if __name__ == "__main__":
    sys.exit(main())
