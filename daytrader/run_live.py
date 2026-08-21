"""LIVE MODE メインループ。

python -m daytrader.run_live で起動する(米国市場の取引時間中に、ローカルで
実行することを想定 — CCRクラウドの/scheduleは最短1時間間隔のため使えない)。

各ティックの処理順序(厳守):
  1. 現在時刻の最新市場データを取得
  2. 保有ポジションのSL/TPを機械的に監視・決済(Claudeは呼ばない)
  3. Scannerで候補銘柄を絞り込む
  4. 各候補についてMarketSnapshotを構築(as_of時点までのデータのみ)し、
     Trading Skill(Claude)に判断させる
  5. 判断内容をJournalに不可変記録
  6. Risk Managerが承認すればOrder Engineが約定、Portfolioを更新
  7. 次のティックへ

一度記録した判断・約定結果は遡及的に書き換えない。
"""

import time
from datetime import datetime, timezone

from . import config, db
from .execution import order_engine
from .journal import journal
from .market_data.engine import MarketDataEngine
from .market_data.provider import PriceUnavailableError, YFinanceProvider
from .portfolio import portfolio
from .risk_manager import risk_manager
from .scanner import scanner
from .skills.base import MarketSnapshot
from .skills.vwap_breakout import VwapBreakoutSkill

_CANDLES_FOR_INDICATORS = 390  # 1トレーディングセッション分(9:30-16:00 ET)


