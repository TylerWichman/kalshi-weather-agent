"""Site-wide liquidity survey from Kalshi's own API (no third-party aggregators).

Answers: where is the real volume across all of Kalshi, how do weather and
health/FDA actually rank, and is there a liquid-but-niche category worth a look.

## Method

1. `GET /series` unfiltered returns the entire catalog (~14,288 series) with each
   series' category in one call -- far cheaper than per-category enumeration.
2. `GET /markets?status=open` is paginated by cursor to sweep every open market.
   Each market carries `volume_24h_fp` and `volume_fp`.
   `mve_filter=exclude` drops multivariate combo markets (KXMVE* parlays). Without
   it the sweep is >1.1M markets, overwhelmingly combos, and runs for hours; they
   are cross-category parlays, not single-category liquidity.
3. The markets listing does not populate `series_ticker`, so the series is derived
   from the event ticker's prefix (`KXHIGHNY-26SEP23` -> `KXHIGHNY`) and joined to
   the catalog. Unmatched prefixes are reported rather than silently dropped.

Volume is in contracts. On Kalshi a contract settles at $0 or $1, so contracts are a
reasonable proxy for notional; where it matters, dollar-weighted volume is also
reported using each market's last price.

Usage:
    python scripts/site_liquidity.py            # uses cache if present
    python scripts/site_liquidity.py --refresh  # re-sweep the API
"""

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict

BASE = "https://api.elections.kalshi.com/trade-api/v2"
UA = {"User-Agent": "kalshi-weather-agent site-survey (tylerwichman13@gmail.com)"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "site_liquidity.json")


