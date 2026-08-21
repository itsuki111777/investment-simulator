"""Portfolio Engine: 現金・保有ポジション・資産評価額・日次カウンター(取引数/
連敗数/実現損益)を管理する。クローズ済みトレードの不可変な記録自体は
journal.record_trade() が担当し、ここではその結果を使って日次統計と
ポジションの状態(OPEN→CLOSED)を更新する。
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from .. import config
from ..journal import journal


@dataclass
class Position:
    id: int
    decision_id: int
    ticker: str
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit_1: float | None
    entry_time: str


def ensure_daily_stats_row(conn: sqlite3.Connection, trade_date: str, starting_equity: float) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO daily_stats (trade_date, trades_count, realized_pnl_dollars, consecutive_losses, starting_equity)
        VALUES (?, 0, 0, 0, ?)
        """,
        (trade_date, starting_equity),
    )
    conn.commit()


def get_trades_count_today(conn: sqlite3.Connection, trade_date: str) -> int:
    row = conn.execute("SELECT trades_count FROM daily_stats WHERE trade_date = ?", (trade_date,)).fetchone()
    return row["trades_count"] if row else 0


def get_consecutive_losses(conn: sqlite3.Connection, trade_date: str) -> int:
    row = conn.execute("SELECT consecutive_losses FROM daily_stats WHERE trade_date = ?", (trade_date,)).fetchone()
    return row["consecutive_losses"] if row else 0


def get_realized_pnl_today(conn: sqlite3.Connection, trade_date: str) -> float:
    row = conn.execute(
        "SELECT realized_pnl_dollars FROM daily_stats WHERE trade_date = ?", (trade_date,)
    ).fetchone()
    return row["realized_pnl_dollars"] if row else 0.0


def get_cash(conn: sqlite3.Connection) -> float:
    closed_pnl = conn.execute("SELECT COALESCE(SUM(pnl_dollars), 0) AS total FROM trades").fetchone()["total"]
    open_cost = conn.execute(
        "SELECT COALESCE(SUM(quantity * entry_price), 0) AS total FROM positions WHERE status = 'OPEN'"
    ).fetchone()["total"]
    return config.INITIAL_CAPITAL_USD + closed_pnl - open_cost


def get_open_positions(conn: sqlite3.Connection) -> list[Position]:
    rows = conn.execute("SELECT * FROM positions WHERE status = 'OPEN'").fetchall()
    return [
        Position(
            id=r["id"],
            decision_id=r["decision_id"],
            ticker=r["ticker"],
            quantity=r["quantity"],
            entry_price=r["entry_price"],
            stop_loss=r["stop_loss"],
            take_profit_1=r["take_profit_1"],
            entry_time=r["entry_time"],
        )
        for r in rows
    ]


def get_account_equity(conn: sqlite3.Connection, current_prices: dict) -> float:
    cash = get_cash(conn)
    positions_value = 0.0
    for pos in get_open_positions(conn):
        price = current_prices.get(pos.ticker, pos.entry_price)
        positions_value += pos.quantity * price
    return cash + positions_value


def open_position(
    conn: sqlite3.Connection,
    decision_id: int,
    ticker: str,
    quantity: float,
    entry_price: float,
    entry_slippage_pct: float,
    stop_loss: float,
    take_profit_1: float | None,
    entry_time,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO positions (
            decision_id, ticker, quantity, entry_price, entry_slippage_pct,
            stop_loss, take_profit_1, entry_time, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
        """,
        (decision_id, ticker, quantity, entry_price, entry_slippage_pct, stop_loss, take_profit_1, str(entry_time)),
    )
    conn.commit()
    return cur.lastrowid


def close_position(
    conn: sqlite3.Connection,
    position: Position,
    exit_price: float,
    exit_time,
    exit_reason: str,
    exit_slippage_pct: float,
    trade_date: str,
) -> dict:
    result = journal.record_trade(conn, position, exit_price, exit_time, exit_reason, exit_slippage_pct)

    conn.execute("UPDATE positions SET status = 'CLOSED' WHERE id = ?", (position.id,))

    ensure_daily_stats_row(conn, trade_date, config.INITIAL_CAPITAL_USD)
    is_loss = result["pnl_dollars"] < 0
    conn.execute(
        """
        UPDATE daily_stats SET
            trades_count = trades_count + 1,
            realized_pnl_dollars = realized_pnl_dollars + ?,
            consecutive_losses = CASE WHEN ? THEN consecutive_losses + 1 ELSE 0 END
        WHERE trade_date = ?
        """,
        (result["pnl_dollars"], int(is_loss), trade_date),
    )
    conn.commit()
    return result


def record_equity_snapshot(conn: sqlite3.Connection, timestamp, current_prices: dict) -> None:
    cash = get_cash(conn)
    positions_value = 0.0
    for pos in get_open_positions(conn):
        price = current_prices.get(pos.ticker, pos.entry_price)
        positions_value += pos.quantity * price
    conn.execute(
        "INSERT INTO equity_curve (timestamp, cash, positions_value, total_equity) VALUES (?, ?, ?, ?)",
        (str(timestamp), cash, positions_value, cash + positions_value),
    )
    conn.commit()
