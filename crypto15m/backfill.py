"""Backfill settled 15-min markets, their 1-minute Kalshi candles, and Coinbase 1-minute spot.

    py -3.12 -m crypto15m.backfill            # all three coins, resumes where it left off

Files in data/crypto15m/:
  markets_<COIN>.jsonl   one settled market per line (ticker, open/close, strike, result)
  candles_<COIN>.jsonl   {"ticker", "c": [[end_ts, bid_close, ask_close, last, volume], ...]}
  spot_<COIN>.jsonl      Coinbase 1-min candles [ts, low, high, open, close, volume]
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .common import COINS, COINBASE, DATA, append_jsonl, get, kalshi, read_jsonl


def ts(iso):
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def f(x):
    return None if x in (None, "") else float(x)


def backfill_markets(coin):
    series = COINS[coin]["series"]
    path = os.path.join(DATA, f"markets_{coin}.jsonl")
    have = {m["ticker"] for m in read_jsonl(path)}
    new, cursor = [], None
    while True:
        q = f"/markets?series_ticker={series}&status=settled&limit=1000"
        d = kalshi(q + (f"&cursor={cursor}" if cursor else ""))
        page = d.get("markets", [])
        fresh = [m for m in page if m["ticker"] not in have]
        for m in fresh:
            new.append({
                "ticker": m["ticker"], "open": ts(m["open_time"]), "close": ts(m["close_time"]),
                "strike": m.get("floor_strike"), "settle": f(m.get("expiration_value")),
                "result": m.get("result"), "volume": f(m.get("volume_fp")),
            })
        cursor = d.get("cursor")
        # Pages come newest first, so once a whole page is already known we're caught up.
        if not cursor or not page or not fresh:
            break
    new.sort(key=lambda m: m["close"])
    append_jsonl(path, new)
    print(f"{coin}: +{len(new)} markets ({len(have) + len(new)} total)", flush=True)
    return read_jsonl(path)


def backfill_candles(coin, markets):
    series = COINS[coin]["series"]
    path = os.path.join(DATA, f"candles_{coin}.jsonl")
    have = {r["ticker"] for r in read_jsonl(path)}
    todo = [m for m in markets if m["ticker"] not in have]
    def one(m):
        try:
            d = kalshi(f"/series/{series}/markets/{m['ticker']}/candlesticks"
                       f"?start_ts={m['open']}&end_ts={m['close']}&period_interval=1",
                       min_gap=0.3, retries=8)
        except Exception as e:
            print(f"{coin}: skip {m['ticker']} ({e}); next run retries it", flush=True)
            return None
        rows = []
        for c in (d or {}).get("candlesticks", []):
            rows.append([c["end_period_ts"], f(c["yes_bid"].get("close_dollars")),
                         f(c["yes_ask"].get("close_dollars")),
                         f(c["price"].get("close_dollars")), f(c.get("volume_fp"))])
        return {"ticker": m["ticker"], "c": rows}

    with ThreadPoolExecutor(2) as ex:
        for i in range(0, len(todo), 200):
            append_jsonl(path, [r for r in ex.map(one, todo[i:i + 200]) if r])
            print(f"{coin}: candles {min(i + 200, len(todo))}/{len(todo)}", flush=True)


def backfill_spot(coin, start, end):
    product = COINS[coin]["product"]
    path = os.path.join(DATA, f"spot_{coin}.jsonl")
    rows = read_jsonl(path)
    have_max = max((r[0] for r in rows), default=start - 60)
    t, new = max(start, have_max + 60), []
    while t < end:
        t2 = min(t + 300 * 60, end)
        s = datetime.fromtimestamp(t, timezone.utc).isoformat()
        e = datetime.fromtimestamp(t2 - 60, timezone.utc).isoformat()
        d = get(f"{COINBASE}/products/{product}/candles?granularity=60&start={s}&end={e}",
                min_gap=0.15) or []
        new.extend(sorted(d))
        t = t2
    new = [r for r in new if r[0] > have_max]
    append_jsonl(path, new)
    print(f"{coin}: +{len(new)} spot minutes", flush=True)


def main(coins):
    for coin in coins:
        markets = backfill_markets(coin)
        if not markets:
            continue
        start = min(m["open"] for m in markets) - 3600
        end = max(m["close"] for m in markets) + 60
        backfill_spot(coin, start, end)
        backfill_candles(coin, markets)
    print("done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or list(COINS))
