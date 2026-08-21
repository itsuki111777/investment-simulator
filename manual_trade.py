"""手動モード: Claude Codeがセッション内でこのCLIを呼び出して売買を記録する。
追加のAPI課金は発生しない。

使い方:
  python manual_trade.py snapshot
  python manual_trade.py status
  python manual_trade.py buy AAPL 10 --reason "..."
  python manual_trade.py sell 7203.T 5 --reason "..."
  python manual_trade.py hold NVDA --reason "..."
"""

import argparse
import sys

import db
import market_data
import portfolio


def cmd_snapshot(args):
    snapshot = market_data.get_market_snapshot()
    print(f"{'Ticker':<10} {'Name':<18} {'Market':<6} {'Price':>12} {'Chg%':>8} {'JPY換算':>14}")
    for item in snapshot:
        if "error" in item:
            print(f"{item['ticker']:<10} {item['name']:<18} {item.get('market',''):<6} 取得失敗: {item['error']}")
            continue
        change = item.get("day_change_pct")
        change_str = f"{change:+.2f}" if change is not None else "N/A"
        print(
            f"{item['ticker']:<10} {item['name']:<18} {item['market']:<6} "
            f"{item['price']:>12,.2f} {change_str:>8} ¥{item['price_jpy_equivalent']:>12,.2f}"
        )


def cmd_status(args):
    conn = db.get_connection()
    cash = portfolio.get_cash_balance_jpy(conn)
    holdings = portfolio.get_holdings_with_cost(conn)
    cash2, holdings_value, total = portfolio.get_portfolio_value_jpy(conn)

    print(f"現金残高:     ¥{cash:,.0f}")
    print(f"保有評価額:   ¥{holdings_value:,.0f}")
    print(f"総資産:       ¥{total:,.0f}")
    print()
    if holdings:
        print(f"{'Ticker':<10} {'数量':>10} {'平均取得単価':>16}")
        for ticker, h in holdings.items():
            print(f"{ticker:<10} {h['quantity']:>10.2f} ¥{h['avg_cost_jpy']:>14,.2f}")
    else:
        print("保有銘柄なし")
    conn.close()


def _do_trade(args, action):
    conn = db.get_connection()
    result = portfolio.execute_trade(
        conn,
        args.ticker.upper(),
        action,
        getattr(args, "quantity", 0),
        decided_by="claude_code_manual",
        reasoning=args.reason,
    )
    print(f"[{result.status}] {result.message}")
    conn.close()
    if result.status == "rejected":
        sys.exit(1)


def cmd_buy(args):
    _do_trade(args, "buy")


def cmd_sell(args):
    _do_trade(args, "sell")


def cmd_hold(args):
    args.quantity = 0
    _do_trade(args, "hold")


def main():
    parser = argparse.ArgumentParser(description="仮想マネー投資シミュレーター - 手動取引CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("snapshot", help="ウォッチリストの現在価格を表示").set_defaults(func=cmd_snapshot)
    sub.add_parser("status", help="現金・保有銘柄・総資産を表示").set_defaults(func=cmd_status)

    p_buy = sub.add_parser("buy", help="買い注文を記録")
    p_buy.add_argument("ticker")
    p_buy.add_argument("quantity", type=float)
    p_buy.add_argument("--reason", required=True)
    p_buy.set_defaults(func=cmd_buy)

    p_sell = sub.add_parser("sell", help="売り注文を記録")
    p_sell.add_argument("ticker")
    p_sell.add_argument("quantity", type=float)
    p_sell.add_argument("--reason", required=True)
    p_sell.set_defaults(func=cmd_sell)

    p_hold = sub.add_parser("hold", help="見送り判断を記録")
    p_hold.add_argument("ticker")
    p_hold.add_argument("--reason", required=True)
    p_hold.set_defaults(func=cmd_hold)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
