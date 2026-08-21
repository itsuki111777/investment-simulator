import os

INITIAL_CAPITAL_JPY = 1_000_000
BASE_CURRENCY = "JPY"
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "simulator.db")
CLAUDE_MODEL = os.environ.get("CLAUDE_TRADER_MODEL", "claude-sonnet-5")

WATCHLIST = [
    {"ticker": "AAPL", "name": "Apple", "market": "US"},
    {"ticker": "MSFT", "name": "Microsoft", "market": "US"},
    {"ticker": "NVDA", "name": "NVIDIA", "market": "US"},
    {"ticker": "GOOGL", "name": "Alphabet", "market": "US"},
    {"ticker": "AMZN", "name": "Amazon", "market": "US"},
    {"ticker": "TSLA", "name": "Tesla", "market": "US"},
    {"ticker": "7203.T", "name": "Toyota", "market": "JP"},
    {"ticker": "6758.T", "name": "Sony", "market": "JP"},
    {"ticker": "9984.T", "name": "SoftBank Group", "market": "JP"},
    {"ticker": "8306.T", "name": "Mitsubishi UFJ", "market": "JP"},
    {"ticker": "6501.T", "name": "Hitachi", "market": "JP"},
    {"ticker": "9432.T", "name": "NTT", "market": "JP"},
    {"ticker": "7974.T", "name": "Nintendo", "market": "JP"},
]
