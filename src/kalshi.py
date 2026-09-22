"""Kalshi market-data client (spec v3 section 4).

Read-only. Production public endpoints need no auth, which is why Phases 1-3 need
no credentials at all -- only Phase 4 onward does.

Two things this module refuses to guess at, both section 9 failure modes:

- **Station matching.** The station is parsed out of each market's `rules_primary`
  text, which names it authoritatively per-market, and then checked against
  config/watchlist.json. A mismatch raises rather than defaulting, because the
  failure is silent otherwise: the model just quietly scores the wrong city.
- **Fee parameters.** `fee_type` and `fee_multiplier` are read from /series per
  series and stored. Never hardcoded (section 3).
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

BASE = "https://api.elections.kalshi.com/trade-api/v2"
UA = {"User-Agent": "kalshi-weather-agent (tylerwichman13@gmail.com)"}

MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}

# "...recorded at New York City (CLINYC) for Sep 23, 2026, is greater than 72..."
STATION_RE = re.compile(r"recorded at\s+(.+?)\s+\(([A-Z0-9]+)\)")


class StationMismatch(Exception):
    """Kalshi's rules text names a station the watchlist doesn't agree with."""


def get(path, retries=4):
    """GET with exponential backoff. Kalshi rate-limits; nothing here is urgent."""
    delay = 1.0
    for attempt in range(retries):
        try:
            req = urllib.request.Request(BASE + path, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as f:
                return json.load(f)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429 or e.code >= 500:
                if attempt == retries - 1:
                    raise
            else:
                raise
        except Exception:
            if attempt == retries - 1:
                raise
        time.sleep(delay)
        delay *= 2
    return None


def series(series_ticker):
    r = get(f"/series/{series_ticker}")
    return (r or {}).get("series")


def open_markets(series_ticker):
    r = get(f"/markets?series_ticker={series_ticker}&status=open&limit=200")
    return (r or {}).get("markets", [])


def orderbook(ticker, depth=32):
    r = get(f"/markets/{ticker}/orderbook?depth={depth}")
    return (r or {}).get("orderbook_fp") or {}


def parse_event_date(event_ticker):
    """KXHIGHNY-26SEP23 -> date(2026, 9, 23)."""
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})$", event_ticker)
    if not m:
        return None
    yy, mon, dd = m.group(1), m.group(2), m.group(3)
    if mon not in MONTHS:
        return None
    return date(2000 + int(yy), MONTHS[mon], int(dd))


def parse_station(rules_primary):
    """Pull (city_name, station_id) out of a market's rules text."""
    m = STATION_RE.search(rules_primary or "")
    return (m.group(1), m.group(2)) if m else (None, None)


def bucket_bounds(market):
    """Inclusive temperature range for a ladder bucket, in Fahrenheit.

    Ladders are one `less` tail, four 2-degree `between` buckets, one `greater`
    tail. Tails return None on their open side.

    Both tails are STRICT against their strike, which is the off-by-one that
    matters most in this codebase:

        less    cap=80   -> "79 or below"  -> (None, 79)
        between 80..81   -> "80 to 81"     -> (80, 81)
        greater floor=87 -> "88 or above"  -> (88, None)

    Kalshi's own `yes_sub_title` is the authority here; verify_bucket_bounds()
    checks this arithmetic against that text. Getting it wrong shifts every
    integrated probability by one degree at exactly the boundary where a
    contract flips.
    """
    st = market.get("strike_type")
    floor = market.get("floor_strike")
    cap = market.get("cap_strike")
    floor = float(floor) if floor is not None else None
    cap = float(cap) if cap is not None else None
    if st == "less":
        return None, (cap - 1.0) if cap is not None else None
    if st == "greater":
        return (floor + 1.0) if floor is not None else None, None
    if st == "between":
        return floor, cap
    return None, None


