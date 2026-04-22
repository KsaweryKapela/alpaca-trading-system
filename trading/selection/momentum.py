"""Momentum-based stock selector.

Ranks stocks by multi-day price momentum. Stocks with strongest recent
trends get the highest scores.

This is the simplest and most robust selection method:
  - 5-day return momentum (primary signal)
  - 20-day return momentum (trend confirmation)
  - Stocks trending UP get long bias; trending DOWN get short bias
"""

from collections import deque
from datetime import date
from typing import Dict, List

from .base import Selector, ScoredStock
from ..models import Bar


class MomentumSelector(Selector):
    """Select stocks by multi-day price momentum."""

    def __init__(
        self,
        symbols: List[str],
        fast_period: int = 5,
        slow_period: int = 20,
        fast_weight: float = 0.6,
        slow_weight: float = 0.4,
    ) -> None:
        super().__init__(symbols)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.fast_weight = fast_weight
        self.slow_weight = slow_weight
        self._closes: Dict[str, deque] = {
            s: deque(maxlen=slow_period + 2) for s in symbols
        }
        self._current_date: date = None
        self._day_close: Dict[str, float] = {}
        self._scores: Dict[str, ScoredStock] = {}

    def update(self, bars: Dict[str, Bar], current_date: date) -> None:
        # On new day, save previous day's close and recompute scores
        if self._current_date != current_date:
            for sym, px in self._day_close.items():
                if sym in self._closes:
                    self._closes[sym].append(px)
            self._current_date = current_date
            self._recompute_scores()

        # Track latest prices
        for sym, bar in bars.items():
            if sym in self._closes:
                self._day_close[sym] = bar.close

    def _recompute_scores(self) -> None:
        self._scores.clear()
        for sym in self.symbols:
            closes = list(self._closes.get(sym, []))
            if len(closes) < self.fast_period + 1:
                continue

            # Fast momentum (5-day return)
            fast_ret = (closes[-1] - closes[-self.fast_period]) / closes[-self.fast_period] * 100

            # Slow momentum (20-day return, if enough data)
            if len(closes) >= self.slow_period + 1:
                slow_ret = (closes[-1] - closes[-self.slow_period]) / closes[-self.slow_period] * 100
            else:
                slow_ret = fast_ret

            # Composite score
            score = abs(fast_ret) * self.fast_weight + abs(slow_ret) * self.slow_weight
            direction = "long" if fast_ret > 0 else "short"

            self._scores[sym] = ScoredStock(
                symbol=sym,
                score=score,
                direction_bias=direction,
                tags={"fast_ret": round(fast_ret, 2), "slow_ret": round(slow_ret, 2)},
            )

    def select(self, top_n: int = 10) -> List[ScoredStock]:
        ranked = sorted(self._scores.values(), key=lambda x: x.score, reverse=True)
        return ranked[:top_n]

    def reset_day(self, current_date: date) -> None:
        pass
