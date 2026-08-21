import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

import config
import market_data


@dataclass
class TradeResult:
    status: str  # "executed" | "rejected" | "hold"
    message: str
    trade_id: int | None


def get_holdings(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT ticker,
               SUM(CASE WHEN action = 'buy' THEN quantity ELSE 0 END) -
               SUM(CASE WHEN action = 'sell' THEN quantity ELSE 0 END) AS qty
        FROM trades
        WHERE status = 'executed' AND action IN ('buy', 'sell')
        GROUP BY ticker
        HAVING qty > 0
        """
    ).fetchall()
    return {row["ticker"]: row["qty"] for row in rows}


def get_holdings_with_cost(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT ticker, action, quantity, price_jpy_equivalent, timestamp
        FROM trades
        WHERE status = 'executed' AND action IN ('buy', 'sell')
        ORDER BY timestamp ASC
        """
    ).fetchall()

    holdings: dict = {}
    for row in rows:
        ticker = row["ticker"]
        h = holdings.setdefault(ticker, {"quantity": 0.0, "avg_cost_jpy": 0.0})
        if row["action"] == "buy":
            total_cost = h["quantity"] * h["avg_cost_jpy"] + row["quantity"] * row["price_jpy_equivalent"]
            h["quantity"] += row["quantity"]
            h["avg_cost_jpy"] = total_cost / h["quantity"] if h["quantity"] > 0 else 0.0
        else:  # sell
            h["quantity"] -= row["quantity"]
            if h["quantity"] <= 0:
                h["quantity"] = 0.0
                h["avg_cost_jpy"] = 0.0

    return {t: h for t, h in holdings.items() if h["quantity"] > 0}


def get_cash_balance_jpy(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        """
        SELECT
            SUM(CASE WHEN action = 'buy' THEN total_jpy ELSE 0 END) AS bought,
            SUM(CASE WHEN action = 'sell' THEN total_jpy ELSE 0 END) AS sold
        FROM trades
        WHERE status = 'executed'
        """
    ).fetchone()
    bought = row["bought"] or 0.0
    sold = row["sold"] or 0.0
    return config.INITIAL_CAPITAL_JPY - bought + sold


def get_portfolio_value_jpy(conn: sqlite3.Connection, live_prices_jpy: dict | None = None):
    """live_prices_jpy: optional {ticker: price_in_jpy} to avoid refetching quotes."""
    cash = get_cash_balance_jpy(conn)
    holdings = get_holdings(conn)

    holdings_value = 0.0
    fx_rate = None
    for ticker, qty in holdings.items():
        price_jpy = (live_prices_jpy or {}).get(ticker)
        if price_jpy is None:
            try:
                quote = market_data.get_quote(ticker)
                if quote["currency"] == "USD":
                    if fx_rate is None:
                        fx_rate = market_data.get_fx_rate_usdjpy()
                    price_jpy = quote["price"] * fx_rate
                else:
                    price_jpy = quote["price"]
            except market_data.PriceUnavailableError:
                price_jpy = 0.0
        holdings_value += price_jpy * qty

    total = cash + holdings_value
    return cash, holdings_value, total


def record_snapshot(conn: sqlite3.Connection) -> None:
    cash, holdings_value, total = get_portfolio_value_jpy(conn)
    conn.execute(
        """
        INSERT INTO portfolio_snapshots (timestamp, cash_jpy, holdings_value_jpy, total_value_jpy)
        VALUES (?, ?, ?, ?)
        """,
        (datetime.now(timezone.utc).isoformat(), cash, holdings_value, total),
    )
    conn.commit()


def _insert_trade(conn, ticker, action, quantity, price, currency, fx_rate,
                   price_jpy_equivalent, total_jpy, decided_by, reasoning,
                   model_used, status) -> int:
    cur = conn.execute(
        """
        INSERT INTO trades (
            timestamp, ticker, action, quantity, price, currency,
            fx_rate_usdjpy, price_jpy_equivalent, total_jpy,
            decided_by, reasoning, model_used, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            ticker, action, quantity, price, currency, fx_rate,
            price_jpy_equivalent, total_jpy, decided_by, reasoning,
            model_used, status,
        ),
    )
    conn.commit()
    return cur.lastrowid


def execute_trade(
    conn: sqlite3.Connection,
    ticker: str,
    action: str,
    quantity: float,
    decided_by: str,
    reasoning: str,
    model_used: str | None = None,
) -> TradeResult:
    action = action.lower()
    if action not in ("buy", "sell", "hold"):
        return TradeResult("rejected", f"Unknown action '{action}'", None)

    if action == "hold":
        trade_id = _insert_trade(
            conn, ticker, "hold", 0, None, None, None, None, 0,
            decided_by, reasoning, model_used, "hold",
        )
        return TradeResult("hold", f"Hold recorded for {ticker}", trade_id)

    if quantity is None or quantity <= 0:
        trade_id = _insert_trade(
            conn, ticker, action, quantity or 0, None, None, None, None, None,
            decided_by, reasoning, model_used, "rejected",
        )
        return TradeResult("rejected", "Quantity must be greater than 0", trade_id)

    try:
        quote = market_data.get_quote(ticker)
    except market_data.PriceUnavailableError as e:
        trade_id = _insert_trade(
            conn, ticker, action, quantity, None, None, None, None, None,
            decided_by, f"{reasoning} | price fetch failed: {e}", model_used, "rejected",
        )
        return TradeResult("rejected", str(e), trade_id)

    price = quote["price"]
    currency = quote["currency"]
    fx_rate = None
    if currency == "USD":
        fx_rate = market_data.get_fx_rate_usdjpy()
        price_jpy_equivalent = price * fx_rate
    else:
        price_jpy_equivalent = price
    total_jpy = quantity * price_jpy_equivalent

    if action == "buy":
        cash = get_cash_balance_jpy(conn)
        if total_jpy > cash:
            trade_id = _insert_trade(
                conn, ticker, action, quantity, price, currency, fx_rate,
                price_jpy_equivalent, total_jpy, decided_by,
                f"{reasoning} | rejected: insufficient cash (need ¥{total_jpy:,.0f}, have ¥{cash:,.0f})",
                model_used, "rejected",
            )
            return TradeResult("rejected", "Insufficient cash", trade_id)

    if action == "sell":
        holdings = get_holdings(conn)
        held = holdings.get(ticker, 0)
        if quantity > held:
            trade_id = _insert_trade(
                conn, ticker, action, quantity, price, currency, fx_rate,
                price_jpy_equivalent, total_jpy, decided_by,
                f"{reasoning} | rejected: insufficient shares (have {held}, tried to sell {quantity})",
                model_used, "rejected",
            )
            return TradeResult("rejected", "Insufficient shares held", trade_id)

    trade_id = _insert_trade(
        conn, ticker, action, quantity, price, currency, fx_rate,
        price_jpy_equivalent, total_jpy, decided_by, reasoning, model_used, "executed",
    )
    record_snapshot(conn)
    return TradeResult(
        "executed",
        f"{action} {quantity} {ticker} @ ¥{price_jpy_equivalent:,.2f} (total ¥{total_jpy:,.0f})",
        trade_id,
    )
