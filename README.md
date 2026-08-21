# 仮想マネー投資シミュレーター

Claude Codeの投資判断力を実験するための個人用シミュレーターです。**実際のリアルマネーは一切使用しません。** 株価は [tradingview-ta](https://github.com/brian-the-dev/python-tradingview-ta)(TradingViewの非公式データ取得ライブラリ)経由で実際の市場データ(米国株・日本株)を取得し、仮想の現金残高のみを操作します。TradingView側の公式データAPIではなく非公式ライブラリである点にご留意ください。

## セットアップ

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # ANTHROPIC_API_KEY を記入(自動モードを使う場合のみ必須)
python db.py           # DB初期化 (data/simulator.db を作成)
```

## モードA: 自動売買(Claude API)

```bash
python claude_trader.py
```

現在の現金・保有銘柄・ウォッチリストの市況をClaude APIに渡し、構造化出力で売買判断を取得して実行します。1回実行すると終了する単発スクリプトで、何度再実行しても安全です(DBから毎回状態を再計算するため)。定期的に自動実行したい場合は、Claude Codeの `/loop` や `/schedule` スキル、または通常のcronから本スクリプトを呼び出してください。

デフォルトモデルは `claude-sonnet-5` です。より深い推論をさせたい場合は `.env` に以下を追加してください:

```
CLAUDE_TRADER_MODEL=claude-opus-5
```

## モードB: 手動売買(Claude Codeセッション内)

Claude Codeとの会話の中で、以下のコマンドを使って市況を確認し、その場で売買判断を記録します。追加のAPI課金は発生しません。

```bash
python manual_trade.py snapshot                              # 市況確認
python manual_trade.py status                                # 現在の資産状況
python manual_trade.py buy AAPL 10 --reason "強い決算内容のため"
python manual_trade.py sell 7203.T 5 --reason "急騰後の利確"
python manual_trade.py hold NVDA --reason "様子見"
```

## ダッシュボード

```bash
streamlit run dashboard.py
```

`http://localhost:8501` で、資産サマリー・資産推移チャート・保有銘柄・売買履歴(自動/手動・実行/拒否/見送りでフィルタ可能)・ウォッチリストを確認できます。

## 設定変更

`config.py` を編集してください:

- `INITIAL_CAPITAL_JPY` — 初期資金(デフォルト ¥1,000,000)
- `WATCHLIST` — 対象銘柄リスト

## クラウド定期実行 (/schedule)

課金なしで「自動売買」を実現するため、Claude Codeの `/schedule` でクラウドエージェントを定期実行する構成にしています(現在は**1時間おき**、`config.py` の `ROUTINE_INTERVAL_HOURS` / `ROUTINE_CRON_MINUTE` と一致させること)。クラウド実行は毎回まっさらな環境のため、`data/simulator.db` は(通常のローカル運用と異なり)**gitで追跡・コミット**して状態を引き継いでいます。`.env`(APIキー)は引き続きgitignore対象です。ローカルでも直接コマンドを実行できますが、その場合は毎回 `git pull` / `git push` を意識してください(cronの実行と競合しないよう注意)。

## Webダッシュボード (Streamlit Community Cloud)

このリポジトリをそのまま [Streamlit Community Cloud](https://share.streamlit.io) に接続し、Main file pathを `dashboard.py` に設定するとブラウザから閲覧できるURLが発行されます。クラウドルーティンが `data/simulator.db` をpushするたびに自動で再デプロイされます。

## 設計メモ

- 基軸通貨はJPYに統一。米国株の売買は実行時のUSD/JPYレートで円換算します。為替変動もそのまま損益に反映されます。
- 保有株数は `trades` テーブルからの導出値です(別テーブルでの二重管理はしていません)。
- `portfolio.execute_trade()` が両モード共通の検証付き実行関数です。現金不足・保有数不足の注文は `rejected` として理由付きでDBに記録され、ダッシュボードから確認できます。

## スキーマ概要

- `trades` — 全取引履歴(買い/売り/見送り/拒否、判断主体、理由、使用モデル)
- `portfolio_snapshots` — 資産推移の記録(取引実行時に自動記録、手動記録も可能)
