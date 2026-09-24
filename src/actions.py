"""KXRAIN collection and paper trading on GitHub Actions (no server, no card).

GitHub's runners are wiped after every job, so state lives as plain JSON-lines files
on the repo's `state` branch, checked out at ./state. Each job loads them into a
fresh SQLite database, runs the same code the laptop runs (src/candidates.py,
src/paper.py), and writes them back.

    python -m src.actions nightly   # 23:29 UTC cron: snapshots at 23:51 and 23:56,
                                    # paper trade at 00:00:30, then update
    python -m src.actions update    # every 3 h: settle, mark, alerts, morning summary
    python -m src.actions dryrun    # one snapshot now, no trade: checks the plumbing
    python -m src.actions import-state --state PATH   # laptop, before Gate 2

Only what cannot be backfilled is kept: KXRAIN book snapshots (Gate 2's depth sizing)
and the paper-trading ledger. Candles and results come back from Kalshi's API at Gate 2
time with `python -m src.candidates history --series KXRAIN`.

Timing: GitHub starts scheduled jobs late, often by 5-30 minutes and worst around the
top of the hour. The job therefore starts early (23:29, backup 23:44) and waits inside
itself for the exact times. A start later than 23:51 loses snapshots; later than 00:30
loses the night, which paper.py records as MISSED and alerts on.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from . import candidates as cand
from . import paper

STATE = os.path.join(cand.ROOT, "state")
SERIES = "KXRAIN"
SNAP_OFFSETS_S = (-9 * 60, -4 * 60)        # 23:51 and 23:56 UTC
TRADE_OFFSET_S = 30                         # 00:00:30 UTC

# table -> (primary-key columns, optional WHERE for export)
TABLES = {
    "books": ("ticker, snap_ts", f"series_ticker = '{SERIES}'"),
    "paper_trades": ("ticker", None),
    "paper_days": ("day", None),
    "paper_meta": ("key", None),
    "paper_equity": ("ts", None),
}


# --------------------------------------------------------------------------- #
# State <-> SQLite

def import_state(conn, state_dir):
    n = 0
    for table in TABLES:
        path = os.path.join(state_dir, f"{table}.jsonl")
        if not os.path.exists(path):
            continue
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
        conn.executemany(
            f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) VALUES "
            f"({', '.join('?' * len(cols))})",
            [[r.get(c) for c in cols] for r in rows])
        # A later state can carry a settlement an earlier one did not have yet.
        if table in ("paper_trades", "paper_meta"):
            conn.executemany(
                f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) VALUES "
                f"({', '.join('?' * len(cols))})",
                [[r.get(c) for c in cols] for r in rows])
        n += len(rows)
    conn.commit()
    return n


def export_state(conn, state_dir):
    os.makedirs(state_dir, exist_ok=True)
    for table, (order, where) in TABLES.items():
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        q = f"SELECT * FROM {table}" + (f" WHERE {where}" if where else "") + f" ORDER BY {order}"
        tmp = os.path.join(state_dir, f"{table}.jsonl.tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            for row in conn.execute(q):
                f.write(json.dumps(dict(zip(cols, row)), separators=(",", ":")) + "\n")
        os.replace(tmp, os.path.join(state_dir, f"{table}.jsonl"))


# --------------------------------------------------------------------------- #
# Health, as it applies here: no 10-minute snapshots and no candle loading on
# Actions, so the laptop checks (snapshot age, events loaded) do not apply.

def actions_health(conn):
    problems = []
    now = int(time.time())
    first = datetime.fromisoformat(paper.TEST_FIRST + "T00:00:00+00:00")
    d = first
    missed = []
    while d.timestamp() <= now and d.date().isoformat() <= paper.TEST_LAST:
        ts = int(d.timestamp())
        if not conn.execute("SELECT 1 FROM books WHERE series_ticker=? AND snap_ts BETWEEN ? AND ?",
                            (SERIES, ts - 600, ts + 120)).fetchone():
            missed.append(d.strftime("%m-%d"))
        d += timedelta(days=1)
    if missed:
        problems.append(f"no decision-time book snapshot on: {', '.join(missed)}")
    miss_days = [r[0][5:] for r in conn.execute(
        "SELECT day FROM paper_days WHERE status='missed' ORDER BY day")]
    if miss_days:
        problems.append(f"paper trading missed: {', '.join(miss_days)}")
    n = conn.execute("SELECT COUNT(DISTINCT snap_ts) FROM books WHERE series_ticker=?",
                     (SERIES,)).fetchone()[0]
    return f"{n} snapshot runs stored on GitHub", problems


# --------------------------------------------------------------------------- #

def wait_until(ts):
    delay = ts - time.time()
    if delay > 0:
        print(f"  waiting {delay / 60:.1f} min until "
              f"{datetime.fromtimestamp(ts, timezone.utc):%H:%M:%S} UTC", flush=True)
        time.sleep(delay)


def target_decision(now):
    """The midnight this run serves: tonight's if it is evening, else the one just past."""
    t = datetime.fromtimestamp(now, timezone.utc)
    day = t.date() + timedelta(days=1) if t.hour >= 12 else t.date()
    return int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp()), day


