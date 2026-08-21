"""Stock Scanner: config.CANDIDATE_UNIVERSEを価格・出来高・相対出来高の
条件で絞り込む。AIに全米株から自由に銘柄を選ばせず、Scannerを通過した
銘柄だけをTrading Skillの候補として渡す。
"""

from dataclasses import dataclass

from .. import config
from ..market_data.engine import MarketDataEngine
from ..market_data.provider import PriceUnavailableError

_MINUTES_PER_SESSION = 390  # 米国株の通常取引時間 (9:30-16:00 ET)


@dataclass
class ScanResult:
    ticker: str
    price: float
    avg_daily_volume: float
    relative_volume: float
    passed: bool
    reason: str


def scan(engine: MarketDataEngine, universe: list[str] | None = None) -> list[ScanResult]:
    universe = universe or config.CANDIDATE_UNIVERSE
    results = []

    for ticker in universe:
        try:
            daily = engine.get_candles(ticker, "1d", 20)
            intraday = engine.get_candles(ticker, "1m", _MINUTES_PER_SESSION)
        except PriceUnavailableError as e:
            results.append(ScanResult(ticker, 0.0, 0.0, 0.0, False, f"data unavailable: {e}"))
            continue

        if not daily or not intraday:
            results.append(ScanResult(ticker, 0.0, 0.0, 0.0, False, "no data"))
            continue

        price = intraday[-1].close
        avg_daily_volume = sum(c.volume for c in daily) / len(daily)
        today_volume_so_far = sum(c.volume for c in intraday)
        elapsed_fraction = min(len(intraday) / _MINUTES_PER_SESSION, 1.0)
        expected_volume_so_far = avg_daily_volume * elapsed_fraction
        relative_volume = today_volume_so_far / max(expected_volume_so_far, 1.0)

        reasons = []
        if price < config.SCANNER_MIN_PRICE:
            reasons.append("price too low")
        if avg_daily_volume < config.SCANNER_MIN_AVG_VOLUME:
            reasons.append("avg volume too low")
        if relative_volume < config.SCANNER_MIN_RELATIVE_VOLUME:
            reasons.append("relative volume too low")

        passed = not reasons
        results.append(
            ScanResult(
                ticker=ticker,
                price=price,
                avg_daily_volume=avg_daily_volume,
                relative_volume=relative_volume,
                passed=passed,
                reason="OK" if passed else "; ".join(reasons),
            )
        )

    return results


def get_candidates(engine: MarketDataEngine, universe: list[str] | None = None) -> list[str]:
    return [r.ticker for r in scan(engine, universe) if r.passed]