def get(path, retries=4):
    delay = 1.0
    for i in range(retries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(BASE + path, headers=UA), timeout=60) as f:
                return json.loads(f.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            if i == retries - 1:
                raise
        except Exception:
            if i == retries - 1:
                raise
        time.sleep(delay)
        delay *= 2
    return None


def num(d, *names):
    for n in names:
        for k in (n, n + "_fp", n + "_dollars"):
            v = d.get(k)
            if v not in (None, ""):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
    return 0.0


def sweep():
    print("Fetching full series catalog ...", flush=True)
    cat = get("/series") or {}
    series = cat.get("series", [])
    print(f"  {len(series):,} series")

    meta = {}
    for s in series:
        meta[s["ticker"]] = dict(
            category=s.get("category") or "(uncategorized)",
            title=s.get("title", ""),
            tags=s.get("tags") or [],
            frequency=s.get("frequency"))

    print("Sweeping open markets ...", flush=True)
    markets, cursor, pages = [], None, 0
    while True:
        r = get(f"/markets?status=open&limit=1000&mve_filter=exclude"
                + (f"&cursor={cursor}" if cursor else ""))
        if not r:
            break
        batch = r.get("markets", [])
        markets += batch
        pages += 1
        cursor = r.get("cursor")
        if pages % 5 == 0:
            print(f"  page {pages}: {len(markets):,} markets", flush=True)
        if not cursor or not batch:
            break
    print(f"  {len(markets):,} open markets across {pages} pages")

    rows = []
    for m in markets:
        ev = m.get("event_ticker") or ""
        st = m.get("series_ticker") or (ev.split("-")[0] if ev else "")
        rows.append(dict(
            series=st, event=ev, ticker=m.get("ticker"),
            v24=num(m, "volume_24h"), vol=num(m, "volume"),
            oi=num(m, "open_interest"),
            last=num(m, "last_price"),
            bid=num(m, "yes_bid"), ask=num(m, "yes_ask")))

    data = dict(meta=meta, rows=rows, fetched=time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(data, open(CACHE, "w"))
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--exclude", default="Sports",
                    help="comma-separated categories to drop entirely (default: Sports)")
    args = ap.parse_args()

    if args.refresh or not os.path.exists(CACHE):
        data = sweep()
    else:
        data = json.load(open(CACHE))
        print(f"(using cache from {data['fetched']}; --refresh to re-sweep)")

    meta, rows = data["meta"], data["rows"]
    dropped = {c.strip().lower() for c in args.exclude.split(",") if c.strip()}

    by_series = defaultdict(lambda: dict(v24=0.0, vol=0.0, oi=0.0, n=0,
                                         dollars=0.0, spreads=[]))
    unmatched = defaultdict(float)
    for r in rows:
        s = by_series[r["series"]]
        s["v24"] += r["v24"]
        s["vol"] += r["vol"]
        s["oi"] += r["oi"]
        s["n"] += 1
        s["dollars"] += r["v24"] * max(r["last"], 0.0)
        if r["bid"] > 0 and r["ask"] > 0 and r["ask"] > r["bid"]:
            s["spreads"].append((r["ask"] - r["bid"]) * 100)
        if r["series"] not in meta:
            unmatched[r["series"]] += r["v24"]

    by_cat = defaultdict(lambda: dict(v24=0.0, vol=0.0, oi=0.0, n_series=0,
                                      n_markets=0, dollars=0.0, spreads=[]))
    for st, s in by_series.items():
        cat = meta.get(st, {}).get("category", "(unmatched series)")
        c = by_cat[cat]
        c["v24"] += s["v24"]
        c["vol"] += s["vol"]
        c["oi"] += s["oi"]
        c["n_series"] += 1
        c["n_markets"] += s["n"]
        c["dollars"] += s["dollars"]
        c["spreads"] += s["spreads"]

    # Sports is excluded outright per instruction: it dominates market COUNT
    # (3,883 series, most of the ~300k open markets) and is a different game
    # entirely. Reported once as a dropped line, then left out of every ranking.
    dropped_stats = {k: v for k, v in by_cat.items() if k.lower() in dropped}
    by_cat = {k: v for k, v in by_cat.items() if k.lower() not in dropped}
    total = sum(c["v24"] for c in by_cat.values()) or 1.0
    if dropped_stats:
        print()
        print("  EXCLUDED per instruction:")
        for k, v in dropped_stats.items():
            print(f"    {k}: {v['v24']:,.0f} contracts/24h across {v['n_series']:,} "
                  f"series, {v['n_markets']:,} markets -- dropped from all rankings")

    print("\n" + "=" * 92)
    print("KALSHI SITE-WIDE LIQUIDITY -- by category, ranked by 24h contract volume")
    print("=" * 92)
    print(f"\n  {'category':<26}{'24h vol':>13}{'share':>8}{'$ vol 24h':>13}"
          f"{'open int':>12}{'series':>8}{'mkts':>8}{'spread':>8}")
    print("  " + "-" * 88)
    ranked = sorted(by_cat.items(), key=lambda kv: -kv[1]["v24"])
    for cat, c in ranked:
        sp = f"{statistics.median(c['spreads']):.0f}c" if c["spreads"] else "-"
        print(f"  {cat[:25]:<26}{c['v24']:>13,.0f}{100*c['v24']/total:>7.1f}%"
              f"{c['dollars']:>13,.0f}{c['oi']:>12,.0f}"
              f"{c['n_series']:>8,}{c['n_markets']:>8,}{sp:>8}")
    print("  " + "-" * 88)
    print(f"  {'TOTAL':<26}{total:>13,.0f}{100.0:>7.1f}%")

    print("\n" + "=" * 92)
    print("WHERE WEATHER AND HEALTH ACTUALLY RANK")
    print("=" * 92)
    print()
    for i, (cat, c) in enumerate(ranked, 1):
        if any(k in cat.lower() for k in ("weather", "climate", "health", "science")):
            print(f"  #{i} of {len(ranked)}  {cat:<28}{c['v24']:>12,.0f} contracts"
                  f"  ({100*c['v24']/total:.2f}% of site volume)")

    print("\n" + "=" * 92)
    print(f"TOP {args.top} SERIES BY 24h VOLUME (the real liquidity)")
    print("=" * 92)
    print(f"\n  {'series':<22}{'category':<22}{'24h vol':>12}{'open int':>11}"
          f"{'mkts':>6}{'spread':>8}  title")
    print("  " + "-" * 118)
    ranked_series = [(st, sv) for st, sv in by_series.items()
                     if meta.get(st, {}).get("category", "").lower() not in dropped]
    for st, s in sorted(ranked_series, key=lambda kv: -kv[1]["v24"])[:args.top]:
        m = meta.get(st, {})
        sp = f"{statistics.median(s['spreads']):.0f}c" if s["spreads"] else "-"
        print(f"  {st[:21]:<22}{m.get('category','(unmatched)')[:21]:<22}"
              f"{s['v24']:>12,.0f}{s['oi']:>11,.0f}{s['n']:>6}{sp:>8}  "
              f"{m.get('title','')[:38]}")

    if unmatched:
        tot_u = sum(unmatched.values())
        print(f"\n  NOTE: {len(unmatched)} event prefixes did not match a series in the")
        print(f"  catalog, carrying {tot_u:,.0f} contracts of 24h volume "
              f"({100*tot_u/total:.1f}%). Top:")
        for st, v in sorted(unmatched.items(), key=lambda kv: -kv[1])[:6]:
            print(f"    {st:<34}{v:>12,.0f}")
    print()


if __name__ == "__main__":
    main()
