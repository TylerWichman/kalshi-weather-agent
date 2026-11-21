"""Headless tick collector: Kalshi order books + multi-exchange spot, written to hourly files.

    py -3.12 -m crypto15m.collect --hours 5.25 --out data/crypto15m/ticks [--upload]

Records (one JSON object per line):
  {"k":"m", "t", "c", "tk", "o", "x", "s"}   market seen: open, close, strike
  {"k":"b", "t", "c", "tk", "y", "n"}        order book (yes bids, no bids), on change
  {"k":"s", "t", "c", "e", "p"}              last trade on exchange e, on change

Exchanges are four constituents of the CF Benchmarks indices that settle these markets:
cb = Coinbase, kr = Kraken, bs = Bitstamp, gm = Gemini.

Each completed hour is gzipped; with --upload it is attached to the GitHub release
`c15m-data-YYYYMMDD` (created on demand) via the gh CLI. File names carry a run tag so
overlapping runs never overwrite each other; the importer dedupes rows.
"""

import argparse
import gzip
import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone

from .common import COINS, COINBASE, get, kalshi

KRAKEN_PAIRS = {"BTC": "XXBTZUSD", "ETH": "XETHZUSD", "SOL": "SOLUSD"}

stop = threading.Event()
wlock = threading.Lock()


class HourlyWriter:
    def __init__(self, out, tag, upload):
        self.out, self.tag, self.upload = out, tag, upload
        os.makedirs(out, exist_ok=True)
        self.hour, self.fh, self.path = None, None, None
        self.n = 0

    def write(self, rec):
        hour = datetime.fromtimestamp(rec["t"], timezone.utc).strftime("%Y%m%d%H")
        with wlock:
            if hour != self.hour:
                self._close()
                self.hour = hour
                self.path = os.path.join(self.out, f"ticks-{hour}-{self.tag}.jsonl")
                self.fh = open(self.path, "a", encoding="utf-8")
            self.fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
            self.n += 1

    def _close(self):
        if not self.fh:
            return
        self.fh.close()
        gz = self.path + ".gz"
        with open(self.path, "rb") as src, gzip.open(gz, "wb") as dst:
            shutil.copyfileobj(src, dst)
        os.remove(self.path)
        print(f"closed {os.path.basename(gz)}", flush=True)
        if self.upload:
            threading.Thread(target=upload, args=(gz, self.hour[:8]), daemon=False).start()
        self.fh = None

    def close(self):
        with wlock:
            self._close()


def upload(path, day):
    tag = f"c15m-data-{day}"
    for attempt in range(3):
        r = subprocess.run(["gh", "release", "upload", tag, path, "--clobber"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print(f"uploaded {os.path.basename(path)} -> {tag}", flush=True)
            return
        subprocess.run(["gh", "release", "create", tag, "--prerelease", "--title", tag,
                        "--notes", "15-min crypto tick data (crypto15m.collect)."],
                       capture_output=True, text=True)
        time.sleep(5)
    print(f"UPLOAD FAILED {path}: {r.stderr.strip()[:300]}", flush=True)


def spot_loop(w):
    last = {}

    def emit(c, e, p):
        if p and last.get((c, e)) != p:
            last[(c, e)] = p
            w.write({"k": "s", "t": round(time.time(), 2), "c": c, "e": e, "p": p})

    while not stop.is_set():
        t0 = time.time()
        for c, cfg in COINS.items():
            try:
                emit(c, "cb", float(get(f"{COINBASE}/products/{cfg['product']}/ticker",
                                        retries=1, min_gap=0)["price"]))
            except Exception:
                pass
            try:
                emit(c, "bs", float(get(f"https://www.bitstamp.net/api/v2/ticker/{c.lower()}usd/",
                                        retries=1, min_gap=0)["last"]))
            except Exception:
                pass
            try:
                emit(c, "gm", float(get(f"https://api.gemini.com/v1/pubticker/{c.lower()}usd",
                                        retries=1, min_gap=0)["last"]))
            except Exception:
                pass
        try:
            d = get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD,ETHUSD,SOLUSD",
                    retries=1, min_gap=0)["result"]
            for c, key in KRAKEN_PAIRS.items():
                if key in d:
                    emit(c, "kr", float(d[key]["c"][0]))
        except Exception:
            pass
        stop.wait(max(0.0, 2.0 - (time.time() - t0)))


def kalshi_loop(w):
    current, last_book, meta_at = {}, {}, 0.0
    while not stop.is_set():
        t0 = time.time()
        if t0 - meta_at > 20 or any(m["x"] <= t0 for m in current.values()):
            meta_at = t0
            for c, cfg in COINS.items():
                try:
                    d = kalshi(f"/markets?series_ticker={cfg['series']}&status=open&limit=5",
                               retries=2, min_gap=0.05)
                    tsf = lambda x: datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp()
                    live = [m for m in d.get("markets", [])
                            if tsf(m["open_time"]) <= t0 < tsf(m["close_time"])]
                    if live:
                        m = min(live, key=lambda m: m["close_time"])
                        rec = {"k": "m", "t": round(t0, 2), "c": c, "tk": m["ticker"],
                               "o": tsf(m["open_time"]), "x": tsf(m["close_time"]),
                               "s": m.get("floor_strike")}
                        if current.get(c, {}).get("tk") != m["ticker"] or rec["s"] != current[c]["s"]:
                            w.write(rec)
                        current[c] = rec
                except Exception:
                    pass
        for c, m in list(current.items()):
            if m["x"] <= time.time():
                continue
            try:
                ob = (kalshi(f"/markets/{m['tk']}/orderbook?depth=10", retries=2, min_gap=0.05)
                      or {}).get("orderbook_fp", {})
                y = [[float(p), float(q)] for p, q in ob.get("yes_dollars") or []]
                n = [[float(p), float(q)] for p, q in ob.get("no_dollars") or []]
                key = (m["tk"], json.dumps(y), json.dumps(n))
                if last_book.get(c) != key:
                    last_book[c] = key
                    w.write({"k": "b", "t": round(time.time(), 2), "c": c, "tk": m["tk"],
                             "y": y, "n": n})
            except Exception:
                pass
        stop.wait(max(0.0, 3.0 - (time.time() - t0)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=1.0)
    ap.add_argument("--out", default=os.path.join("data", "crypto15m", "ticks"))
    ap.add_argument("--tag", default=os.environ.get("GITHUB_RUN_ID", "local"))
    ap.add_argument("--upload", action="store_true")
    a = ap.parse_args()
    w = HourlyWriter(a.out, a.tag, a.upload)
    threads = [threading.Thread(target=f, args=(w,), daemon=True) for f in (spot_loop, kalshi_loop)]
    for t in threads:
        t.start()
    end = time.time() + a.hours * 3600
    print(f"collecting until {datetime.fromtimestamp(end, timezone.utc):%H:%M}Z", flush=True)
    try:
        while time.time() < end:
            time.sleep(min(60, max(0, end - time.time())))
            print(f"{datetime.now(timezone.utc):%H:%M}Z records {w.n}", flush=True)
    finally:
        stop.set()
        for t in threads:
            t.join(timeout=10)
        w.close()
        for t in threading.enumerate():
            if t is not threading.current_thread() and not t.daemon:
                t.join(timeout=120)  # let the last upload finish


if __name__ == "__main__":
    main()
