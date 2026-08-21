import os
import sqlite3

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp             TEXT NOT NULL,
    ticker                TEXT NOT NULL,
    action                TEXT NOT NULL CHECK(action IN ('buy','sell','hold')),
    quantity              REAL NOT NULL DEFAULT 0,
    price                 REAL,
    currency              TEXT CHECK(currency IN ('USD','JPY')),
    fx_rate_usdjpy        REAL,
    price_jpy_equivalent  REAL,
    total_jpy             REAL,
    decided_by            TEXT NOT NULL CHECK(decided_by IN ('claude_api','claude_code_manual')),
    reasoning              TEXT,
    model_used            TEXT,
    status                TEXT NOT NULL DEFAULT 'executed' CHECK(status IN ('executed','rejected','hold'))
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp          TEXT NOT NULL,
    cash_jpy           REAL NOT NULL,
    holdings_value_jpy REAL NOT NULL,
    total_value_jpy    REAL NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


if __name__ == "__main__":
    conn = get_connection()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print(f"DB initialized at {config.DB_PATH}")
    print("Tables:", ", ".join(row["name"] for row in tables))
    conn.close()
