"""Live paper trading of the frozen KXRAIN rule, with mock money and a dashboard.

Pre-registration Amendment 2: this is a display, not the verdict. It trades exactly
the frozen rule (config/kxrain_frozen.json, via scripts/rain_calibration.py) but
fills against the LIVE order book at the decision time instead of the hourly candle
close, so its P&L will differ slightly from Gate 2's.

    python -m src.paper trade    # once a day, just after 00:00 UTC
    python -m src.paper update   # every 10 min: settle, mark to market, redraw dashboard

Rules of the simulation, fixed here:
- Decision at 00:00 UTC on the contract date. A trade run more than 5 minutes late
  (machine asleep, GitHub starting the job late) records the day as MISSED rather
  than trading on prices from after the decision time.
- Taker fills at the best price on the book. Real quadratic taker fee.
- Mock account starts at $100. Each trade spends at most $5 including the fee (5% of
  the starting account), and never more than the contracts shown at the best price or
  the cash on hand. This is smaller than Gate 2's sizing (up to 100 contracts, which
  would commit ~$300 a day), so dollar P&L here is a scaled-down version of Gate 2's;
  per-contract results are the same rule.
- Held to settlement. Open positions are marked at what they could be SOLD for now
  (the best bid on the side held), which is the conservative value.
- Warm-up: it also trades 09-25 and 09-26, the pre-registration's embargo days, so
  the pipeline runs before the test starts. Gate 2 never reads paper trades, so this
  cannot touch the verdict; the dashboard labels those days and reports test-day P&L
  separately.

Phone alerts (deploy/alert_topic.txt, ntfy.sh): each night's trades, each settlement,
and an account summary every morning at 13:00 UTC (9 AM Eastern). Only outbound
messages; nothing is exposed.
"""

import argparse
import importlib.util
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

from . import candidates as cand
from .fees import trade_fee_cents
from .history import get, _num, _cents

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "data", "dashboard")
TOKEN_FILE = os.path.join(ROOT, "deploy", "dashboard_token.txt")
TOPIC_FILE = os.path.join(ROOT, "deploy", "alert_topic.txt")
TEMPLATE = os.path.join(ROOT, "src", "dashboard_template.html")

SERIES = "KXRAIN"
START_BANKROLL_C = 10_000      # $100
MAX_TRADE_C = 500              # $5 per trade, fee included
DEPTH_CAP = 100
LATE_LIMIT_S = 5 * 60         # Amendment 3: a later run trades on post-decision prices
PAPER_FIRST = "2026-09-25"     # warm-up nights 09-25, 09-26 (embargo; see docstring)
TEST_FIRST = "2026-09-27"
TEST_LAST = "2026-10-24"
TEST_DAYS = 28
SUMMARY_HOUR_UTC = 13

