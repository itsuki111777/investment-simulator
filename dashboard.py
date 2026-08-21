from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import config
import db
import market_data
import portfolio

JST = ZoneInfo("Asia/Tokyo")

ACTION_JA = {"buy": "買い", "sell": "売り", "hold": "見送り"}
STATUS_JA = {"executed": "実行済み", "rejected": "拒否", "hold": "見送り"}
DECIDED_BY_JA = {"claude_api": "Claude API(自動)", "claude_code_manual": "Claude Code(手動/クラウド)"}
MARKET_JA = {"US": "米国", "JP": "日本"}

st.set_page_config(page_title="投資シミュレーター", layout="wide")


@st.cache_data(ttl=60)
def cached_market_snapshot():
    return market_data.get_market_snapshot(config.WATCHLIST)


def get_conn():
    return db.get_connection()


def to_jst_str(iso_str, fmt="%Y-%m-%d %H:%M"):
    if not iso_str:
        return ""
    dt = pd.to_datetime(iso_str, utc=True).tz_convert(JST)
    return dt.strftime(fmt)


def next_scheduled_run_utc(now_utc: datetime) -> datetime:
    interval = config.ROUTINE_INTERVAL_HOURS
    minute = config.ROUTINE_CRON_MINUTE
    candidate = now_utc.replace(minute=minute, second=0, microsecond=0)
    if candidate <= now_utc:
        candidate += timedelta(hours=1)
    while candidate.hour % interval != 0:
        candidate += timedelta(hours=1)
    return candidate


def tradingview_mini_widget(tv_exchange: str, tv_symbol: str, height: int = 160) -> str:
    symbol = f"{tv_exchange}:{tv_symbol}"
    return f"""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript"
        src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
      {{
        "symbol": "{symbol}",
        "width": "100%",
        "height": "{height}",
        "locale": "ja",
        "dateRange": "1M",
        "colorTheme": "light",
        "isTransparent": false,
        "autosize": true,
        "largeChartUrl": ""
      }}
      </script>
    </div>
    """


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

now_utc = datetime.now(timezone.utc)
next_run_utc = next_scheduled_run_utc(now_utc)
remaining = next_run_utc - now_utc
remaining_h, remaining_rem = divmod(int(remaining.total_seconds()), 3600)
remaining_m = remaining_rem // 60

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("総資産", f"¥{total:,.0f}")
col2.metric("現金", f"¥{cash:,.0f}")
col3.metric("保有評価額", f"¥{holdings_value:,.0f}")
col4.metric("損益", f"¥{pnl:,.0f}", f"{pnl_pct:+.2f}%")
col5.metric(
    "次回自動売買まで",
    f"{remaining_h}時間{remaining_m}分",
    help=f"予定時刻: {next_run_utc.astimezone(JST).strftime('%Y-%m-%d %H:%M')} (JST)",
)

tab_overview, tab_holdings, tab_history, tab_watchlist = st.tabs(
    ["資産推移", "保有銘柄", "売買履歴", "ウォッチリスト"]
)

with tab_overview:
    snapshots = conn.execute(
        "SELECT timestamp, total_value_jpy FROM portfolio_snapshots ORDER BY timestamp ASC"
    ).fetchall()
    if snapshots:
        df_snap = pd.DataFrame(snapshots, columns=["timestamp", "total_value_jpy"])
        df_snap["日時"] = pd.to_datetime(df_snap["timestamp"], utc=True).dt.tz_convert(JST)
        df_snap = df_snap.rename(columns={"total_value_jpy": "総資産(円)"})
        st.line_chart(df_snap.set_index("日時")["総資産(円)"])
    else:
        st.info("まだスナップショットがありません。取引を行うか、サイドバーから記録してください。")

