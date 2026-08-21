"""Trade Journal: Trading Skillの判断とクローズ済みトレードを不可変に記録する。
どちらのテーブルもINSERTのみで運用し、一度書き込んだ行は後から更新しない
(判断理由の遡及的な書き換え禁止というHARD RULEをここで担保する)。
"""

import json
import sqlite3
from datetime import datetime, timezone


def record_decision(conn: sqlite3.Connection, as_of, decision, risk_decision) -> int:
    cur = conn.execute(
        """
        INSERT INTO decisions (
            as_of, ticker, action, strategy, entry_type, entry_price, stop_loss,
            take_profit_1, take_profit_2, risk_reward_ratio, confidence,
            max_hold_minutes, reasoning, invalidators, risk_manager_approved,
            risk_manager_reason, position_size, risk_dollars, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(as_of),
            decision.ticker,
            decision.action,
            decision.strategy,
            decision.entry_type,
            decision.entry_price,
            decision.stop_loss,
            decision.take_profit_1,
            decision.take_profit_2,
            decision.risk_reward_ratio,
            decision.confidence,
            decision.max_hold_minutes,
            json.dumps(decision.reasoning, ensure_ascii=False),
            json.dumps(decision.invalidators, ensure_ascii=False),
            int(risk_decision.approved),
            risk_decision.reason,
            risk_decision.position_size,
            risk_decision.risk_dollars,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return cur.lastrowid


def record_trade(conn: sqlite3.Connection, position, exit_price, exit_time, exit_reason, exit_slippage_pct) -> dict:
    """クローズしたトレードを不可変な行として1回だけ書き込む。計算結果を
    呼び出し元(portfolio)に返し、日次統計の更新に使えるようにする。
    """
    entry_dt = datetime.fromisoformat(position.entry_time)
    exit_dt = exit_time if isinstance(exit_time, datetime) else datetime.fromisoformat(str(exit_time))

    pnl_dollars = (exit_price - position.entry_price) * position.quantity
    direction = 1 if position.quantity > 0 else -1
    pnl_pct = (exit_price - position.entry_price) / position.entry_price * direction * 100
    risk_per_share = abs(position.entry_price - position.stop_loss)
    r_multiple = (
        pnl_dollars / (risk_per_share * abs(position.quantity)) if risk_per_share > 0 else None
    )
    holding_minutes = (exit_dt - entry_dt).total_seconds() / 60

    conn.execute(
        """
        INSERT INTO trades (
            position_id, decision_id, ticker, quantity, entry_price, exit_price,
            entry_time, exit_time, exit_reason, exit_slippage_pct, pnl_dollars,
            pnl_pct, r_multiple, holding_minutes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            position.id,
            position.decision_id,
            position.ticker,
            position.quantity,
            position.entry_price,
            exit_price,
            position.entry_time,
            str(exit_dt),
            exit_reason,
            exit_slippage_pct,
            pnl_dollars,
            pnl_pct,
            r_multiple,
            holding_minutes,
        ),
    )
    conn.commit()

    return {
        "pnl_dollars": pnl_dollars,
        "pnl_pct": pnl_pct,
        "r_multiple": r_multiple,
        "holding_minutes": holding_minutes,
    }


def get_recent_decisions(conn: sqlite3.Connection, limit: int = 50):
    return conn.execute(
        "SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()


def get_trade_history(conn: sqlite3.Connection, limit: int = 100):
    return conn.execute(
        "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
