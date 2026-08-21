import os

INITIAL_CAPITAL_JPY = 1_000_000
BASE_CURRENCY = "JPY"
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "simulator.db")
CLAUDE_MODEL = os.environ.get("CLAUDE_TRADER_MODEL", "claude-sonnet-5")

WATCHLIST = [
    {"ticker": "AAPL", "name": "Apple", "market": "US", "tv_symbol": "AAPL", "tv_exchange": "NASDAQ", "tv_screener": "america"},
    {"ticker": "MSFT", "name": "Microsoft", "market": "US", "tv_symbol": "MSFT", "tv_exchange": "NASDAQ", "tv_screener": "america"},
    {"ticker": "NVDA", "name": "NVIDIA", "market": "US", "tv_symbol": "NVDA", "tv_exchange": "NASDAQ", "tv_screener": "america"},
    {"ticker": "GOOGL", "name": "Alphabet", "market": "US", "tv_symbol": "GOOGL", "tv_exchange": "NASDAQ", "tv_screener": "america"},
    {"ticker": "AMZN", "name": "Amazon", "market": "US", "tv_symbol": "AMZN", "tv_exchange": "NASDAQ", "tv_screener": "america"},
    {"ticker": "TSLA", "name": "Tesla", "market": "US", "tv_symbol": "TSLA", "tv_exchange": "NASDAQ", "tv_screener": "america"},
    {"ticker": "7203.T", "name": "Toyota", "market": "JP", "tv_symbol": "7203", "tv_exchange": "TSE", "tv_screener": "japan"},
    {"ticker": "6758.T", "name": "Sony", "market": "JP", "tv_symbol": "6758", "tv_exchange": "TSE", "tv_screener": "japan"},
    {"ticker": "9984.T", "name": "SoftBank Group", "market": "JP", "tv_symbol": "9984", "tv_exchange": "TSE", "tv_screener": "japan"},
    {"ticker": "8306.T", "name": "Mitsubishi UFJ", "market": "JP", "tv_symbol": "8306", "tv_exchange": "TSE", "tv_screener": "japan"},
    {"ticker": "6501.T", "name": "Hitachi", "market": "JP", "tv_symbol": "6501", "tv_exchange": "TSE", "tv_screener": "japan"},
    {"ticker": "9432.T", "name": "NTT", "market": "JP", "tv_symbol": "9432", "tv_exchange": "TSE", "tv_screener": "japan"},
    {"ticker": "7974.T", "name": "Nintendo", "market": "JP", "tv_symbol": "7974", "tv_exchange": "TSE", "tv_screener": "japan"},
]

FX_USDJPY = {"tv_symbol": "USDJPY", "tv_exchange": "FX_IDC", "tv_screener": "forex"}

# クラウドの自動売買ルーティン(/schedule)の実行間隔。ダッシュボードの「次回実行まで」
# 表示に使う。ルーティン側のcron設定を変更したらここも合わせて変更すること。
ROUTINE_INTERVAL_HOURS = 1
ROUTINE_CRON_MINUTE = 0
