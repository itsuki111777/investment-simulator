"""ローソク足の集計ロジック(例: 1分足×5本 → 5分足)。"""

from .provider import Candle


def aggregate_candles(candles_1m: list[Candle], group_size: int) -> list[Candle]:
    """連続するcandles_1m(古い順)を`group_size`本ずつまとめて上位足を合成する。

    Open  = グループ内で最初の1分足のOpen
    High  = グループ内のHighの最大値
    Low   = グループ内のLowの最小値
    Close = グループ内で最後の1分足のClose
    Volume = グループ内のVolume合計
    """
    aggregated = []
    n = len(candles_1m)
    for i in range(0, n - n % group_size, group_size):
        group = candles_1m[i:i + group_size]
        if len(group) < group_size:
            continue
        aggregated.append(
            Candle(
                timestamp=group[0].timestamp,
                open=group[0].open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=group[-1].close,
                volume=sum(c.volume for c in group),
            )
        )
    return aggregated
