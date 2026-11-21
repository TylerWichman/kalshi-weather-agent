"""Backfill every public Kalshi trade for settled ETH/SOL 15-min windows.

    py -3.12 -m crypto15m.trades            # oldest first, resumes

Kalshi's public trade history reaches back at least to mid-September 2026 (trading on
these series starts around Sept 15); it runs oldest-first in case retention is finite. Each window's trades are stored gzipped in
data/crypto15m.sqlite, table trade_blobs: one row per ticker,
data = gzip(JSON [[ts, yes_price, count, taker_yes], ...]) sorted by time, where
taker_yes = 1 if the taker bought YES (lifted the YES ask), 0 if the taker bought NO
(hit the YES bid).

On Windows the process asks the OS not to sleep while it runs, and releases that on exit.
"""

import gzip
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from .common import kalshi
from .store import connect

COINS = ("ETH", "SOL")


def keep_awake(on):
    try:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
    except Exception:
        pass


def ensure(con):
    con.execute("CREATE TABLE IF NOT EXISTS trade_blobs (ticker TEXT PRIMARY KEY, coin TEXT, "
                "close INTEGER, n INTEGER, data BLOB)")
    con.commit()


def fetch(ticker):
    rows, cur = [], ""
    while True:
        d = kalshi(f"/markets/trades?ticker={ticker}&limit=1000" + (f"&cursor={cur}" if cur else ""),
                   min_gap=0.12, retries=8)
        for t in d.get("trades", []):
            ts = datetime.fromisoformat(t["created_time"].replace("Z", "+00:00")).timestamp()
            rows.append([round(ts, 3), float(t["yes_price_dollars"]), float(t["count_fp"]),
                         1 if t["taker_side"] == "yes" else 0])
        cur = d.get("cursor")
        if not cur or not d.get("trades"):
            break
    rows.sort()
    return rows


def main(coins=COINS):
    con = connect()
    ensure(con)
    have = {r[0] for r in con.execute("SELECT ticker FROM trade_blobs")}
    q = ",".join("?" * len(coins))
    todo = [r for r in con.execute(
        f"SELECT ticker, coin, close FROM markets WHERE coin IN ({q}) ORDER BY close", coins)
        if r[0] not in have]
    print(f"{len(todo)} windows to fetch", flush=True)
    keep_awake(True)
    empty_run = 0
    try:
        with ThreadPoolExecutor(2) as ex:
            for i in range(0, len(todo), 50):
                batch = todo[i:i + 50]
                got = list(ex.map(lambda r: fetch(r[0]), batch))
                for (tk, coin, close), rows in zip(batch, got):
                    if not rows:
                        empty_run += 1
                        continue  # expired or no trades: leave unrecorded
                    empty_run = 0
                    con.execute("INSERT OR REPLACE INTO trade_blobs VALUES (?,?,?,?,?)",
                                (tk, coin, close, len(rows),
                                 gzip.compress(json.dumps(rows, separators=(",", ":")).encode())))
                con.commit()
                print(f"{min(i + 50, len(todo))}/{len(todo)}  through "
                      f"{datetime.fromtimestamp(batch[-1][2]):%m-%d %H:%M}", flush=True)
    finally:
        keep_awake(False)
    n, rows = con.execute("SELECT COUNT(*), SUM(n) FROM trade_blobs").fetchone()
    print(f"done: {n} windows, {rows} trades stored", flush=True)


if __name__ == "__main__":
    main(tuple(sys.argv[1:]) or COINS)
