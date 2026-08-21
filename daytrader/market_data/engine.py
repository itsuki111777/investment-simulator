"""MarketDataEngine: providerをラップし、銘柄×時間足単位で結果を共有キャッシュする。
同じティックの中でScanner・複数Skill・Risk Managerが同じ銘柄の同じ時間足を
それぞれ個別にAPIへ取りに行くことを防ぐ(APIリクエスト数の節約)。
"""

import time

from . import candles as candle_utils
from .provider import Candle, MarketDataProvider, Quote


class MarketDataEngine:
    def __init__(self, provider: MarketDataProvider, cache_ttl_seconds: float = 20.0):
        self.provider = provider
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[tuple, tuple[float, list[Candle]]] = {}

    def get_candles(self, ticker: str, timeframe: str, limit: int) -> list[Candle]:
        key = (ticker, timeframe, limit)
        now = time.time()
        cached = self._cache.get(key)
        if cached and now - cached[0] < self.cache_ttl_seconds:
            return cached[1]

        if timeframe == "5m":
            # 5分足はプロバイダに直接聞かず、1分足から合成する(単一の情報源に統一)
            one_min = self.get_candles(ticker, "1m", limit * 5)
            result = candle_utils.aggregate_candles(one_min, group_size=5)[-limit:]
        else:
            result = self.provider.get_candles(ticker, timeframe, limit)

        self._cache[key] = (now, result)
        return result

    def get_current_quote(self, ticker: str) -> Quote:
        return self.provider.get_current_quote(ticker)

    def clear_cache(self) -> None:
        self._cache.clear()
