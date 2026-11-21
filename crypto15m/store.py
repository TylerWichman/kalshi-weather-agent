"""SQLite store for everything the 15-min crypto work collects: data/crypto15m.sqlite

Tables
  markets       one row per settled market (backfill)
  kminutes      Kalshi 1-minute bid/ask/last/volume per market (backfill)
  spot_minutes  Coinbase 1-minute candles (backfill)
  book_ticks    Kalshi order book snapshots, written when the book changes (collector)
  spot_ticks    last-trade price per exchange, written when it changes (collector)
  market_meta   open/close/strike per market as seen live (collector)

Imports are idempotent (INSERT OR IGNORE), so re-running sync is always safe.
"""

import gzip
import json
import os
import sqlite3

from .common import COINS, DATA, ROOT, read_jsonl

DB = os.path.join(ROOT, "data", "crypto15m.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS markets (
  ticker TEXT PRIMARY KEY, coin TEXT, open INTEGER, close INTEGER,
  strike REAL, settle REAL, result TEXT, volume REAL);
CREATE TABLE IF NOT EXISTS kminutes (
  ticker TEXT, ts INTEGER, bid REAL, ask REAL, last REAL, volume REAL,
  PRIMARY KEY (ticker, ts));
CREATE TABLE IF NOT EXISTS spot_minutes (
  coin TEXT, ts INTEGER, low REAL, high REAL, open REAL, close REAL, volume REAL,
  PRIMARY KEY (coin, ts));
CREATE TABLE IF NOT EXISTS book_ticks (
  coin TEXT, ticker TEXT, ts REAL, yes TEXT, no TEXT, PRIMARY KEY (ticker, ts));
CREATE TABLE IF NOT EXISTS spot_ticks (
  coin TEXT, ex TEXT, ts REAL, price REAL, PRIMARY KEY (coin, ex, ts));
CREATE TABLE IF NOT EXISTS market_meta (
  ticker TEXT PRIMARY KEY, coin TEXT, open REAL, close REAL, strike REAL);
CREATE TABLE IF NOT EXISTS imported_files (name TEXT PRIMARY KEY);
CREATE INDEX IF NOT EXISTS markets_coin_close ON markets (coin, close);
CREATE INDEX IF NOT EXISTS book_coin_ts ON book_ticks (coin, ts);
CREATE INDEX IF NOT EXISTS spot_coin_ts ON spot_ticks (coin, ts);
"""


def connect():
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    return con


def import_backfill(con):
    for coin in COINS:
        ms = read_jsonl(os.path.join(DATA, f"markets_{coin}.jsonl"))
        con.executemany("INSERT OR IGNORE INTO markets VALUES (?,?,?,?,?,?,?,?)",
                        [(m["ticker"], coin, m["open"], m["close"], m["strike"], m["settle"],
                          m["result"], m["volume"]) for m in ms])
        rows = []
        for r in read_jsonl(os.path.join(DATA, f"candles_{coin}.jsonl")):
            rows.extend((r["ticker"], *c) for c in r["c"])
        con.executemany("INSERT OR IGNORE INTO kminutes VALUES (?,?,?,?,?,?)", rows)
        sp = read_jsonl(os.path.join(DATA, f"spot_{coin}.jsonl"))
        con.executemany("INSERT OR IGNORE INTO spot_minutes VALUES (?,?,?,?,?,?,?)",
                        [(coin, *r) for r in sp])
    con.commit()


def import_ticks(con, path):
    """Import one collector file (.jsonl or .jsonl.gz). Skips files already imported."""
    name = os.path.basename(path)
    if con.execute("SELECT 1 FROM imported_files WHERE name=?", (name,)).fetchone():
        return 0
    opener = gzip.open if path.endswith(".gz") else open
    books, spots, metas = [], [], []
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            k = r.get("k")
            if k == "b":
                books.append((r["c"], r["tk"], r["t"], json.dumps(r["y"]), json.dumps(r["n"])))
            elif k == "s":
                spots.append((r["c"], r["e"], r["t"], r["p"]))
            elif k == "m":
                metas.append((r["tk"], r["c"], r["o"], r["x"], r["s"]))
    con.executemany("INSERT OR IGNORE INTO book_ticks VALUES (?,?,?,?,?)", books)
    con.executemany("INSERT OR IGNORE INTO spot_ticks VALUES (?,?,?,?)", spots)
    con.executemany("INSERT OR IGNORE INTO market_meta VALUES (?,?,?,?,?)", metas)
    con.execute("INSERT INTO imported_files VALUES (?)", (name,))
    con.commit()
    return len(books) + len(spots)


def summary(con):
    q = lambda s: con.execute(s).fetchone()[0]
    return {
        "markets": q("SELECT COUNT(*) FROM markets"),
        "kminutes": q("SELECT COUNT(*) FROM kminutes"),
        "spot_minutes": q("SELECT COUNT(*) FROM spot_minutes"),
        "book_ticks": q("SELECT COUNT(*) FROM book_ticks"),
        "spot_ticks": q("SELECT COUNT(*) FROM spot_ticks"),
        "first_close": q("SELECT datetime(MIN(close),'unixepoch') FROM markets"),
        "last_close": q("SELECT datetime(MAX(close),'unixepoch') FROM markets"),
        "ticks_through": q("SELECT datetime(MAX(ts),'unixepoch') FROM book_ticks"),
    }