def cmd_nightly(conn):
    now = time.time()
    decision, day = target_decision(now)
    print(f"Nightly run for {day} (decision {datetime.fromtimestamp(decision, timezone.utc):%Y-%m-%d %H:%M} UTC), "
          f"started {(now - decision) / 60:+.1f} min from it", flush=True)
    if conn.execute("SELECT 1 FROM paper_days WHERE day=?", (day.isoformat(),)).fetchone():
        print("  already handled by an earlier run")
        return
    for off in SNAP_OFFSETS_S:
        at = decision + off
        if time.time() > at + 240:
            print(f"  snapshot {off // 60:+d} min: too late, skipped")
            continue
        wait_until(at)
        cand.cmd_books(conn, [SERIES])
    wait_until(decision + TRADE_OFFSET_S)
    paper.cmd_trade(conn)
    paper.cmd_update(conn)


def step_summary(conn):
    """A readable page on the run itself (Actions tab, also in the GitHub mobile app)."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    cash, open_val = paper.ledger(conn)
    lines = ["## KXRAIN paper trading", "", paper.account_line(conn), ""]
    summary, problems = cand.health_report(conn)
    lines += ["**Collector:** " + ("OK" if not problems else "PROBLEM: " + "; ".join(problems)),
              f"<sub>{summary}</sub>", ""]
    rows = conn.execute(
        "SELECT day, city, side, contracts, price_c, fee_c, status, mark_c FROM paper_trades "
        "ORDER BY entered_ts DESC LIMIT 40").fetchall()
    if rows:
        lines += ["| Day | City | Side | Contracts | Paid | Status | P&L |",
                  "|---|---|---|--:|--:|---|--:|"]
        for day, city, side, n, price, fee, status, mark in rows:
            value = 100 if status == "won" else 0 if status == "lost" else (mark or price)
            pnl = value * n - price * n - fee
            label = {"won": "Won", "lost": "Lost"}.get(status, "Open (marked)")
            lines.append(f"| {day[5:]}{' (warm-up)' if day < paper.TEST_FIRST else ''} | "
                         f"{paper.CITY.get(city, city)} | {side.upper()} | {n} | {price}¢ | "
                         f"{label} | {paper.money(pnl, True)} |")
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["nightly", "update", "dryrun", "import-state"])
    ap.add_argument("--state", default=STATE)
    args = ap.parse_args()

    conn = paper.connect()
    if args.cmd == "import-state":
        n = import_state(conn, args.state)
        print(f"imported {n} rows from {args.state} into {cand.DB_PATH}")
        return

    cand.health_report = actions_health        # paper.py's alerts read it from here
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if topic:
        os.makedirs(os.path.dirname(paper.TOPIC_FILE), exist_ok=True)
        open(paper.TOPIC_FILE, "w").write(topic)
    n = import_state(conn, args.state)
    print(f"loaded {n} state rows")

    if args.cmd == "nightly":
        cmd_nightly(conn)
    elif args.cmd == "update":
        paper.cmd_update(conn)
    else:
        cand.cmd_books(conn, [SERIES])
        print(actions_health(conn))

    export_state(conn, args.state)
    step_summary(conn)
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
