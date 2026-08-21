"""Order Engine: 現実的な価格で注文を約定させる。BUYはAsk側、SELLはBid側を
基準にスリッページを加える(実際のBid/Askは無料データに含まれないため、
相対出来高から合成した近似スプレッド/スリッページを使う)。約定を前提とせず、
Limit注文は価格到達だけでは即約定させない。
"""

from dataclasses import dataclass
from datetime import datetime

from ..market_data.liquidity import estimate_slippage_pct
from ..market_data.provider import Candle


@dataclass
class Fill:
    price: float
    timestamp: datetime
    slippage_pct: float


def simulate_market_fill(
    side: str, quote_price: float, relative_volume: float, timestamp: datetime
) -> Fill:
    """成行注文の約定シミュレーション。BUYはAsk側(価格+スリッページ)、
    SELLはBid側(価格-スリッページ)に寄せる。流動性が低いほどスリッページを増やす。
    """
    slip_pct = estimate_slippage_pct(relative_volume)
    if side == "BUY":
        fill_price = quote_price * (1 + slip_pct)
    else:  # SELL
        fill_price = quote_price * (1 - slip_pct)
    return Fill(price=fill_price, timestamp=timestamp, slippage_pct=slip_pct)


def check_limit_fill(
    side: str, limit_price: float, candle: Candle, relative_volume: float
) -> Fill | None:
    """指値注文は「価格に到達しただけ」では約定させない。ローソク足のレンジ内に
    価格が到達し、かつそのバーの出来高が薄すぎない場合のみ約定したとみなす簡易モデル。
    """
    touched = candle.low <= limit_price <= candle.high
    if not touched:
        return None

    min_volume_for_confidence = 500
    if candle.volume < min_volume_for_confidence:
        return None  # このバーでは板の厚みが不十分だったとみなし、約定させない

    slip_pct = estimate_slippage_pct(relative_volume) * 0.5  # 指値は成行よりスリッページが小さい
    return Fill(price=limit_price, timestamp=candle.timestamp, slippage_pct=slip_pct)


def check_stop_trigger(side: str, stop_price: float, candle: Candle) -> bool:
    """このバー中にストップが発火したかどうか。"""
    if side == "LONG":  # ロングのストップは売り(下抜けで発火)
        return candle.low <= stop_price
    else:  # SHORTのストップは買い(上抜けで発火)
        return candle.high >= stop_price


def evaluate_open_positions_for_exit(positions, candle_by_ticker: dict):
    """保有中の全ポジションについて、最新バーとストップ/利確を突き合わせ、
    条件を満たしたものを決定論的に決済対象として返す。Claudeは呼び出さない。
    """
    exits = []
    for position in positions:
        candle = candle_by_ticker.get(position.ticker)
        if candle is None:
            continue

        side = "LONG" if position.quantity > 0 else "SHORT"
        stop_hit = check_stop_trigger(side, position.stop_loss, candle)

        target_hit = False
        if position.take_profit_1 is not None:
            if side == "LONG":
                target_hit = candle.high >= position.take_profit_1
            else:
                target_hit = candle.low <= position.take_profit_1

        if stop_hit or target_hit:
            # ストップと利確が同一バーで両方ヒットし得る場合は、保守的にストップ優先とする
            exit_price = position.stop_loss if stop_hit else position.take_profit_1
            reason = "STOP_LOSS" if stop_hit else "TAKE_PROFIT"
            exits.append((position, exit_price, reason, candle.timestamp))

    return exits
