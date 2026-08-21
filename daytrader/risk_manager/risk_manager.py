"""Risk Manager: Trading Skillの提案(BUY/SELL)を承認するかどうかを判定し、
承認する場合はストップまでの距離と最大許容損失からポジションサイズを計算する。
HARD RULESはここに固定実装し、Skill側から変更できないようにする。
"""

from dataclasses import dataclass

from .. import config
from ..skills.base import TradeDecision


@dataclass
class RiskDecision:
    approved: bool
    reason: str
    position_size: float = 0.0
    risk_dollars: float = 0.0


def evaluate(
    decision: TradeDecision,
    account_equity: float,
    trades_today: int,
    consecutive_losses: int,
    daily_pnl: float,
    daily_loss_limit_dollars: float,
) -> RiskDecision:
    if decision.action == "NO_TRADE":
        return RiskDecision(approved=True, reason="NO_TRADE is always acceptable")

    # HARD RULE: 最大連敗数に達したら取引停止
    if consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
        return RiskDecision(approved=False, reason="max consecutive losses reached; trading halted for today")

    # HARD RULE: 1日の最大取引数
    if trades_today >= config.MAX_TRADES_PER_DAY:
        return RiskDecision(approved=False, reason="max trades per day reached")

    # HARD RULE: 1日の最大損失
    if daily_pnl <= -abs(daily_loss_limit_dollars):
        return RiskDecision(approved=False, reason="max daily loss reached; trading halted for today")

    # HARD RULE: ストップロス無しのエントリーは禁止
    if decision.entry_price is None or decision.stop_loss is None:
        return RiskDecision(approved=False, reason="entry requires both entry_price and stop_loss")

    risk_per_share = abs(decision.entry_price - decision.stop_loss)
    if risk_per_share <= 0:
        return RiskDecision(approved=False, reason="invalid stop_loss (zero distance from entry)")

    # ポジションサイズ = 最大許容損失額 ÷ 1株あたりの損失(固定株数ではない)
    max_risk_dollars = account_equity * config.MAX_RISK_PER_TRADE_PCT
    position_size = int(max_risk_dollars // risk_per_share)

    if position_size <= 0:
        return RiskDecision(
            approved=False,
            reason="computed position size is zero (risk too small relative to stop distance)",
        )

    # HARD RULE: 最大ポジションサイズの上限
    max_position_value = account_equity * config.MAX_POSITION_VALUE_PCT
    max_shares_by_value = int(max_position_value // decision.entry_price)
    position_size = min(position_size, max_shares_by_value)
    if position_size <= 0:
        return RiskDecision(approved=False, reason="position size capped to zero by max position value limit")

    actual_risk_dollars = position_size * risk_per_share
    return RiskDecision(
        approved=True,
        reason="approved",
        position_size=position_size,
        risk_dollars=actual_risk_dollars,
    )


def can_adjust_stop(current_stop: float, new_stop: float, side: str) -> bool:
    """HARD RULE: 建値後にストップを不利な方向へ広げることは禁止(タイトにするのはOK)。"""
    if side == "LONG":
        return new_stop >= current_stop
    return new_stop <= current_stop
