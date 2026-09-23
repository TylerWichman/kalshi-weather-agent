"""Build the calibration dataset: as-issued forecasts vs official actuals.

Spec v3 Phase 2, calibration half. Needs no Kalshi price data -- this answers
"is p_model honest?", which gates whether the economic half is worth building.

## Sources, and why these specifically

**Actuals: NCEI GHCN-Daily TMAX.** Validated against the NWS final CLI products
already in `data/basis.sqlite` -- **58/58 exact matches across all 12 stations**.
That matters because CLI is the product Kalshi's station ids are named after, so
GHCN is the same number with years of history instead of seven days.

**Forecasts: Open-Meteo previous-runs API, `models=ecmwf_ifs025` pinned.**

Pinning is not optional. The default `best_match` blend switches model families
around the 48h boundary, and the switch shows up as a bias discontinuity, not a
smooth skill decay:

    best_match / gfs_seamless   MAE 1.95 -> 2.10 -> 4.76 -> 4.54   bias +1.3 -> +4.8
    ecmwf_ifs025                MAE 1.35 -> 1.86 -> 2.27 -> 2.02   bias stable

A backtest built on the blended default would be fitting a model-switch artifact.
ECMWF's monotonic-within-noise error growth is also the evidence that this archive
holds genuinely as-issued forecasts rather than leaking the answer -- a leaking
archive scores equally well at every lead.

The API serves hourly values only (daily aggregates reject the `previous_dayN`
suffix), so the daily max is computed here over the station's **local** calendar
day, which is how the settlement day is defined.

## Lead-time convention

`lead_days = N` means the forecast was issued N days before the target date. A daily
high is set mid-afternoon local, so:

    lead_days=0  ~15h  -> spec's 0-24h bucket   (the CONTROL, per section 9.5)
    lead_days=1  ~39h  -> 24-48h bucket         (the DECISION bucket)
    lead_days=2  ~63h  -> 48-72h

Usage:  python scripts/build_calibration_set.py [--days 365]
"""

import argparse
import collections
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHLIST = os.path.join(ROOT, "config", "watchlist.json")
DB_PATH = os.path.join(ROOT, "data", "calibration.sqlite")

UA = {"User-Agent": "kalshi-weather-agent calibration (tylerwichman13@gmail.com)"}
PREV_RUNS = "https://previous-runs-api.open-meteo.com/v1/forecast"
NCEI = "https://www.ncei.noaa.gov/access/services/data/v1"

MODEL = "ecmwf_ifs025"      # pinned deliberately; see module docstring
MAX_LEAD = 5
MIN_HOURS = 20              # a daily max needs near-complete local-day coverage

