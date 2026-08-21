# リアルタイム・デイトレードシミュレーター (LIVE MODE / MVP)

既存の日次シミュレーター(プロジェクトルートの `manual_trade.py` / `claude_trader.py` / `dashboard.py`)とは完全に独立した、未来情報を混入させないリアルタイム・デイトレードエンジンです。DBも別ファイル(`data/daytrader.db`)を使うため、既存システムには一切影響しません。

**実際のお金は一切使用しません。すべて仮想シミュレーションです。**

## セットアップ

```bash
source venv/bin/activate      # プロジェクトルートの既存venvをそのまま使う
pip install -r requirements.txt   # yfinanceが追加されています
python -m daytrader.db        # data/daytrader.db を初期化
```

`.env` の `ANTHROPIC_API_KEY` は既存システムと共用します(Trading SkillがClaude APIを呼ぶため)。

## 起動方法

```bash
python -m daytrader.run_live
```

米国株式市場の取引時間中(9:30-16:00 ET、日本時間だと夜間〜早朝)に、ローカルのターミナルで起動してください。1分足が確定するたびに、Scanner→Trading Skill(Claude)→Risk Manager→Order Engineの順で処理し、約定結果をJournalに記録します。

**クラウドの `/schedule` ルーティンでは動かせません**(最短実行間隔が1時間のため、1分間隔の判断サイクルには使えません)。この点はMVPの既知の制約です。

## 処理の流れ

```
1分足確定
↓
保有ポジションのSL/TPを機械的に監視・決済(Claude呼び出しなし)
↓
Scannerが候補銘柄を絞り込み(価格・出来高・相対出来高)
↓
Trading Skill(Claude)がBUY/SELL/NO_TRADEを判断
↓
Risk Managerが承認/拒否・ポジションサイズ計算(HARD RULESを強制)
↓
Order Engineが約定シミュレーション(スリッページ込み)
↓
Portfolio更新・Journalに不可変記録
```

一度記録した判断(`decisions`テーブル)とクローズ済みトレード(`trades`テーブル)は、後から書き換えません。

## 既知の制約(MVP)

- データソースはyfinance(無料・非公式)。実際のBid/Askは含まれないため、相対出来高から合成したスリッページ/スプレッドで近似しています。分足データにも数分程度の遅延があり得ます。
- 候補銘柄は`config.CANDIDATE_UNIVERSE`の静的リストをScannerで絞り込む方式です(全米株の動的スキャンではありません)。
- Trading Skillは`VWAP_BREAKOUT`アーキタイプ1本のみ(複数Skillの比較はPhase 2)。
- 本格的なパフォーマンス分析(Sharpe Ratio/Expectancy/Rマルチプル分布等)は未実装。現状は`trades`テーブルから基本的なPnLを確認できる程度です。
- ダッシュボードUIは未実装(バックエンドのみ)。

## 設定変更

`daytrader/config.py` を編集してください。初期資金・リスク上限・スキャナー条件・候補銘柄リストなどはすべてここにあります。
