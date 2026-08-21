from datetime import datetime, timezone

import yfinance as yf

import config


class PriceUnavailableError(Exception):
    pass


def determine_currency(ticker: str) -> str:
    return "JPY" if ticker.endswith(".T") else "USD"


def _last_price_from_history(t: yf.Ticker) -> float | None:
    hist = t.history(period="5d")
    if hist.empty:
        return None
    return float(hist["Close"].iloc[-1])


def get_quote(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    price = None
    prev_close = None

    try:
        fast_info = t.fast_info
        price = fast_info.get("lastPrice")
        prev_close = fast_info.get("previousClose")
    except Exception:
        price = None

    if price is None:
        price = _last_price_from_history(t)

    if price is None:
        raise PriceUnavailableError(f"Could not fetch a price for {ticker}")

    day_change_pct = None
    if prev_close:
        try:
            day_change_pct = (price - prev_close) / prev_close * 100
        except ZeroDivisionError:
            day_change_pct = None

    return {
        "ticker": ticker,
        "price": float(price),
        "currency": determine_currency(ticker),
        "day_change_pct": day_change_pct,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_fx_rate_usdjpy() -> float:
    t = yf.Ticker("JPY=X")
    try:
        rate = t.fast_info.get("lastPrice")
    except Exception:
        rate = None
    if rate is None:
        rate = _last_price_from_history(t)
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
