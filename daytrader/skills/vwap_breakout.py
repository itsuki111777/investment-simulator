"""MVPのデフォルトTrading Skill。特定の実在トレーダーを再現するものではなく、
一般的な「VWAPブレイクアウト」アーキタイプ(判断ルールのみ)をモデル化する。
"""

import anthropic
from dotenv import load_dotenv

from .. import config
from .base import MarketSnapshot, TradeDecision, TradingSkill

load_dotenv()

SYSTEM_PROMPT = """あなたはデイトレードの仮想売買判断を行うTrading Skillです。
これは実際のお金を一切使わない実験用シミュレーションです。

# 判断フレームワーク: VWAPブレイクアウト・アーキタイプ
- 好む相場: 出来高を伴ってVWAPを明確に上抜け/下抜けする場面
- エントリー条件: 価格がVWAPを回復(ロング)または割り込み(ショート)、かつ相対出来高が平常時より高いことを確認
- 損切り: 直近のスイング安値/高値、またはATRベースの妥当な距離に設定する。ストップの無いエントリーは禁止
- 利益確定: リスクリワード比 概ね1.5〜2倍を目安にtake_profit_1を設定
- 取引を避けるべき条件: 出来高が乏しい、方向感が不明瞭、値動きがVWAP付近でもみ合っている
- 最大保有時間の目安: 30分程度(デイトレードのため長時間保有を避ける)

# 厳守事項
- 与えられたスナップショットの時刻(as_of)より後の情報は一切存在しない。未来は分からない。ローソク足・出来高・指標はすべてas_of時点までのものである前提で判断すること。
- ポジションサイズ・リスク金額はあなたが決める必要はない(Risk Managerが別途計算する)。BUY/SELLの場合はentry_priceとstop_lossを必ず具体的な価格で指定すること。
- 特定の銘柄について「この銘柄は買い」というような銘柄固有の結論を出さず、あくまでこの時点のデータに基づいた判断をすること。
- 条件が揃わなければ無理にエントリーせず、actionをNO_TRADEにすること。NO_TRADEは常に正当な判断である。
- 出力は指定されたスキーマに厳密に従うこと。reasoningには判断根拠を簡潔な箇条書きで、invalidatorsにはこの判断が無効になる条件を記載すること。
"""


def _format_candles(candles) -> str:
    lines = []
    for c in candles:
        lines.append(
            f"  {c.timestamp:%H:%M} O:{c.open:.2f} H:{c.high:.2f} L:{c.low:.2f} C:{c.close:.2f} V:{int(c.volume)}"
        )
    return "\n".join(lines) if lines else "  (データなし)"


class VwapBreakoutSkill(TradingSkill):
    name = "VWAP_BREAKOUT"

    def __init__(self, client: anthropic.Anthropic | None = None):
        self.client = client or anthropic.Anthropic()

    def decide(self, snapshot: MarketSnapshot) -> TradeDecision:
        user_content = self._build_prompt(snapshot)
        response = self.client.messages.parse(
            model=config.CLAUDE_MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
            output_format=TradeDecision,
        )
        decision = response.parsed_output
        decision.strategy = self.name
        return decision

    def _build_prompt(self, snapshot: MarketSnapshot) -> str:
        lines = [
            f"銘柄: {snapshot.ticker}",
            f"判断時刻(as_of, UTC): {snapshot.as_of.isoformat()}",
            f"現在値: {snapshot.price:.2f}",
            f"VWAP: {snapshot.vwap}",
            f"EMA9: {snapshot.ema_9} / EMA20: {snapshot.ema_20}",
            f"RSI14: {snapshot.rsi_14}",
            f"ATR14: {snapshot.atr_14}",
            f"相対出来高: {snapshot.relative_volume:.2f}",
            "",
            "直近1分足(古い順、最新10本):",
            _format_candles(snapshot.candles_1m[-10:]),
            "",
            "直近5分足(古い順、最新10本):",
            _format_candles(snapshot.candles_5m[-10:]),
            "",
            f"口座残高: ${snapshot.account_equity:,.2f}",
            f"この銘柄の現在のポジション数量: {snapshot.current_position_qty}",
            f"本日の取引回数: {snapshot.trades_today}",
            f"本日の実現損益: ${snapshot.daily_pnl:,.2f}",
            f"直近の連敗数: {snapshot.consecutive_losses}",
        ]
        return "\n".join(lines)
