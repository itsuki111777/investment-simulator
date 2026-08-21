import os

INITIAL_CAPITAL_USD = 100_000.0
MARKET = "US_EQUITIES"
TRADING_STYLE = "DAY_TRADING"
DEFAULT_TIMEFRAMES = ["1m", "5m"]

# --- Risk limits (all overridable here; enforced in risk_manager, not by skills) ---
MAX_TRADES_PER_DAY = 5
MAX_RISK_PER_TRADE_PCT = 0.005          # 0.5% of current account equity
MAX_DAILY_LOSS_PCT = 0.02               # 2% of starting-of-day equity
MAX_CONSECUTIVE_LOSSES = 3
ALLOW_OVERNIGHT_POSITIONS = False
MAX_POSITION_VALUE_PCT = 0.25           # safety cap: no single position > 25% of equity

# --- Scanner criteria ---
SCANNER_MIN_PRICE = 5.0
SCANNER_MIN_AVG_VOLUME = 1_000_000
SCANNER_MIN_RELATIVE_VOLUME = 1.5

# Candidate universe: free data sources can't scan the whole US market cheaply,
# so we start from a static liquid-name list and let the scanner filter it.
CANDIDATE_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META", "AMD",
    "NFLX", "AVGO", "JPM", "SPY", "QQQ",
]

# --- Execution / slippage (synthetic, since free intraday data has no real bid/ask) ---
DEFAULT_SLIPPAGE_PCT = 0.0005           # 0.05% baseline for liquid names
LOW_LIQUIDITY_SLIPPAGE_MULTIPLIER = 3.0
LOW_LIQUIDITY_REL_VOLUME_THRESHOLD = 1.0

# --- Decision cadence ---
DECISION_TIMEFRAME = "1m"               # a Trading Skill decision is triggered each time this timeframe's candle confirms

CLAUDE_MODEL = os.environ.get("DAYTRADER_CLAUDE_MODEL", "claude-sonnet-5")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "daytrader.db")
