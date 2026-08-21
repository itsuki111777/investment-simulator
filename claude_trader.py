"""自動モード: Claude APIに現在の市況を渡し、売買判断を実行させる。
1回実行して終了する単発スクリプト。何度再実行しても安全 (DBから毎回状態を再計算する)。
定期実行したい場合は /loop や /schedule スキル、または cron などから本スクリプトを呼び出す。
"""

import sys
from typing import Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

import config
import db
import market_data
import portfolio

load_dotenv()

SYSTEM_PROMPT = """あなたは個人の実験用に仮想マネーで運用する投資判断アシスタントです。
現在の現金残高(円)、保有銘柄、ウォッチリストのライブ市況が与えられます。
ウォッチリストの銘柄それぞれについて buy / sell / hold を判断してください。
実際に保有する現金・株数を超える注文は執行時に拒否されるので、与えられた制約内で判断してください。
各判断には簡潔な理由を必ず添えてください。"""


class TradeDecision(BaseModel):
    ticker: str
    action: Literal["buy", "sell", "hold"]
    quantity: int
    reasoning: str


class TradingPlan(BaseModel):
    decisions: list[TradeDecision]
    overall_reasoning: str


def build_prompt(cash: float, holdings: dict, snapshot: list[dict]) -> str:
    lines = [f"現在の現金残高: ¥{cash:,.0f}", ""]

    lines.append("保有銘柄:")
    if holdings:
        for ticker, qty in holdings.items():
            lines.append(f"  - {ticker}: {qty}株")
    else:
        lines.append("  (なし)")

    lines.append("")
    lines.append("ウォッチリスト市況:")
    for item in snapshot:
        if "error" in item:
            lines.append(f"  - {item['ticker']} ({item['name']}): 取得失敗 ({item['error']})")
            continue
        change = item.get("day_change_pct")
        change_str = f"{change:+.2f}%" if change is not None else "N/A"
        lines.append(
            f"  - {item['ticker']} ({item['name']}, {item['market']}): "
            f"{item['price']:.2f} {item['currency']} (前日比 {change_str}), "
            f"円換算 ¥{item['price_jpy_equivalent']:,.2f}"
        )

    return "\n".join(lines)


def main():
    client = anthropic.Anthropic()
    conn = db.get_connection()

    try:
        snapshot = market_data.get_market_snapshot(config.WATCHLIST)
    except market_data.PriceUnavailableError as e:
        print(f"市況データの取得に失敗しました: {e}")
        sys.exit(1)

    cash = portfolio.get_cash_balance_jpy(conn)
    holdings = portfolio.get_holdings(conn)
    user_content = build_prompt(cash, holdings, snapshot)

    try:
        response = client.messages.parse(
            model=config.CLAUDE_MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
            output_format=TradingPlan,
        )
    except anthropic.AuthenticationError:
        print("認証エラー: .env に正しい ANTHROPIC_API_KEY を設定してください。")
        sys.exit(1)
    except anthropic.RateLimitError:
        print("レート制限に達しました。しばらく待ってから再実行してください。")
        sys.exit(1)
    except anthropic.APIConnectionError as e:
        print(f"API接続エラー: {e}")
        sys.exit(1)
    except anthropic.APIStatusError as e:
        print(f"APIエラー (status={e.status_code}): {e.message}")
        sys.exit(1)

    plan = response.parsed_output
    print(f"総合判断: {plan.overall_reasoning}\n")

    for d in plan.decisions:
        result = portfolio.execute_trade(
            conn,
            d.ticker,
            d.action,
            d.quantity,
            decided_by="claude_api",
            reasoning=d.reasoning,
            model_used=config.CLAUDE_MODEL,
        )
        print(f"[{result.status}] {d.ticker} {d.action} {d.quantity}: {result.message}")

    conn.close()


if __name__ == "__main__":
    main()
