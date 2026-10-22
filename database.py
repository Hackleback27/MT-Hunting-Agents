"""
database.py - the shared database every agent writes into.

Run this file once to create hunting.db:
    python database.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "hunting.db"

SCHEMA = """
-- One row per hunting district. Deer/elk/lion share one set of district
-- numbers and antelope uses another, so species_group is part of the key.
CREATE TABLE IF NOT EXISTS districts (
    district       TEXT NOT NULL,          -- e.g. '313'
    species_group  TEXT NOT NULL,          -- 'deer_elk_lion', 'antelope', 'bear', ...
    region         INTEGER,                -- FWP region 1-7
    name           TEXT,                   -- optional friendly name
    PRIMARY KEY (district, species_group)
);

-- Filled by the harvest agent: FWP harvest estimates.
CREATE TABLE IF NOT EXISTS harvest_stats (
    district       TEXT    NOT NULL,
    species        TEXT    NOT NULL,       -- 'elk', 'mule deer', 'whitetail', 'antelope', ...
    year           INTEGER NOT NULL,
    hunters        INTEGER,
    hunter_days    INTEGER,
    harvest        INTEGER,                -- total animals taken
    success_rate   REAL,                   -- harvest / hunters (0-1)
    days_per_kill  REAL,                   -- hunter_days / harvest
    source_file    TEXT,
    collected_at   TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (district, species, year)
);

-- Filled later by the access agent.
CREATE TABLE IF NOT EXISTS access_info (
    district           TEXT NOT NULL,
    species_group      TEXT NOT NULL,
    public_land_pct    REAL,
    bma_acres          REAL,               -- Block Management acres
    notes              TEXT,
    collected_at       TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (district, species_group)
);

-- Filled later by the regulations agent.
CREATE TABLE IF NOT EXISTS regulations (
    district       TEXT NOT NULL,
    species        TEXT NOT NULL,
    year           INTEGER NOT NULL,
    season_open    TEXT,
    season_close   TEXT,
    license_type   TEXT,                   -- 'general', 'limited entry', ...
    notes          TEXT,
    collected_at   TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (district, species, year)
);

-- Filled later by the conditions agent (closures, fire, snow).
CREATE TABLE IF NOT EXISTS conditions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    district       TEXT,
    kind           TEXT,                   -- 'fire closure', 'road closure', 'weather'
    description    TEXT,
    starts         TEXT,
    ends           TEXT,
    source_url     TEXT,
    collected_at   TEXT DEFAULT (datetime('now'))
);

-- Every agent logs each run here so you can see what happened.
CREATE TABLE IF NOT EXISTS agent_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    agent          TEXT NOT NULL,
    started_at     TEXT DEFAULT (datetime('now')),
    rows_written   INTEGER,
    status         TEXT,                   -- 'ok' or 'error'
    message        TEXT
);
"""


def connect():
    """Open the database (creating tables if needed)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def log_run(conn, agent, rows, status, message=""):
    conn.execute(
        "INSERT INTO agent_runs (agent, rows_written, status, message) VALUES (?, ?, ?, ?)",
        (agent, rows, status, message),
    )
    conn.commit()


if __name__ == "__main__":
    conn = connect()
    tables = [r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    print(f"Database ready at {DB_PATH}")
    print("Tables:", ", ".join(tables))
