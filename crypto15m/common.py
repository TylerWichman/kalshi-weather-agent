"""Shared bits for the Kalshi 15-minute crypto work (KXBTC15M / KXETH15M / KXSOL15M).

Market rule (from rules_primary): YES if the 60-second average of the CF Benchmarks
real-time index before close is >= the 60-second average before open. That opening
average is the market's `floor_strike`, and ties go to YES.

Coinbase spot stands in for the CF index, which isn't public. The gap between them is
measured per market as (Coinbase price at open) vs floor_strike.
"""

import json
import math
import os
import threading
import time
import urllib.error
import urllib.request

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
COINBASE = "https://api.exchange.coinbase.com"
UA = {"User-Agent": "crypto15m-research/0.1"}  # deliberately generic

COINS = {
    "BTC": {"series": "KXBTC15M", "product": "BTC-USD"},
    "ETH": {"series": "KXETH15M", "product": "ETH-USD"},
    "SOL": {"series": "KXSOL15M", "product": "SOL-USD"},
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "crypto15m")
os.makedirs(DATA, exist_ok=True)

_lock = threading.Lock()
_last = [0.0]


def _pace(min_gap):
    with _lock:
        wait = _last[0] + min_gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()


def get(url, retries=5, min_gap=0.12):
    """GET JSON with pacing and backoff. Returns None on 404."""
    delay = 1.0
    for attempt in range(retries):
        _pace(min_gap)
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as f:
                return json.load(f)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code not in (429,) and e.code < 500:
                raise
        except Exception:
            if attempt == retries - 1:
                raise
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"gave up on {url}")


def kalshi(path, **kw):
    return get(KALSHI + path, **kw)


def fee(price, contracts=1, multiplier=1.0):
    """Kalshi quadratic taker fee in dollars: ceil(0.07 * m * C * P * (1-P)) to the cent."""
    raw = 0.07 * multiplier * contracts * price * (1 - price)
    return math.ceil(raw * 100 - 1e-9) / 100


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def fair_yes(spot, strike, secs_left, sigma_per_sec, obs_mean_log=None, obs_secs=0):
    """P(60-s average of price before close >= strike) under driftless log-Brownian motion.

    secs_left: seconds until close. sigma_per_sec: stdev of log price per sqrt(second).
    When secs_left <= 60 part of the averaging window has been seen: pass the mean log
    price observed so far (obs_mean_log) and how many seconds that covers (obs_secs).
    """
    if spot <= 0 or strike <= 0 or sigma_per_sec <= 0:
        return None
    x = math.log(spot)
    k = math.log(strike)
    s2 = sigma_per_sec ** 2
    if secs_left > 60:
        mean = x
        var = s2 * (secs_left - 60) + s2 * 60 / 3.0
    else:
        tau = max(secs_left, 0.0)
        seen = obs_secs if obs_mean_log is not None else 0
        obs = obs_mean_log if obs_mean_log is not None else x
        # Seconds of the window neither observed nor in the future are filled with spot.
        filler = max(60 - tau - seen, 0)
        mean = (obs * seen + x * filler + x * tau) / 60.0
        var = s2 * tau ** 3 / (3 * 3600.0)
    if var <= 0:
        return 1.0 if mean >= k else 0.0
    return norm_cdf((mean - k) / math.sqrt(var))


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for l in f:
            try:
                out.append(json.loads(l))
            except ValueError:
                pass  # a line cut off by an interrupted write
    return out


def append_jsonl(path, rows):
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
