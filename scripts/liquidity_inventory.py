"""Liquidity inventory for alternative Kalshi weather markets.

Measurement only -- no modelling, no strategy. One question: does any other weather
market on this venue carry volume comparable to the daily-high ladders already
tested?

Benchmark from the daily-high ladders (spec v3 section 8):
  ~1,355,000 contracts of 24h volume across 48 daily temp series
  median 75,671 contracts per ladder-day
  median quoted spread 1.8c

Reports per series: open markets, 24h and lifetime volume, open interest, median
quoted spread, and real resting depth from the order book (not just top-of-book
size, since depth is what the previous four tests kept lacking).

Usage:  python scripts/liquidity_inventory.py
"""

import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict

BASE = "https://api.elections.kalshi.com/trade-api/v2"
UA = {"User-Agent": "kalshi-weather-agent liquidity (tylerwichman13@gmail.com)"}

# Daily-high watchlist, for the apples-to-apples benchmark row.
BENCHMARK = ["KXHIGHLAX", "KXHIGHMIA", "KXHIGHNY", "KXHIGHAUS", "KXHIGHTATL",
             "KXHIGHCHI", "KXHIGHTDAL", "KXHIGHPHIL", "KXHIGHTHOU", "KXHIGHTOKC",
             "KXHIGHDEN", "KXHIGHTDC"]

DEPTH_SAMPLE = 3        # markets per series to pull full depth for


def get(path, retries=3):
    delay = 1.0
    for i in range(retries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(BASE + path, headers=UA), timeout=40) as f:
                return json.loads(f.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            if i == retries - 1:
                return None
        except Exception:
            if i == retries - 1:
                return None
        time.sleep(delay)
        delay *= 2
    return None


def num(d, *names):
    for n in names:
        for k in (n, n + "_fp", n + "_dollars"):
            if isinstance(d, dict) and d.get(k) not in (None, ""):
                return float(d[k])
    return 0.0


def book_depth(ticker):
    """Total resting contracts on both sides, from the real order book."""
    r = get(f"/markets/{ticker}/orderbook?depth=32")
    ob = (r or {}).get("orderbook_fp") or {}
    total = 0.0
    for side in ("yes_dollars", "no_dollars"):
        for level in (ob.get(side) or []):
            try:
                total += float(level[1])
            except (IndexError, TypeError, ValueError):
                pass
    return total


def inventory(series_tickers, label):
    rows = []
    for st in series_tickers:
        m = get(f"/markets?series_ticker={st}&status=open&limit=200")
        markets = (m or {}).get("markets", [])
        if not markets:
            rows.append(dict(ticker=st, label=label, n=0, v24=0, vol=0, oi=0,
                             spread=None, depth=None))
            continue
        spreads = []
        for x in markets:
            b, a = num(x, "yes_bid"), num(x, "yes_ask")
            if b > 0 and a > 0 and a > b:
                spreads.append((a - b) * 100)
        ranked = sorted(markets, key=lambda x: -num(x, "volume_24h"))
        depths = [book_depth(x["ticker"]) for x in ranked[:DEPTH_SAMPLE]]
        rows.append(dict(
            ticker=st, label=label, n=len(markets),
            v24=sum(num(x, "volume_24h") for x in markets),
            vol=sum(num(x, "volume") for x in markets),
            oi=sum(num(x, "open_interest") for x in markets),
            spread=statistics.median(spreads) if spreads else None,
            depth=statistics.median(depths) if depths else None))
        time.sleep(0.1)
    return rows


def show(rows, title):
    rows = sorted(rows, key=lambda r: -r["v24"])
    live = [r for r in rows if r["n"] > 0]
    print(f"\n{title}")
    print(f"  {'series':<18}{'mkts':>5}{'vol 24h':>11}{'lifetime':>12}"
          f"{'open int':>10}{'spread':>8}{'depth':>9}")
    print("  " + "-" * 73)
    for r in rows[:16]:
        sp = f"{r['spread']:.0f}c" if r["spread"] else "-"
        dp = f"{r['depth']:,.0f}" if r["depth"] else "-"
        print(f"  {r['ticker']:<18}{r['n']:>5}{r['v24']:>11,.0f}{r['vol']:>12,.0f}"
              f"{r['oi']:>10,.0f}{sp:>8}{dp:>9}")
    if len(rows) > 16:
        print(f"  ... and {len(rows)-16} more")
    print("  " + "-" * 73)
    print(f"  {'TOTAL':<18}{sum(r['n'] for r in rows):>5}"
          f"{sum(r['v24'] for r in rows):>11,.0f}{sum(r['vol'] for r in rows):>12,.0f}"
          f"{sum(r['oi'] for r in rows):>10,.0f}")
    print(f"  series with any open market: {len(live)}/{len(rows)}")
    return rows


def main():
    cat = get("/series?category=Climate%20and%20Weather")
    series = (cat or {}).get("series", [])
    by_tag = defaultdict(list)
    for s in series:
        for t in (s.get("tags") or ["<none>"]):
            by_tag[t].append(s["ticker"])

    print("=" * 79)
    print("LIQUIDITY INVENTORY -- alternative weather markets (measurement only)")
    print("=" * 79)

    # Monthly rain/snow: filter the tag to monthly frequency.
    freq = {s["ticker"]: s.get("frequency") for s in series}
    monthly_rain = [t for t in by_tag["Snow and rain"] if freq.get(t) == "monthly"]

    groups = [
        (BENCHMARK, "daily-high (BENCHMARK)", "1. BENCHMARK -- daily-high ladders"),
        (by_tag["Heatwaves"], "heatwave", "2. HEATWAVE markets"),
        (monthly_rain, "monthly-rain", "3. MONTHLY RAIN/SNOW markets"),
        (by_tag["Hourly temperature"], "hourly", "4. HOURLY temperature markets"),
    ]
    all_rows = {}
    for tickers, label, title in groups:
        all_rows[label] = show(inventory(tickers, label), title)

    print("\n" + "=" * 79)
    print("COMPARISON vs the benchmark")
    print("=" * 79)
    bench = sum(r["v24"] for r in all_rows["daily-high (BENCHMARK)"])
    bench_oi = sum(r["oi"] for r in all_rows["daily-high (BENCHMARK)"])
    print(f"\n  {'group':<26}{'24h vol':>12}{'vs bench':>11}{'open int':>12}"
          f"{'median spread':>15}")
    print("  " + "-" * 76)
    for label, rows in all_rows.items():
        v = sum(r["v24"] for r in rows)
        oi = sum(r["oi"] for r in rows)
        sps = [r["spread"] for r in rows if r["spread"]]
        sp = f"{statistics.median(sps):.0f}c" if sps else "-"
        print(f"  {label:<26}{v:>12,.0f}{(v/bench if bench else 0):>10.1%}"
              f"{oi:>12,.0f}{sp:>15}")
    print(f"\n  benchmark 24h volume: {bench:,.0f} contracts, "
          f"open interest {bench_oi:,.0f}")
    print()


if __name__ == "__main__":
    main()
