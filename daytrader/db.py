import os
import sqlite3

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    as_of                  TEXT NOT NULL,
    ticker                 TEXT NOT NULL,
    action                 TEXT NOT NULL CHECK(action IN ('BUY','SELL','NO_TRADE')),
    strategy               TEXT NOT NULL,
    entry_type             TEXT,
    entry_price            REAL,
    stop_loss              REAL,
    take_profit_1          REAL,
    take_profit_2          REAL,
    risk_reward_ratio       REAL,
    confidence             INTEGER,
    max_hold_minutes       INTEGER,
    reasoning               TEXT NOT NULL,
    invalidators             TEXT,
    risk_manager_approved   INTEGER NOT NULL,
    risk_manager_reason     TEXT,
    position_size           REAL,
    risk_dollars             REAL,
    created_at               TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id           INTEGER NOT NULL,
    ticker                TEXT NOT NULL,
    quantity              REAL NOT NULL,
    entry_price           REAL NOT NULL,
    entry_slippage_pct    REAL,
    stop_loss             REAL NOT NULL,
    take_profit_1         REAL,
    entry_time            TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','CLOSED')),
    FOREIGN KEY (decision_id) REFERENCES decisions(id)
);

CREATE TABLE IF NOT EXISTS trades (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id          INTEGER NOT NULL,
    decision_id          INTEGER NOT NULL,
    ticker               TEXT NOT NULL,
    quantity             REAL NOT NULL,
    entry_price          REAL NOT NULL,
    exit_price           REAL NOT NULL,
    entry_time           TEXT NOT NULL,
    exit_time            TEXT NOT NULL,
    exit_reason          TEXT NOT NULL,
    exit_slippage_pct    REAL,
    pnl_dollars          REAL NOT NULL,
    pnl_pct              REAL NOT NULL,
    r_multiple           REAL,
    holding_minutes      REAL,
    FOREIGN KEY (position_id) REFERENCES positions(id),
    FOREIGN KEY (decision_id) REFERENCES decisions(id)
);

CREATE TABLE IF NOT EXISTS daily_stats (
    trade_date            TEXT PRIMARY KEY,
    trades_count          INTEGER NOT NULL DEFAULT 0,
    realized_pnl_dollars  REAL NOT NULL DEFAULT 0,
    consecutive_losses    INTEGER NOT NULL DEFAULT 0,
    starting_equity       REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS equity_curve (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT NOT NULL,
    cash              REAL NOT NULL,
    positions_value   REAL NOT NULL,
    total_equity      REAL NOT NULL
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