with tab_holdings:
    holdings = portfolio.get_holdings_with_cost(conn)
    if holdings:
        rows = []
        for ticker, h in holdings.items():
            live_jpy = live_prices_jpy.get(ticker)
            market_value = live_jpy * h["quantity"] if live_jpy is not None else None
            unrealized_pnl = (
                (live_jpy - h["avg_cost_jpy"]) * h["quantity"] if live_jpy is not None else None
            )
            entry = next((e for e in config.WATCHLIST if e["ticker"] == ticker), {})
            rows.append(
                {
                    "銘柄": ticker,
                    "銘柄名": entry.get("name", ticker),
                    "数量": h["quantity"],
                    "平均取得単価(円)": round(h["avg_cost_jpy"], 2),
                    "現在値(円)": round(live_jpy, 2) if live_jpy is not None else None,
                    "評価額(円)": round(market_value, 0) if market_value is not None else None,
                    "評価損益(円)": round(unrealized_pnl, 0) if unrealized_pnl is not None else None,
                }
            )
        df_holdings = pd.DataFrame(rows)
        st.dataframe(
            df_holdings,
            use_container_width=True,
            hide_index=True,
            column_config={
                "評価損益(円)": st.column_config.NumberColumn(format="¥%d"),
                "評価額(円)": st.column_config.NumberColumn(format="¥%d"),
                "平均取得単価(円)": st.column_config.NumberColumn(format="¥%.2f"),
                "現在値(円)": st.column_config.NumberColumn(format="¥%.2f"),
            },
        )

        st.subheader("直近の値動き")
        tickers_held = list(holdings.keys())
        cols = st.columns(3)
        for i, ticker in enumerate(tickers_held):
            entry = next((e for e in config.WATCHLIST if e["ticker"] == ticker), None)
            if entry is None:
                continue
            with cols[i % 3]:
                st.caption(f"{entry.get('name', ticker)} ({ticker})")
                components.html(
                    tradingview_mini_widget(entry["tv_exchange"], entry["tv_symbol"]),
                    height=170,
                )
    else:
        st.info("保有銘柄なし")

with tab_history:
    filter_col1, filter_col2 = st.columns(2)
    decided_by_filter = filter_col1.selectbox(
        "判断主体", ["すべて", "Claude API(自動)", "Claude Code(手動/クラウド)"]
    )
    status_filter = filter_col2.selectbox("ステータス", ["すべて", "実行済み", "拒否", "見送り"])

    trades = conn.execute("SELECT * FROM trades ORDER BY timestamp DESC").fetchall()
    if trades:
        df_trades = pd.DataFrame([dict(row) for row in trades])
        df_trades["decided_by_ja"] = df_trades["decided_by"].map(DECIDED_BY_JA)
        df_trades["status_ja"] = df_trades["status"].map(STATUS_JA)

        if decided_by_filter != "すべて":
            df_trades = df_trades[df_trades["decided_by_ja"] == decided_by_filter]
        if status_filter != "すべて":
            df_trades = df_trades[df_trades["status_ja"] == status_filter]

        df_trades["日時"] = df_trades["timestamp"].apply(to_jst_str)
        df_trades["種別"] = df_trades["action"].map(ACTION_JA)

        display_df = df_trades[
            [
                "日時", "ticker", "種別", "quantity", "price", "currency",
                "price_jpy_equivalent", "total_jpy", "decided_by_ja", "status_ja",
                "reasoning", "model_used",
            ]
        ].rename(
            columns={
                "ticker": "銘柄",
                "quantity": "数量",
                "price": "価格(現地通貨)",
                "currency": "通貨",
                "price_jpy_equivalent": "円換算価格",
                "total_jpy": "合計(円)",
                "decided_by_ja": "判断主体",
                "status_ja": "ステータス",
                "reasoning": "理由",
                "model_used": "使用モデル",
            }
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("該当する取引履歴がありません")

with tab_watchlist:
    rows = []
    for item in snapshot:
        if "error" in item:
            rows.append(
                {
                    "銘柄名": item.get("name"),
                    "コード": item["ticker"],
                    "市場": MARKET_JA.get(item.get("market"), item.get("market")),
                    "価格": None,
                    "通貨": None,
                    "前日比(%)": None,
                    "円換算": None,
                    "備考": "取得失敗",
                }
            )
            continue
        rows.append(
            {
                "銘柄名": item.get("name"),
                "コード": item["ticker"],
                "市場": MARKET_JA.get(item.get("market"), item.get("market")),
                "価格": round(item["price"], 2),
                "通貨": item["currency"],
                "前日比(%)": round(item["day_change_pct"], 2) if item.get("day_change_pct") is not None else None,
                "円換算": round(item["price_jpy_equivalent"], 2),
                "備考": "",
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with st.sidebar:
    st.header("設定")
    st.write(f"初期資金: ¥{config.INITIAL_CAPITAL_JPY:,.0f}")
    st.write(f"基軸通貨: {config.BASE_CURRENCY}")
    st.write(f"ウォッチリスト銘柄数: {len(config.WATCHLIST)}")
    st.write(f"自動売買間隔: {config.ROUTINE_INTERVAL_HOURS}時間ごと")
    if st.button("今すぐスナップショット記録"):
        portfolio.record_snapshot(conn)
        st.success("記録しました")
        st.rerun()

conn.close()