# Validated 58/58 against NWS final CLI products in data/basis.sqlite.
GHCN = {
    "KATL": "USW00013874", "KAUS": "USW00013904", "KDCA": "USW00013743",
    "KDEN": "USW00003017", "KDFW": "USW00003927", "KHOU": "USW00012918",
    "KLAX": "USW00023174", "KMDW": "USC00111577", "KMIA": "USW00012839",
    "KNYC": "USW00094728", "KOKC": "USW00013967", "KPHL": "USW00013739",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS calibration_set (
    nws_station   TEXT NOT NULL,
    city          TEXT,
    target_date   TEXT NOT NULL,
    lead_days     INTEGER NOT NULL,
    forecast_f    REAL NOT NULL,     -- daily max from the run issued lead_days earlier
    actual_f      REAL,              -- GHCN-Daily TMAX (== NWS final CLI)
    model         TEXT NOT NULL,
    n_hours       INTEGER,           -- local-day coverage behind forecast_f
    built_at      TEXT NOT NULL,
    PRIMARY KEY (nws_station, target_date, lead_days)
);
CREATE INDEX IF NOT EXISTS ix_cal_date ON calibration_set(target_date);
CREATE INDEX IF NOT EXISTS ix_cal_lead ON calibration_set(lead_days);
"""


def get(url, retries=4):
    delay = 2.0
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as f:
                return json.loads(f.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            if attempt == retries - 1:
                raise
        except Exception:
            if attempt == retries - 1:
                raise
        time.sleep(delay)
        delay *= 2
    return None


def daily_max_by_lead(lat, lon, tz, past_days):
    """{lead_days: {date: (max_f, n_hours)}} from the pinned model's archived runs."""
    variables = ["temperature_2m"] + [
        f"temperature_2m_previous_day{i}" for i in range(1, MAX_LEAD + 1)
    ]
    url = (f"{PREV_RUNS}?latitude={lat:.4f}&longitude={lon:.4f}"
           f"&hourly={','.join(variables)}&models={MODEL}"
           f"&temperature_unit=fahrenheit&timezone={urllib.parse.quote(tz)}"
           f"&past_days={past_days}&forecast_days=1")
    j = get(url)
    if not j or "hourly" not in j:
        return {}
    h = j["hourly"]
    times = h["time"]

    out = {}
    for lead, var in enumerate(variables):
        # With models= pinned, Open-Meteo may or may not suffix the key.
        key = var if var in h else f"{var}_{MODEL}"
        if key not in h:
            continue
        per = collections.defaultdict(list)
        for t, v in zip(times, h[key]):
            if v is not None:
                per[t[:10]].append(v)
        out[lead] = {d: (max(vals), len(vals)) for d, vals in per.items()
                     if len(vals) >= MIN_HOURS}
    return out


def ghcn_actuals(station_id, start, end):
    rows = get(f"{NCEI}?dataset=daily-summaries&stations={station_id}"
               f"&startDate={start}&endDate={end}&dataTypes=TMAX"
               f"&units=standard&format=json")
    if not isinstance(rows, list):
        return {}
    return {r["DATE"]: float(r["TMAX"]) for r in rows if r.get("TMAX") not in (None, "")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    wl = json.load(open(WATCHLIST))["series"]
    stations = {}
    for s in wl:
        if s["nws_station"] in GHCN and s["kind"] == "high":
            stations.setdefault(s["nws_station"], s)

    built = datetime.now(timezone.utc).isoformat()
    total = 0
    print(f"Building calibration set: {len(stations)} stations, {args.days} days, "
          f"model={MODEL}, leads 0..{MAX_LEAD}\n")
    print(f"{'station':<8}{'city':<15}{'fc rows':>9}{'matched':>9}{'dates':>24}")
    print("-" * 66)

    for st, s in sorted(stations.items()):
        try:
            by_lead = daily_max_by_lead(s["lat"], s["lon"], s["timezone"], args.days)
        except Exception as e:
            print(f"{st:<8}{s['city']:<15}  FORECAST FAIL {str(e)[:40]}", file=sys.stderr)
            continue
        if not by_lead:
            print(f"{st:<8}{s['city']:<15}  no forecast data", file=sys.stderr)
            continue

        all_dates = sorted({d for m in by_lead.values() for d in m})
        actuals = ghcn_actuals(GHCN[st], all_dates[0], all_dates[-1])

        n_fc = n_match = 0
        for lead, per_date in by_lead.items():
            for d, (val, nh) in per_date.items():
                a = actuals.get(d)
                n_fc += 1
                n_match += a is not None
                conn.execute(
                    "INSERT OR REPLACE INTO calibration_set VALUES (?,?,?,?,?,?,?,?,?)",
                    (st, s["city"], d, lead, val, a, MODEL, nh, built),
                )
        conn.commit()
        total += n_match
        print(f"{st:<8}{s['city']:<15}{n_fc:>9}{n_match:>9}"
              f"{all_dates[0] + ' .. ' + all_dates[-1]:>24}")
        time.sleep(1.0)

    print("-" * 66)
    print(f"\n{total} forecast/actual pairs -> {DB_PATH}")
    r = conn.execute(
        "SELECT lead_days, COUNT(*) n, COUNT(DISTINCT target_date) d, COUNT(DISTINCT nws_station) s "
        "FROM calibration_set WHERE actual_f IS NOT NULL GROUP BY lead_days ORDER BY lead_days"
    ).fetchall()
    print(f"\n{'lead_days':>10}{'pairs':>8}{'dates':>8}{'stations':>10}")
    for lead, n, d, s in r:
        print(f"{lead:>10}{n:>8}{d:>8}{s:>10}")
    conn.close()


if __name__ == "__main__":
    main()
