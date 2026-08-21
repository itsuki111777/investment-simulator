"""MarketDataProviderの抽象インターフェース。特定のベンダーにシステム全体を
依存させないため、実際のデータ取得はこのインターフェースの背後に隠す。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


class PriceUnavailableError(Exception):
    pass


@dataclass
class Candle:
    timestamp: datetime  # ローソク足の開始時刻(UTC)
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Quote:
    ticker: str
    price: float
    timestamp: datetime


class MarketDataProvider(ABC):
    @abstractmethod
    def get_current_quote(self, ticker: str) -> Quote:
        ...

    @abstractmethod
    def get_candles(self, ticker: str, timeframe: str, limit: int) -> list[Candle]:
        """指定時間足の直近`limit`本を古い順で返す。timeframeは "1m" / "5m" / "1d"。"""
        ...


_YF_INTERVAL = {"1m": "1m", "5m": "5m", "1d": "1d"}
_YF_PERIOD = {"1m": "1d", "5m": "5d", "1d": "1mo"}


class YFinanceProvider(MarketDataProvider):
    """yfinance(Yahoo Finance非公式ラッパー)による実装。無料だが、分足データは
    通常やや遅延(数分程度)がある点に留意。5分足はエンジン側で1分足から合成する
    運用を基本とするため、ここでは "5m" のネイティブ取得はフォールバック用途。
    """

    def get_current_quote(self, ticker: str) -> Quote:
        candles = self.get_candles(ticker, "1m", 1)
        if not candles:
            raise PriceUnavailableError(f"No recent 1m data for {ticker}")
        last = candles[-1]
        return Quote(ticker=ticker, price=last.close, timestamp=last.timestamp)

    def get_candles(self, ticker: str, timeframe: str, limit: int) -> list[Candle]:
        if timeframe not in _YF_INTERVAL:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        import yfinance as yf

        try:
            hist = yf.Ticker(ticker).history(
                period=_YF_PERIOD[timeframe],
                interval=_YF_INTERVAL[timeframe],
            )
        except Exception as e:
            raise PriceUnavailableError(f"yfinance fetch failed for {ticker} ({timeframe}): {e}")

        if hist.empty:
            raise PriceUnavailableError(f"No candle data for {ticker} ({timeframe})")

        hist = hist.tail(limit)
        candles = []
        for ts, row in hist.iterrows():
            candles.append(
                Candle(
                    timestamp=ts.to_pydatetime(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                )
            )
        return candles
