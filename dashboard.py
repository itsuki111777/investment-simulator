import pandas as pd
import streamlit as st

import config
import db
import market_data
import portfolio

st.set_page_config(page_title="投資シミュレーター", layout="wide")


@st.cache_data(ttl=60)
def cached_market_snapshot():
    return market_data.get_market_snapshot(config.WATCHLIST)


def get_conn():
    return db.get_connection()


st.title("仮想マネー投資シミュレーター")
st.caption("実際のリアルマネーは使用していません。株価データはTradingView(tradingview-ta)経由の実市場データです。")

conn = get_conn()

snapshot = cached_market_snapshot()
live_prices_jpy = {
    item["ticker"]: item["price_jpy_equivalent"]
    for item in snapshot
    if "error" not in item
}

failed_tickers = [item["ticker"] for item in snapshot if "error" in item]
if failed_tickers:
    st.warning(
        f"以下の銘柄は最新価格を取得できませんでした(取得単価で近似表示しています): {', '.join(failed_tickers)}"
    )

cash, holdings_value, total = portfolio.get_portfolio_value_jpy(conn, live_prices_jpy)
pnl = total - config.INITIAL_CAPITAL_JPY
pnl_pct = (pnl / config.INITIAL_CAPITAL_JPY) * 100

col1, col2, col3, col4 = st.columns(4)
col1.metric("総資産", f"¥{total:,.0f}")
col2.metric("現金", f"¥{cash:,.0f}")
col3.metric("保有評価額", f"¥{holdings_value:,.0f}")
col4.metric("損益", f"¥{pnl:,.0f}", f"{pnl_pct:+.2f}%")

st.subheader("資産推移")
snapshots = conn.execute(
    "SELECT timestamp, total_value_jpy FROM portfolio_snapshots ORDER BY timestamp ASC"
).fetchall()
if snapshots:
    df_snap = pd.DataFrame(snapshots, columns=["timestamp", "total_value_jpy"])
    df_snap["timestamp"] = pd.to_datetime(df_snap["timestamp"])
    st.line_chart(df_snap.set_index("timestamp"))
else:
    st.info("まだスナップショットがありません。取引を行うか、サイドバーから記録してください。")

st.subheader("保有銘柄")
holdings = portfolio.get_holdings_with_cost(conn)
if holdings:
    rows = []
    for ticker, h in holdings.items():
        live_jpy = live_prices_jpy.get(ticker)
        market_value = live_jpy * h["quantity"] if live_jpy is not None else None
        unrealized_pnl = (
            (live_jpy - h["avg_cost_jpy"]) * h["quantity"] if live_jpy is not None else None
        )
        rows.append(
            {
                "ticker": ticker,
                "quantity": h["quantity"],
                "avg_cost_jpy": h["avg_cost_jpy"],
                "live_price_jpy": live_jpy,
                "market_value_jpy": market_value,
                "unrealized_pnl_jpy": unrealized_pnl,
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
else:
    st.info("保有銘柄なし")

st.subheader("売買履歴")
filter_col1, filter_col2 = st.columns(2)
decided_by_filter = filter_col1.selectbox(
    "判断主体", ["すべて", "claude_api", "claude_code_manual"]
)
status_filter = filter_col2.selectbox("ステータス", ["すべて", "executed", "rejected", "hold"])

query = "SELECT * FROM trades WHERE 1=1"
params = []
if decided_by_filter != "すべて":
    query += " AND decided_by = ?"
    params.append(decided_by_filter)
if status_filter != "すべて":
    query += " AND status = ?"
    params.append(status_filter)
query += " ORDER BY timestamp DESC"

trades = conn.execute(query, params).fetchall()
if trades:
    df_trades = pd.DataFrame([dict(row) for row in trades])
    st.dataframe(df_trades, use_container_width=True)
else:
    st.info("該当する取引履歴がありません")

st.subheader("ウォッチリスト")
st.dataframe(pd.DataFrame(snapshot), use_container_width=True)

with st.sidebar:
    st.header("設定")
    st.write(f"初期資金: ¥{config.INITIAL_CAPITAL_JPY:,.0f}")
    st.write(f"基軸通貨: {config.BASE_CURRENCY}")
    st.write(f"ウォッチリスト銘柄数: {len(config.WATCHLIST)}")
    if st.button("今すぐスナップショット記録"):
        portfolio.record_snapshot(conn)
        st.success("記録しました")
        st.rerun()

conn.close()