CITY = {
    "ATL": "Atlanta", "AUS": "Austin", "BOS": "Boston", "CHI": "Chicago",
    "CLL": "College Station", "CMH": "Columbus", "DAL": "Dallas", "DC": "Washington DC",
    "DEN": "Denver", "EWR": "Newark", "HOU": "Houston", "LAX": "Los Angeles",
    "LEX": "Lexington", "LV": "Las Vegas", "MIA": "Miami", "MIN": "Minneapolis",
    "MKE": "Milwaukee", "NOLA": "New Orleans", "NYC": "New York City",
    "OKC": "Oklahoma City", "PHIL": "Philadelphia", "PHX": "Phoenix", "PIT": "Pittsburgh",
    "PVD": "Providence", "SATX": "San Antonio", "SEA": "Seattle", "SFO": "San Francisco",
    "TTN": "Trenton",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_trades (
    ticker        TEXT PRIMARY KEY,
    event_ticker  TEXT NOT NULL,
    day           TEXT NOT NULL,
    city          TEXT NOT NULL,
    side          TEXT NOT NULL,        -- yes | no
    price_c       INTEGER NOT NULL,     -- per contract, the side bought
    contracts     INTEGER NOT NULL,
    fee_c         INTEGER NOT NULL,     -- whole order
    p_model       REAL,
    bid_c         INTEGER, ask_c INTEGER,
    entered_ts    INTEGER NOT NULL,
    status        TEXT NOT NULL,        -- open | won | lost
    settled_ts    INTEGER,
    mark_c        INTEGER,              -- per contract, latest liquidation value
    marked_ts     INTEGER
);
CREATE TABLE IF NOT EXISTS paper_days (
    day           TEXT PRIMARY KEY,
    run_ts        INTEGER NOT NULL,
    status        TEXT NOT NULL,        -- traded | no-signal | missed
    n_markets     INTEGER,
    n_trades      INTEGER
);
CREATE TABLE IF NOT EXISTS paper_meta (
    key           TEXT PRIMARY KEY,
    value         TEXT
);
CREATE TABLE IF NOT EXISTS paper_equity (
    ts            INTEGER PRIMARY KEY,
    equity_c      INTEGER NOT NULL,
    cash_c        INTEGER NOT NULL,
    open_c        INTEGER NOT NULL
);
"""


def frozen_rule():
    """The exact decide() and parameters Gate 2 uses -- one implementation, not two."""
    spec = importlib.util.spec_from_file_location(
        "rain_calibration", os.path.join(ROOT, "scripts", "rain_calibration.py"))
    rc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rc)
    fz = json.load(open(rc.FROZEN))
    return rc, fz["alpha"], fz["beta"]


def connect():
    conn = cand.connect()
    conn.executescript(SCHEMA)
    return conn


def event_for(day):
    return f"{SERIES}-{day:%y%b%d}".upper()


def best(levels):
    """Best-first [[cents, size], ...] -> (cents, size) or (None, 0)."""
    return (levels[0][0], levels[0][1]) if levels else (None, 0)


# --------------------------------------------------------------------------- #

def cmd_trade(conn):
    rc, a, b = frozen_rule()
    now = int(time.time())
    day = datetime.fromtimestamp(now, timezone.utc).date()
    decision = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
    event = event_for(day)
    if not (PAPER_FIRST <= day.isoformat() <= TEST_LAST):
        print(f"{event}: outside the paper-trading window ({PAPER_FIRST} to {TEST_LAST})")
        return
    if conn.execute("SELECT 1 FROM paper_days WHERE day=?", (day.isoformat(),)).fetchone():
        print(f"{event}: already handled today")
        return
    if now - decision > LATE_LIMIT_S:
        conn.execute("INSERT INTO paper_days VALUES (?,?,?,?,?)",
                     (day.isoformat(), now, "missed", 0, 0))
        conn.commit()
        print(f"{event}: MISSED -- run {(now - decision) // 60} min after the decision time")
        notify(f"Paper trading MISSED {fmt_day(day.isoformat())}",
               f"The trade run started {(now - decision) // 60} min after 00:00 UTC, so "
               "no trades were placed (the rule only trades at the decision time). "
               "The run started late: the machine was off or asleep, or GitHub started "
               "the job late.\n" + account_line(conn),
               priority="high", tags="warning")
        return

    markets = (get(f"/markets?event_ticker={event}") or {}).get("markets", [])
    cash, _ = ledger(conn)
    trades, skipped = [], 0
    for m in markets:
        ob = (get(f"/markets/{m['ticker']}/orderbook?depth=10") or {})
        ob = ob.get("orderbook_fp") or ob.get("orderbook") or {}
        yes = cand.book_levels(ob.get("yes_dollars") or ob.get("yes"))
        no = cand.book_levels(ob.get("no_dollars") or ob.get("no"))
        bid, bid_sz = best(yes)
        no_bid, no_sz = best(no)
        ask = 100 - no_bid if no_bid is not None else None
        # Keep the snapshot: it is also a decision-time book for Gate 2.
        conn.execute("INSERT OR REPLACE INTO books VALUES (?,?,?,?,?,?,?,?)",
                     (m["ticker"], SERIES, now, m.get("close_time"), bid, ask,
                      json.dumps(yes), json.dumps(no)))
        if bid is None or ask is None or bid <= 0 or ask >= 100 or bid > ask:
            continue
        row = dict(ticker=m["ticker"], bid=bid, ask=ask, mid=(bid + ask) / 2.0)
        d = rc.decide(row, a, b)
        if not d:
            continue
        side, price, _ = d
        # Buying YES lifts resting NO bids, and vice versa.
        shown = no_sz if side == "yes" else bid_sz
        contracts = int(min(DEPTH_CAP, shown, MAX_TRADE_C // price))
        fee = trade_fee_cents(contracts, price, is_maker=False)
        while contracts > 0 and (price * contracts + fee > min(MAX_TRADE_C, cash)):
            contracts -= 1
            fee = trade_fee_cents(contracts, price, is_maker=False)
        if contracts < 1:
            skipped += 1           # signal, but no cash (or no size) to take it
            continue
        cash -= price * contracts + fee
        trades.append((m["ticker"], event, day.isoformat(), m["ticker"].rsplit("-", 1)[1],
                       side, price, contracts, fee, rc.p_model(row, a, b), bid, ask,
                       now, "open", None, price, now))
        time.sleep(cand.PAUSE)

    conn.executemany("INSERT OR IGNORE INTO paper_trades VALUES "
                     "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", trades)
    conn.execute("INSERT INTO paper_days VALUES (?,?,?,?,?)",
                 (day.isoformat(), now, "traded" if trades else "no-signal",
                  len(markets), len(trades)))
    conn.commit()
    print(f"{event}: {len(markets)} markets, {len(trades)} paper trades"
          + (f", {skipped} signals skipped for lack of cash or size" if skipped else ""))
    for t in trades:
        print(f"  BUY {t[6]:>3} {t[4].upper():<3} {t[3]:<5} @ {t[5]}c  (fee {t[7]}c)")

    label = fmt_day(day.isoformat()) + (" (warm-up)" if day.isoformat() < TEST_FIRST else
                                        f" (test day {test_day(day.isoformat())} of {TEST_DAYS})")
    if trades:
        lines = [f"BUY {t[6]} {t[4].upper()} {CITY.get(t[3], t[3])} @ {t[5]}\u00a2 "
                 f"(${(t[5] * t[6] + t[7]) / 100:.2f})" for t in trades]
        body = "\n".join(lines)
    else:
        body = f"No trades: none of the {len(markets)} markets met the rule tonight."
    if skipped:
        body += f"\n{skipped} signal(s) skipped for lack of cash or size."
    notify(f"Paper trades {label}", body + "\n" + account_line(conn), tags="umbrella")


def cmd_update(conn):
    now = int(time.time())
    settled_now = []
    for ticker, side, city, price, n, fee in conn.execute(
            "SELECT ticker, side, city, price_c, contracts, fee_c FROM paper_trades "
            "WHERE status='open'").fetchall():
        m = (get(f"/markets/{ticker}") or {}).get("market") or {}
        result = m.get("result")
        if result in ("yes", "no"):
            won = result == side
            conn.execute("UPDATE paper_trades SET status=?, settled_ts=?, mark_c=?, marked_ts=? "
                         "WHERE ticker=?",
                         ("won" if won else "lost", now, 100 if won else 0, now, ticker))
            pnl = (100 if won else 0) * n - price * n - fee
            settled_now.append(f"{'\u2713 Won' if won else '\u2715 Lost'} "
                               f"{CITY.get(city, city)} {side.upper()}: {money(pnl, True)}")
            continue
        yes_bid = _cents(_num(m, "yes_bid"))
        yes_ask = _cents(_num(m, "yes_ask"))
        mark = yes_bid if side == "yes" else (100 - yes_ask if yes_ask else None)
        if mark is not None:
            conn.execute("UPDATE paper_trades SET mark_c=?, marked_ts=? WHERE ticker=?",
                         (mark, now, ticker))
        time.sleep(cand.PAUSE)

    cash, open_val = ledger(conn)
    conn.execute("INSERT OR REPLACE INTO paper_equity VALUES (?,?,?,?)",
                 (now, cash + open_val, cash, open_val))
    conn.commit()
    path = render(conn)
    print(f"{cand.utcnow()}  equity ${(cash + open_val) / 100:,.2f}  -> {path}")

    if settled_now:
        notify(f"{len(settled_now)} paper position(s) settled",
               "\n".join(settled_now) + "\n" + account_line(conn), tags="moneybag")
    today = datetime.fromtimestamp(now, timezone.utc)
    last = conn.execute("SELECT value FROM paper_meta WHERE key='summary_day'").fetchone()
    has_trades = conn.execute("SELECT 1 FROM paper_trades LIMIT 1").fetchone()
    if (has_trades and today.hour >= SUMMARY_HOUR_UTC
            and (not last or last[0] != today.date().isoformat())):
        notify("Paper trading: daily summary", summary_text(conn), tags="bar_chart")
        conn.execute("INSERT OR REPLACE INTO paper_meta VALUES ('summary_day', ?)",
                     (today.date().isoformat(),))
        conn.commit()


def money(c, sign=False):
    s = f"${abs(c) / 100:,.2f}"
    return (("+" if c > 0 else "-" if c < 0 else "") if sign else ("-" if c < 0 else "")) + s


def fmt_day(iso):
    return datetime.fromisoformat(iso).strftime("%a %b %d").replace(" 0", " ")


def test_day(iso):
    return (datetime.fromisoformat(iso) - datetime.fromisoformat(TEST_FIRST)).days + 1


def trade_pnl(price, n, fee, status):
    return (100 if status == "won" else 0) * n - price * n - fee


def account_line(conn):
    cash, open_val = ledger(conn)
    eq = cash + open_val
    rows = conn.execute("SELECT status FROM paper_trades").fetchall()
    won = sum(r[0] == "won" for r in rows)
    lost = sum(r[0] == "lost" for r in rows)
    n_open = sum(r[0] == "open" for r in rows)
    return (f"Account {money(eq)} ({money(eq - START_BANKROLL_C, True)} since start) \u00b7 "
            f"{won} won, {lost} lost, {n_open} open")


def summary_text(conn):
    rows = conn.execute("SELECT day, price_c, contracts, fee_c, status FROM paper_trades "
                        "WHERE status != 'open'").fetchall()
    test = [r for r in rows if r[0] >= TEST_FIRST]
    done = conn.execute("SELECT COUNT(*) FROM paper_days WHERE day BETWEEN ? AND ?",
                        (TEST_FIRST, TEST_LAST)).fetchone()[0]
    missed = conn.execute("SELECT COUNT(*) FROM paper_days WHERE status='missed'").fetchone()[0]
    lines = [account_line(conn)]
    if test:
        lines.append(f"Test days only: {money(sum(trade_pnl(*r[1:]) for r in test), True)} "
                     f"on {len(test)} settled trades")
    lines.append(f"Test progress: day {min(done, TEST_DAYS)} of {TEST_DAYS}"
                 + (f" \u00b7 {missed} night(s) missed" if missed else ""))
    summary, problems = cand.health_report(conn)
    lines.append("Collector OK" if not problems else "Collector PROBLEM: " + "; ".join(problems))
    return "\n".join(lines)


def notify(title, body, priority="default", tags=None):
    """Push to the ntfy.sh topic in deploy/alert_topic.txt, if there is one. Outbound
    only. Never lets an alert failure break trading or the dashboard."""
    if not os.path.exists(TOPIC_FILE):
        return
    topic = open(TOPIC_FILE).read().strip()
    headers = {"Title": title, "Priority": priority}     # titles are kept ASCII
    if tags:
        headers["Tags"] = tags
    try:
        req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"),
                                     headers=headers, method="POST")
        urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:
        print(f"  alert not sent: {e}")


def ledger(conn):
    """(cash, open position value) in cents."""
    cash = START_BANKROLL_C
    open_val = 0
    for price, n, fee, status, mark in conn.execute(
            "SELECT price_c, contracts, fee_c, status, mark_c FROM paper_trades"):
        cash -= price * n + fee
        if status == "won":
            cash += 100 * n
        elif status == "open":
            open_val += (mark if mark is not None else price) * n
    return cash, open_val


# --------------------------------------------------------------------------- #
# Dashboard

def site_dir():
    """Server: a random unguessable folder, so the page is not found by scanning.
    Laptop (no token file): data/dashboard/local."""
    token = open(TOKEN_FILE).read().strip() if os.path.exists(TOKEN_FILE) else "local"
    d = os.path.join(SITE, token)
    os.makedirs(d, exist_ok=True)
    root_index = os.path.join(SITE, "index.html")
    if not os.path.exists(root_index):
        open(root_index, "w").write("<!doctype html><title>.</title>")
    return d


def render(conn):
    trades = [dict(zip(("ticker", "day", "city", "side", "price", "contracts", "fee",
                        "p_model", "entered", "status", "settled", "mark"), r))
              for r in conn.execute(
                  "SELECT ticker, day, city, side, price_c, contracts, fee_c, p_model, "
                  "entered_ts, status, settled_ts, mark_c FROM paper_trades ORDER BY entered_ts")]
    equity = [dict(t=t, v=v) for t, v in conn.execute(
        "SELECT ts, equity_c FROM paper_equity ORDER BY ts")]
    days = [dict(zip(("day", "status", "markets", "trades"), r)) for r in conn.execute(
        "SELECT day, status, n_markets, n_trades FROM paper_days ORDER BY day")]
    summary, problems = cand.health_report(conn)
    cash, open_val = ledger(conn)
    data = dict(
        updated=int(time.time()), start=START_BANKROLL_C, cash=cash, open=open_val,
        trades=trades, equity=equity, days=days,
        health=dict(ok=not problems, summary=summary, problems=problems),
        test=dict(first=TEST_FIRST, last=TEST_LAST, days=TEST_DAYS, paper_first=PAPER_FIRST),
    )
    html = open(TEMPLATE, encoding="utf-8").read().replace(
        "/*__DATA__*/null", json.dumps(data).replace("</", "<\\/"))
    out = os.path.join(site_dir(), "index.html")
    tmp = out + ".tmp"
    open(tmp, "w", encoding="utf-8").write(html)
    os.replace(tmp, out)      # atomic: a viewer never loads a half-written page
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["trade", "update", "render"])
    args = ap.parse_args()
    conn = connect()
    if args.cmd == "trade":
        cmd_trade(conn)
        cmd_update(conn)
    elif args.cmd == "update":
        cmd_update(conn)
    else:
        print(render(conn))
    conn.close()


if __name__ == "__main__":
    main()