def _compute_indicators(candles_1m: list) -> dict:
    if not candles_1m:
        return {"vwap": None, "ema_9": None, "ema_20": None, "rsi_14": None, "atr_14": None}

    closes = [c.close for c in candles_1m]
    volumes = [c.volume for c in candles_1m]
    typical_prices = [(c.high + c.low + c.close) / 3 for c in candles_1m]
    cum_vol = sum(volumes) or 1.0
    vwap = sum(tp * v for tp, v in zip(typical_prices, volumes)) / cum_vol

    def ema(values, period):
        if len(values) < period:
            return None
        k = 2 / (period + 1)
        e = sum(values[:period]) / period
        for v in values[period:]:
            e = v * k + e * (1 - k)
        return e

    def rsi(values, period=14):
        if len(values) < period + 1:
            return None
        gains, losses = [], []
        for i in range(1, period + 1):
            change = values[i] - values[i - 1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def atr(cs, period=14):
        if len(cs) < period + 1:
            return None
        trs = []
        for i in range(1, len(cs)):
            high, low, prev_close = cs[i].high, cs[i].low, cs[i - 1].close
            trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        return sum(trs[-period:]) / period

    return {
        "vwap": vwap,
        "ema_9": ema(closes, 9),
        "ema_20": ema(closes, 20),
        "rsi_14": rsi(closes),
        "atr_14": atr(candles_1m),
    }


def run_tick(conn, engine: MarketDataEngine, skill, trade_date: str) -> None:
    now = datetime.now(timezone.utc)

    # --- 2. 保有ポジションのSL/TPを機械的に監視・決済 ---
    open_positions = portfolio.get_open_positions(conn)
    latest_candle_by_ticker = {}
    for pos in open_positions:
        try:
            c = engine.get_candles(pos.ticker, "1m", 1)
        except PriceUnavailableError:
            continue
        if c:
            latest_candle_by_ticker[pos.ticker] = c[-1]

    exits = order_engine.evaluate_open_positions_for_exit(open_positions, latest_candle_by_ticker)
    for position, exit_price, reason, exit_time in exits:
        slip_pct = 0.0  # ストップ/利確はその価格自体で発火する想定のため追加スリッページは付与しない
        portfolio.close_position(conn, position, exit_price, exit_time, reason, slip_pct, trade_date)
        print(f"[exit] {position.ticker} {reason} @ {exit_price:.2f}")

    # --- 3. Scannerで候補銘柄を絞り込む ---
    candidates = scanner.get_candidates(engine)

    open_tickers = {p.ticker for p in portfolio.get_open_positions(conn)}
    trades_today = portfolio.get_trades_count_today(conn, trade_date)
    consecutive_losses = portfolio.get_consecutive_losses(conn, trade_date)
    daily_pnl = portfolio.get_realized_pnl_today(conn, trade_date)
    daily_loss_limit_dollars = config.INITIAL_CAPITAL_USD * config.MAX_DAILY_LOSS_PCT

    for ticker in candidates:
        if ticker in open_tickers:
            continue
        if trades_today >= config.MAX_TRADES_PER_DAY:
            break
        if consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
            break

        try:
            candles_1m = engine.get_candles(ticker, "1m", _CANDLES_FOR_INDICATORS)
            candles_5m = engine.get_candles(ticker, "5m", 20)
        except PriceUnavailableError:
            continue
        if not candles_1m:
            continue

        indicators = _compute_indicators(candles_1m)
        scan_results = scanner.scan(engine, [ticker])
        relative_volume = scan_results[0].relative_volume if scan_results else 1.0

        current_candle = candles_1m[-1]
        equity = portfolio.get_account_equity(conn, {ticker: current_candle.close})

        # --- 4. MarketSnapshotを構築しTrading Skillに判断させる ---
        snapshot = MarketSnapshot(
            as_of=now,
            ticker=ticker,
            price=current_candle.close,
            candles_1m=candles_1m,
            candles_5m=candles_5m,
            vwap=indicators["vwap"],
            ema_9=indicators["ema_9"],
            ema_20=indicators["ema_20"],
            rsi_14=indicators["rsi_14"],
            atr_14=indicators["atr_14"],
            relative_volume=relative_volume,
            account_equity=equity,
            current_position_qty=0,
            trades_today=trades_today,
            daily_pnl=daily_pnl,
            consecutive_losses=consecutive_losses,
        )

        decision = skill.decide(snapshot)

        risk_decision = risk_manager.evaluate(
            decision, equity, trades_today, consecutive_losses, daily_pnl, daily_loss_limit_dollars,
        )

        # --- 5. 判断内容をJournalに不可変記録 ---
        decision_id = journal.record_decision(conn, now, decision, risk_decision)
        print(
            f"[decision] {ticker} {decision.action} strategy={decision.strategy} "
            f"approved={risk_decision.approved} ({risk_decision.reason})"
        )

        # --- 6. Risk Managerが承認すればOrder Engineが約定 ---
        if decision.action == "NO_TRADE" or not risk_decision.approved:
            continue

        if decision.entry_type == "LIMIT" and decision.entry_price is not None:
            fill = order_engine.check_limit_fill(decision.action, decision.entry_price, current_candle, relative_volume)
            if fill is None:
                continue  # このバーでは約定せず。判断自体はJournalに記録済み
        else:
            fill = order_engine.simulate_market_fill(decision.action, current_candle.close, relative_volume, now)

        quantity = risk_decision.position_size if decision.action == "BUY" else -risk_decision.position_size
        portfolio.open_position(
            conn, decision_id, ticker, quantity, fill.price, fill.slippage_pct,
            decision.stop_loss, decision.take_profit_1, now,
        )
        trades_today += 1
        print(f"[fill] {ticker} {decision.action} {abs(quantity)}株 @ {fill.price:.2f}")

    portfolio.record_equity_snapshot(conn, now, {})


def main(poll_interval_seconds: int = 60, max_iterations: int | None = None) -> None:
    conn = db.get_connection()
    provider = YFinanceProvider()
    engine = MarketDataEngine(provider)
    skill = VwapBreakoutSkill()

    iteration = 0
    try:
        while max_iterations is None or iteration < max_iterations:
            trade_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            try:
                run_tick(conn, engine, skill, trade_date)
            except Exception as e:
                print(f"[run_live] tick error: {e}")

            iteration += 1
            if max_iterations is not None and iteration >= max_iterations:
                break
            time.sleep(poll_interval_seconds)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
