"""Composite stock selector — combines multiple scoring signals.

Scores each stock on multiple dimensions and produces a single tradability
score. Designed for experimentation: weights can be tuned, signals can be
enabled/disabled.

Signals:
  1. Intraday RVOL (volume vs average) — institutional interest
  2. Intraday range expansion (range vs average) — directional energy
  3. Multi-day momentum (5-day return) — trend alignment
  4. Gap magnitude (overnight gap size) — catalyst present
  5. Intraday RS vs SPY — stock-specific strength/weakness
"""

from collections import deque
from datetime import date
from typing import Dict, List, Optional

from .base import Selector, ScoredStock
from ..models import Bar


SKIP = {"VGK", "EFA", "EWG", "FXI", "EWJ", "UVXY", "VXX", "VIXY",
        "XLK", "XLF", "SMH", "SPY", "QQQ", "IWM", "TQQQ"}


class CompositeSelector(Selector):
    """Multi-factor stock scorer and selector."""

    def __init__(
        self,
        symbols: List[str],
        # Weights for each factor
        w_rvol: float = 1.0,
        w_range: float = 1.0,
        w_momentum: float = 1.0,
        w_gap: float = 0.5,
        w_rs: float = 0.5,
        # Lookback for baselines
        lookback: int = 20,
    ) -> None:
        super().__init__(symbols)
        self.w_rvol = w_rvol
        self.w_range = w_range
        self.w_momentum = w_momentum
        self.w_gap = w_gap
        self.w_rs = w_rs
        self.lookback = lookback

        tradable = [s for s in symbols if s not in SKIP]
        self._state: Dict[str, dict] = {s: self._fresh(s) for s in tradable}
        self._spy_return: float = 0.0
        self._spy_open: Optional[float] = None
        self._current_date: Optional[date] = None
        self._scores: Dict[str, ScoredStock] = {}

    def _fresh(self, sym: str) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "prev_close": None,
            "session_volume": 0.0,
            "session_high": None,
            "session_low": None,
            # Baselines
            "daily_volumes": deque(maxlen=self.lookback),
            "daily_ranges": deque(maxlen=self.lookback),
            "daily_closes": deque(maxlen=self.lookback + 1),
        }

    def update(self, bars: Dict[str, Bar], current_date: date) -> None:
        # SPY tracking
        spy_bar = bars.get("SPY")
        if spy_bar:
            if self._current_date != current_date:
                self._spy_open = spy_bar.open
            if self._spy_open and self._spy_open > 0:
                self._spy_return = (spy_bar.close - self._spy_open) / self._spy_open * 100

        if self._current_date != current_date:
            self._current_date = current_date
            # Save yesterday's stats and reset
            for sym, st in self._state.items():
                if st["current_date"] is not None and st["session_volume"] > 0:
                    st["daily_volumes"].append(st["session_volume"])
                    if st["session_high"] and st["session_low"] and st["session_low"] > 0:
                        r = (st["session_high"] - st["session_low"]) / st["session_low"] * 100
                        st["daily_ranges"].append(r)
                if st["prev_close"] is not None:
                    st["daily_closes"].append(st["prev_close"])

                bar = bars.get(sym)
                st["current_date"] = current_date
                st["day_open"] = bar.open if bar else None
                st["session_volume"] = 0.0
                st["session_high"] = None
                st["session_low"] = None

        for sym, st in self._state.items():
            bar = bars.get(sym)
            if bar is None:
                continue
            st["session_volume"] += bar.volume
            if st["session_high"] is None or bar.high > st["session_high"]:
                st["session_high"] = bar.high
            if st["session_low"] is None or bar.low < st["session_low"]:
                st["session_low"] = bar.low
            st["prev_close"] = bar.close

    def select(self, top_n: int = 10) -> List[ScoredStock]:
        """Score all stocks and return top-N."""
        self._scores.clear()

        for sym, st in self._state.items():
            score = 0.0
            tags = {}

            # 1. RVOL
            if st["daily_volumes"] and st["session_volume"] > 0:
                avg_vol = sum(st["daily_volumes"]) / len(st["daily_volumes"])
                if avg_vol > 0:
                    rvol = st["session_volume"] / avg_vol
                    tags["rvol"] = round(rvol, 2)
                    score += min(rvol, 5.0) * self.w_rvol

            # 2. Range expansion
            if (st["daily_ranges"] and st["session_high"] and st["session_low"]
                    and st["session_low"] > 0):
                curr_range = (st["session_high"] - st["session_low"]) / st["session_low"] * 100
                avg_range = sum(st["daily_ranges"]) / len(st["daily_ranges"])
                if avg_range > 0:
                    range_ratio = curr_range / avg_range
                    tags["range_x"] = round(range_ratio, 2)
                    score += min(range_ratio, 3.0) * self.w_range

            # 3. Multi-day momentum
            closes = list(st["daily_closes"])
            if len(closes) >= 6:
                mom_5d = (closes[-1] - closes[-5]) / closes[-5] * 100
                tags["mom_5d"] = round(mom_5d, 2)
                score += min(abs(mom_5d), 10.0) / 2 * self.w_momentum

            # 4. Gap magnitude
            if st["day_open"] and len(closes) > 0 and closes[-1] > 0:
                gap = (st["day_open"] - closes[-1]) / closes[-1] * 100
                tags["gap"] = round(gap, 2)
                score += min(abs(gap), 5.0) * self.w_gap

            # 5. Intraday RS vs SPY
            if st["day_open"] and st["day_open"] > 0 and st["prev_close"]:
                stock_ret = (st["prev_close"] - st["day_open"]) / st["day_open"] * 100
                rs = stock_ret - self._spy_return
                tags["rs"] = round(rs, 2)
                score += min(abs(rs), 5.0) * self.w_rs

            # Direction bias: align with momentum
            mom = tags.get("mom_5d", 0)
            rs_val = tags.get("rs", 0)
            if mom > 0 and rs_val > 0:
                direction = "long"
            elif mom < 0 and rs_val < 0:
                direction = "short"
            else:
                direction = "neutral"

            if score > 0:
                self._scores[sym] = ScoredStock(
                    symbol=sym, score=round(score, 2),
                    direction_bias=direction, tags=tags,
                )

        ranked = sorted(self._scores.values(), key=lambda x: x.score, reverse=True)
        return ranked[:top_n]

    def reset_day(self, current_date: date) -> None:
        pass
