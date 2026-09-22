"""Storage layer (spec v3 section 7).

SQLite to start, per section 6. Two rules shape the schema:

1. `forecast_snapshots` and `market_prices` are append-only. Reconstructing "what
   was known when" is what makes Phase 2's backtest honest, and an UPDATE anywhere
   in those tables destroys that.
2. Prices are integer cents, never floats. Kalshi hands back decimal strings like
   "0.4700"; 47 is exact and 0.47 is not, and these get compared against fee
   thresholds where a rounding error changes a trade decision.

Temperatures stay REAL -- they are measurements, not money.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "trading.sqlite")

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- One row per Kalshi market (a single bucket of a ladder).
CREATE TABLE IF NOT EXISTS contracts (
    ticker            TEXT PRIMARY KEY,
    series_ticker     TEXT NOT NULL,
    event_ticker      TEXT NOT NULL,        -- the ladder this bucket belongs to
    city              TEXT NOT NULL,
    kind              TEXT NOT NULL,        -- high | low
    kalshi_station_id TEXT NOT NULL,        -- e.g. CLINYC (an NWS CLI product id)
    nws_station       TEXT NOT NULL,        -- e.g. KNYC
    settlement_source TEXT NOT NULL,        -- The Weather Company, for everything we trade
    target_date       TEXT NOT NULL,        -- local calendar day the extreme is measured over
    strike_type       TEXT NOT NULL,        -- less | between | greater
    floor_strike      REAL,                 -- null on the `less` tail
    cap_strike        REAL,                 -- null on the `greater` tail
    bucket_low_f      REAL,                 -- inclusive; null = open tail
    bucket_high_f     REAL,                 -- inclusive; null = open tail
    fee_type          TEXT,                 -- read from /series, never hardcoded (section 3)
    fee_multiplier    REAL,
    open_time         TEXT,
    close_time        TEXT,
    expiration_time   TEXT,
    status            TEXT,
    result            TEXT,                 -- yes | no | '' while open
    first_seen        TEXT NOT NULL,
    last_seen         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_contracts_event ON contracts(event_ticker);
CREATE INDEX IF NOT EXISTS ix_contracts_date  ON contracts(target_date);

-- Append-only. One row per order-book poll per market.
CREATE TABLE IF NOT EXISTS market_prices (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker         TEXT NOT NULL,
    observed_at    TEXT NOT NULL,
    yes_bid_cents  INTEGER,
    yes_ask_cents  INTEGER,
    yes_bid_size   REAL,
    yes_ask_size   REAL,
    last_price_cents INTEGER,
    volume         REAL,
    volume_24h     REAL,
    open_interest  REAL,
    -- Full depth as JSON: {"yes": [[cents, size], ...], "no": [[cents, size], ...]}
    -- Depth decides whether an edge is executable, so the whole book is kept.
    book_json      TEXT,
    FOREIGN KEY (ticker) REFERENCES contracts(ticker)
);
CREATE INDEX IF NOT EXISTS ix_prices_ticker_time ON market_prices(ticker, observed_at);

-- Append-only. One row per forecast pull per station per source.
CREATE TABLE IF NOT EXISTS forecast_snapshots (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nws_station    TEXT NOT NULL,
    target_date    TEXT NOT NULL,
    kind           TEXT NOT NULL,           -- high | low
    source         TEXT NOT NULL,           -- nws_gridpoint | openmeteo_ensemble
    model          TEXT,                    -- gfs / ecmwf / null for the NWS point forecast
    fetched_at     TEXT NOT NULL,
    run_time       TEXT,                    -- model init time, when the source reports one
    lead_time_hours REAL,
    point_value_f  REAL,                    -- the single value, for point-forecast sources
    -- Ensemble members stored individually, not just mean/spread: Tier 2 and any
    -- refit need the raw sample (section 7).
    members_json   TEXT,
    n_members      INTEGER,
    UNIQUE (nws_station, target_date, kind, source, model, fetched_at)
);
CREATE INDEX IF NOT EXISTS ix_fcst_station_date ON forecast_snapshots(nws_station, target_date);

-- Live intraday station observations. Added in Phase 1 after measurement showed the
-- market prices same-day contracts off observed data while gridded forecasts lag it
-- badly (see docs/phase1-findings.md). Without this the system would compute huge
-- phantom edges against markets that already know the answer.
CREATE TABLE IF NOT EXISTS station_observations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nws_station   TEXT NOT NULL,
    local_date    TEXT NOT NULL,        -- station-local calendar day
    observed_at   TEXT NOT NULL,        -- UTC timestamp of the observation
    temp_f        REAL NOT NULL,
    fetched_at    TEXT NOT NULL,
    UNIQUE (nws_station, observed_at)
);
CREATE INDEX IF NOT EXISTS ix_obs_station_date ON station_observations(nws_station, local_date);

-- Later phases (sections 2.2, 2.6, 2.3, 2.4). Created now so the schema is one place.
CREATE TABLE IF NOT EXISTS model_estimates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL,
    event_ticker    TEXT NOT NULL,
    estimated_at    TEXT NOT NULL,
    p_model         REAL NOT NULL,
    conf_low        REAL,
    conf_high       REAL,
    p_market        REAL,
    edge            REAL,
    lead_time_hours REAL,
    features_json   TEXT,
    FOREIGN KEY (ticker) REFERENCES contracts(ticker)
);
CREATE INDEX IF NOT EXISTS ix_est_ticker_time ON model_estimates(ticker, estimated_at);

CREATE TABLE IF NOT EXISTS ladder_coherence (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_ticker  TEXT NOT NULL,
    observed_at   TEXT NOT NULL,
    n_buckets     INTEGER,
    sum_bid_cents INTEGER,
    sum_mid_cents INTEGER,
    sum_ask_cents INTEGER,
    flagged       INTEGER,          -- executable gap before fees
    survives_fees INTEGER,          -- still profitable after six legs of fees
    note          TEXT
);
CREATE INDEX IF NOT EXISTS ix_coh_event_time ON ladder_coherence(event_ticker, observed_at);

CREATE TABLE IF NOT EXISTS trades (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker            TEXT NOT NULL,
    mode              TEXT NOT NULL,        -- simulation | live
    action            TEXT NOT NULL,        -- entry | exit
    side              TEXT NOT NULL,        -- yes | no
    order_type        TEXT,                 -- maker | taker
    status            TEXT NOT NULL,        -- submitted | filled | cancelled | rejected
    submitted_at      TEXT NOT NULL,
    filled_at         TEXT,
    price_cents       INTEGER,
    contracts         INTEGER,
    fee_cents         INTEGER,
    model_estimate_id INTEGER,
    decision_json     TEXT,                 -- the full fee check that gated it
    FOREIGN KEY (ticker) REFERENCES contracts(ticker)
);

CREATE TABLE IF NOT EXISTS positions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL,
    mode            TEXT NOT NULL,
    side            TEXT NOT NULL,
    contracts       INTEGER NOT NULL,
    avg_entry_cents REAL,
    opened_at       TEXT NOT NULL,
    closed_at       TEXT,
    exit_cents      REAL,
    fees_paid_cents INTEGER DEFAULT 0,
    net_pnl_cents   INTEGER,
    FOREIGN KEY (ticker) REFERENCES contracts(ticker)
);

CREATE TABLE IF NOT EXISTS risk_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    mode        TEXT,
    kind        TEXT NOT NULL,        -- limit_hit | kill_switch | blocked_trade
    ticker      TEXT,
    reason      TEXT NOT NULL,
    detail_json TEXT
);

-- Operational record of every collector pass, so gaps in the append-only tables
-- can be told apart from "the collector never ran".
CREATE TABLE IF NOT EXISTS collection_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    kind          TEXT NOT NULL,      -- contracts | books | forecasts
    n_ok          INTEGER DEFAULT 0,
    n_failed      INTEGER DEFAULT 0,
    note          TEXT
);
"""


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def dollars_to_cents(value):
    """Kalshi returns decimal strings like '0.4700'. Round, don't truncate.

    float() then int() would turn 0.47 into 46 often enough to matter, and these
    values feed fee thresholds where one cent changes a decision.
    """
    if value is None or value == "":
        return None
    return int(round(float(value) * 100))


def connect(path=DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def start_run(conn, kind):
    cur = conn.execute(
        "INSERT INTO collection_runs (started_at, kind) VALUES (?,?)", (utcnow(), kind)
    )
    conn.commit()
    return cur.lastrowid


def finish_run(conn, run_id, n_ok, n_failed, note=""):
    conn.execute(
        "UPDATE collection_runs SET finished_at=?, n_ok=?, n_failed=?, note=? WHERE id=?",
        (utcnow(), n_ok, n_failed, note, run_id),
    )
    conn.commit()