# "79° or below" / "88° or above" / "80° to 81°"
_SUB_BELOW = re.compile(r"(-?\d+)\s*°?\s*or below", re.I)
_SUB_ABOVE = re.compile(r"(-?\d+)\s*°?\s*or above", re.I)
_SUB_RANGE = re.compile(r"(-?\d+)\s*°?\s*to\s*(-?\d+)", re.I)


def verify_bucket_bounds(market):
    """Cross-check computed bounds against Kalshi's human-readable subtitle.

    The subtitle is what a human trader reads and what the rules mean. If the
    strike arithmetic disagrees with it, the arithmetic is wrong.
    """
    sub = market.get("yes_sub_title") or ""
    lo, hi = bucket_bounds(market)

    m = _SUB_BELOW.search(sub)
    if m:
        want = float(m.group(1))
        return (lo is None and hi == want), f"subtitle '{sub}' => (None, {want}), got ({lo}, {hi})"
    m = _SUB_ABOVE.search(sub)
    if m:
        want = float(m.group(1))
        return (hi is None and lo == want), f"subtitle '{sub}' => ({want}, None), got ({lo}, {hi})"
    m = _SUB_RANGE.search(sub)
    if m:
        w_lo, w_hi = float(m.group(1)), float(m.group(2))
        return (lo == w_lo and hi == w_hi), f"subtitle '{sub}' => ({w_lo}, {w_hi}), got ({lo}, {hi})"
    return True, f"no parseable subtitle ({sub!r}); bounds unverified"


def verify_station(market, expected_station_id, expected_source):
    """Fail loudly if Kalshi's own rules text disagrees with the watchlist.

    This is the section 9 station-mismatch guard. Kalshi has renamed and relisted
    these series before, and a settlement station changing under us would otherwise
    show up as unexplained model error months later.
    """
    _, station_id = parse_station(market.get("rules_primary"))
    if station_id is None:
        raise StationMismatch(
            f"{market['ticker']}: could not parse a station from rules_primary"
        )
    if station_id != expected_station_id:
        raise StationMismatch(
            f"{market['ticker']}: rules say station {station_id}, "
            f"watchlist says {expected_station_id}"
        )
    rules = market.get("rules_primary", "")
    if expected_source and expected_source.lower() not in rules.lower():
        raise StationMismatch(
            f"{market['ticker']}: rules_primary does not name expected settlement "
            f"source {expected_source!r}"
        )
    return station_id


def ladder_for_event(markets, event_ticker):
    """All buckets of one event, ordered low to high."""
    rung = [m for m in markets if m.get("event_ticker") == event_ticker]

    def key(m):
        lo, hi = bucket_bounds(m)
        return (lo if lo is not None else -1e9, hi if hi is not None else 1e9)

    return sorted(rung, key=key)


def check_ladder_complete(ladder):
    """Sanity-check that a ladder is contiguous and exhaustive.

    A gap or overlap means the bucket parsing is wrong, and every probability
    integrated over those edges downstream would be wrong with it.
    """
    problems = []
    bounds = [bucket_bounds(m) for m in ladder]
    if not bounds:
        return ["empty ladder"]
    if bounds[0][0] is not None:
        problems.append("no open `less` tail at the bottom")
    if bounds[-1][1] is not None:
        problems.append("no open `greater` tail at the top")
    for i in range(len(bounds) - 1):
        hi = bounds[i][1]
        nxt_lo = bounds[i + 1][0]
        if hi is None or nxt_lo is None:
            continue
        # Buckets are inclusive integer degrees, so the next low should be hi + 1.
        if abs(nxt_lo - (hi + 1.0)) > 1e-9:
            problems.append(
                f"gap/overlap between {ladder[i]['ticker']} (<={hi}) "
                f"and {ladder[i+1]['ticker']} (>={nxt_lo})"
            )
    # Independently confirm each bucket against Kalshi's own subtitle wording.
    for m in ladder:
        ok, detail = verify_bucket_bounds(m)
        if not ok:
            problems.append(f"{m['ticker']}: bounds disagree with subtitle -- {detail}")
    return problems
