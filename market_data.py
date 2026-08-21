import time
from datetime import datetime, timezone

from tradingview_ta import Interval, TA_Handler

import config

_RETRIES = 3
_RETRY_DELAY_SECONDS = 0.8


class PriceUnavailableError(Exception):
    pass


def determine_currency(ticker: str) -> str:
    return "JPY" if ticker.endswith(".T") else "USD"


def _find_watchlist_entry(ticker: str) -> dict:
    entry = next((e for e in config.WATCHLIST if e["ticker"] == ticker), None)
    if entry is None:
        raise PriceUnavailableError(f"{ticker} is not in the configured watchlist")
    return entry


def _fetch_indicators(symbol: str, exchange: str, screener: str) -> dict:
    last_error = None
    for attempt in range(_RETRIES):
        try:
            handler = TA_Handler(
                symbol=symbol,
                exchange=exchange,
                screener=screener,
                interval=Interval.INTERVAL_1_DAY,
            )
            return handler.get_analysis().indicators
        except Exception as e:
            last_error = e
            if attempt < _RETRIES - 1:
                time.sleep(_RETRY_DELAY_SECONDS)
    raise PriceUnavailableError(f"TradingView fetch failed for {symbol} ({exchange}): {last_error}")


def get_quote(ticker: str) -> dict:
    entry = _find_watchlist_entry(ticker)
    indicators = _fetch_indicators(entry["tv_symbol"], entry["tv_exchange"], entry["tv_screener"])

    price = indicators.get("close")
    if price is None:
        raise PriceUnavailableError(f"Could not fetch a price for {ticker}")

    day_change_pct = indicators.get("change")

    return {
        "ticker": ticker,
        "price": float(price),
        "currency": determine_currency(ticker),
        "day_change_pct": day_change_pct,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_fx_rate_usdjpy() -> float:
    fx = config.FX_USDJPY
    indicators = _fetch_indicators(fx["tv_symbol"], fx["tv_exchange"], fx["tv_screener"])
    rate = indicators.get("close")
    if rate is None:
        raise PriceUnavailableError("Could not fetch USD/JPY FX rate")
    return float(rate)


def get_market_snapshot(watchlist=None) -> list[dict]:
    if watchlist is None:
        watchlist = config.WATCHLIST

    fx_rate = None
    snapshot = []
    for entry in watchlist:
        ticker = entry["ticker"]
        try:
            quote = get_quote(ticker)
        except PriceUnavailableError as e:
            snapshot.append(
                {
                    "ticker": ticker,
                    "name": entry.get("name", ticker),
                    "market": entry.get("market"),
                    "error": str(e),
                }
            )
            continue

        if quote["currency"] == "USD" and fx_rate is None:
            fx_rate = get_fx_rate_usdjpy()

        quote["name"] = entry.get("name", ticker)
        quote["market"] = entry.get("market")
        quote["fx_rate_usdjpy"] = fx_rate if quote["currency"] == "USD" else None
        quote["price_jpy_equivalent"] = (
            quote["price"] * fx_rate if quote["currency"] == "USD" else quote["price"]
        )
        snapshot.append(quote)

    return snapshot
