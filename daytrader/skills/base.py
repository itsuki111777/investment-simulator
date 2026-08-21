"""Trading Skillの共通インターフェースと、AIの必須出力スキーマ。

Trading Skill = 売買アイデアを生成するだけ。ポジションサイズは決めない
(Risk Managerの責務)。銘柄固有の結論("NVDAは買い"等)をハードコードしては
いけない — 判断ルール(セットアップ・確認条件・損切り・利確・回避条件)のみを
表現すること。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TradeDecision(BaseModel):
    ticker: str
    action: Literal["BUY", "SELL", "NO_TRADE"]
    strategy: str = ""
    entry_type: Optional[Literal["MARKET", "LIMIT"]] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    confidence: int = Field(ge=0, le=100, default=50)
    max_hold_minutes: Optional[int] = None
    reasoning: list[str] = Field(default_factory=list)
    invalidators: list[str] = Field(default_factory=list)


@dataclass
class MarketSnapshot:
    """Trading Skillに渡してよい情報はこれだけ。as_of時点より後のデータを
    絶対に含めないこと(エンジン側の責務)。
    """

    as_of: datetime
    ticker: str
    price: float
    candles_1m: list
    candles_5m: list
    vwap: Optional[float]
    ema_9: Optional[float]
    ema_20: Optional[float]
    rsi_14: Optional[float]
    atr_14: Optional[float]
    relative_volume: float
    account_equity: float
    current_position_qty: float
    trades_today: int
    daily_pnl: float
    consecutive_losses: int


class TradingSkill:
    name: str = "base"

    def decide(self, snapshot: MarketSnapshot) -> TradeDecision:
        raise NotImplementedError
