"""Forecast ingestion: NWS point forecasts and Open-Meteo ensembles (spec v3 section 2.1).

Both are free and need no key. NWS wants a User-Agent.

The important distinction, and the one v1/v2 of the spec got wrong: **NWS here is a
forecast input, not the settlement source.** The settlement target is The Weather
Company, and the official daily extreme for basis purposes comes from the CLI
product (scripts/basis_logger.py), not from anything in this module.

Temperatures are requested in Fahrenheit throughout. Kalshi's bucket edges are whole
degrees F, so converting from Celsius at the last moment would put rounding error
exactly where it does the most damage -- at a bucket boundary.
"""

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

NWS = "https://api.weather.gov"
OPENMETEO = "https://ensemble-api.open-meteo.com/v1/ensemble"
UA = {"User-Agent": "kalshi-weather-agent (tylerwichman13@gmail.com)"}

# Section 2.1: GEFS (31 members) + ECMWF IFS (51 members) = 82 members per point.
ENSEMBLE_MODELS = "gfs025,ecmwf_ifs025"


def _get(url, retries=4):
    delay = 1.0
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as f:
                return json.load(f)
        except urllib.error.HTTPError as e:
            if e.code in (404, 400):
                return None
            if attempt == retries - 1:
                raise
        except Exception:
            if attempt == retries - 1:
                raise
        time.sleep(delay)
        delay *= 2
    return None


def c_to_f(c):
    return c * 9.0 / 5.0 + 32.0


def nws_gridpoint_forecast(office, gx, gy, target_date, kind):
    """NWS daily max/min for `target_date` from the gridpoint forecast.

    Returns (value_f, updated_iso) or (None, None).

    The gridpoint `maxTemperature`/`minTemperature` series is used rather than the
    textual /forecast periods, because periods are labelled "Today"/"Tonight" and
    resolving those to a calendar date is ambiguous around midnight.
    """
    prop = "maxTemperature" if kind == "high" else "minTemperature"
    j = _get(f"{NWS}/gridpoints/{office}/{gx},{gy}")
    if not j:
        return None, None
    props = j.get("properties", {})
    series = (props.get(prop) or {}).get("values", [])
    unit = (props.get(prop) or {}).get("uom", "")
    want = target_date.isoformat()
    for entry in series:
        # validTime looks like "2026-09-23T07:00:00+00:00/PT13H"; the date prefix of
        # the local-adjusted start is what the NWS labels the day by.
        start = entry.get("validTime", "").split("/")[0]
        if start[:10] == want:
            v = entry.get("value")
            if v is None:
                continue
            return (c_to_f(v) if "degC" in unit else float(v)), props.get("updateTime")
    return None, props.get("updateTime")


def openmeteo_ensemble(lat, lon, target_date, kind, timezone_name):
    """All ensemble members' daily max/min for `target_date`.

    Returns {"members": [...], "n": int, "by_model": {...}, "run_time": iso|None}.

    Members are returned individually rather than as mean/spread: Tier 1 fits a
    distribution to the sample, and Tier 2 needs the raw members to refit at all
    (section 7).
    """
    var = "temperature_2m_max" if kind == "high" else "temperature_2m_min"
    qs = (
        f"?latitude={lat:.4f}&longitude={lon:.4f}"
        f"&daily={var}&models={ENSEMBLE_MODELS}"
        f"&forecast_days=3&temperature_unit=fahrenheit"
        f"&timezone={urllib.request.quote(timezone_name)}"
    )
    j = _get(OPENMETEO + qs)
    if not j:
        return None

    daily = j.get("daily", {})
    dates = daily.get("time", [])
    if target_date.isoformat() not in dates:
        return None
    idx = dates.index(target_date.isoformat())

    members, by_model = [], {}
    for key, values in daily.items():
        if key == "time" or not key.startswith(var):
            continue
        if idx >= len(values):
            continue
        v = values[idx]
        if v is None:
            continue
        # Open-Meteo key shapes, member index BEFORE the model name:
        #   "temperature_2m_max_ncep_gefs025"            -> gefs control run
        #   "temperature_2m_max_member01_ncep_gefs025"   -> gefs perturbed member
        #   "temperature_2m_max_member01_ecmwf_ifs025_ensemble"
        suffix = key[len(var):].lstrip("_")
        if suffix.startswith("member"):
            parts = suffix.split("_", 1)
            model = parts[1] if len(parts) > 1 else "unknown"
        else:
            model = suffix or "control"
        model = model.replace("_ensemble", "")
        members.append(float(v))
        by_model.setdefault(model, []).append(float(v))

    if not members:
        return None
    return {
        "members": members,
        "n": len(members),
        "by_model": {k: len(v) for k, v in by_model.items()},
        "run_time": j.get("generationtime_ms") and None,  # Open-Meteo omits init time here
    }


def lead_time_hours(target_date, timezone_name, now=None):
    """Hours until the target day's extreme is final: local midnight after the day.

    A daily high is not set until the local day ends, so lead time is measured to
    the end of the local calendar day, not to its start.
    """
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone_name)
    now = now or datetime.now(timezone.utc)
    end_local = datetime.combine(target_date, datetime.min.time(), tzinfo=tz)
    end_local = end_local.replace(hour=23, minute=59, second=59)
    return (end_local.astimezone(timezone.utc) - now).total_seconds() / 3600.0


def station_observations(station, tz_name, local_day, limit=500):
    """Raw observations for a station over one local calendar day.

    Returns [(utc_iso, temp_f), ...].

    Deliberately NOT used to compute an official daily extreme -- sampled
    observations understate true highs, which is the trap the basis logger hit
    (see scripts/basis_logger.py). Its job here is the running intraday picture:
    what has this station already reached today, which is the information the
    market is visibly pricing off at short lead.
    """
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(tz_name)
    start = datetime.combine(local_day, datetime.min.time(), tzinfo=tz)
    end = start + timedelta(days=1)
    url = (
        f"{NWS}/stations/{station}/observations"
        f"?start={start.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f"&end={end.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f"&limit={limit}"
    )
    j = _get(url)
    if not j:
        return []
    out = []
    for feat in j.get("features", []):
        p = feat.get("properties") or {}
        t = p.get("temperature") or {}
        v, unit = t.get("value"), t.get("unitCode", "")
        if v is None or not p.get("timestamp"):
            continue
        out.append((p["timestamp"], c_to_f(v) if "degC" in unit else float(v)))
    return out
