"""流動性に応じたスリッページ/スプレッドの簡易推定。

無料の分足データには実際の板・Bid/Askが含まれないため、相対出来高から
スリッページ・スプレッドを合成する近似モデル。scanner/order_engine双方で
同じ関数を参照することで基準がずれないようにする。
"""

from .. import config


def estimate_slippage_pct(relative_volume: float) -> float:
    if relative_volume < config.LOW_LIQUIDITY_REL_VOLUME_THRESHOLD:
        return config.DEFAULT_SLIPPAGE_PCT * config.LOW_LIQUIDITY_SLIPPAGE_MULTIPLIER
    return config.DEFAULT_SLIPPAGE_PCT
