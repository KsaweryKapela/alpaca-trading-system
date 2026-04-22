"""Abnormality Scanner — selects stocks acting unusually for THEMSELVES.

CREATIVE APPROACH: Instead of asking "which stock moved most?", ask
"which stock is behaving most differently from its own normal?"

A 2% move on TSLA is normal (avg daily range 4%). But a 2% move on WMT
is a 3-sigma event. The WMT move is more likely catalyst-driven and
more predictable.

ABNORMALITY = today's value / stock's own historical average

Dimensions measured:
  1. Volume abnormality: today's volume / own 20-day avg volume
  2. Range abnormality: today's range / own 20-day avg range
  3. Gap abnormality: today's gap / own avg gap magnitude
  4. Return abnormality: today's return / own avg daily return magnitude

A stock scoring high on multiple dimensions is having an UNUSUAL day,
which usually means a catalyst → more directional → better to trade.
"""

from collections import deque
from datetime import date
from typing import Dict, List, Optional
import math

from .base import Selector, ScoredStock
from ..models import Bar


SKIP = {"VGK", "EFA", "EWG", "FXI", "EWJ", "UVXY", "VXX", "VIXY",
        "XLK", "XLF", "SMH", "SPY", "QQQ", "IWM", "TQQQ"}


class AbnormalitySelector(Selector):
    """Select stocks by how unusual their current behavior is."""

    def __init__(
        self,
        symbols: List[str],
        lookback: int = 20,
        min_abnormality: float = 1.5,  # minimum abnormality score to qualify
    ) -> None:
        super().__init__(symbols)
        self.lookback = lookback
        self.min_abnormality = min_abnormality

        tradable = [s for s in symbols if s not in SKIP]
        self._state: Dict[str, dict] = {s: self._fresh() for s in tradable}
        self._spy_return: float = 0.0
        self._spy_open: Optional[float] = None
        self._current_date: Optional[date] = None

    def _fresh(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "prev_close": None,
            "session_volume": 0.0,
            "session_high": None,
            "session_low": None,
            # History for baseline
            "daily_volumes": deque(maxlen=self.lookback),
            "daily_ranges": deque(maxlen=self.lookback),
            "daily_abs_returns": deque(maxlen=self.lookback),
            "daily_abs_gaps": deque(maxlen=self.lookback),
            "daily_closes": deque(maxlen=self.lookback + 1),
        }

    def update(self, bars: Dict[str, Bar], current_date: date) -> None:
        spy_bar = bars.get("SPY")
        if spy_bar:
            if self._current_date != current_date:
                self._spy_open = spy_bar.open
            if self._spy_open and self._spy_open > 0:
                self._spy_return = (spy_bar.close - self._spy_open) / self._spy_open * 100

        if self._current_date != current_date:
            self._current_date = current_date
            for sym, st in self._state.items():
                if st["current_date"] is not None and st["prev_close"] is not None:
                    # Save daily stats
                    if st["session_volume"] > 0:
                        st["daily_volumes"].append(st["session_volume"])
                    if st["session_high"] and st["session_low"] and st["session_low"] > 0:
                        st["daily_ranges"].append(
                            (st["session_high"] - st["session_low"]) / st["session_low"] * 100)
                    if st["day_open"] and st["day_open"] > 0:
                        st["daily_abs_returns"].append(
                            abs((st["prev_close"] - st["day_open"]) / st["day_open"] * 100))
                    st["daily_closes"].append(st["prev_close"])
                    # Gap
                    bar = bars.get(sym)
                    if bar and len(st["daily_closes"]) > 0:
                        prev_c = st["daily_closes"][-1]
                        if prev_c > 0:
                            st["daily_abs_gaps"].append(abs((bar.open - prev_c) / prev_c * 100))

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
        scored: List[ScoredStock] = []

        for sym, st in self._state.items():
            if st["day_open"] is None or st["prev_close"] is None:
                continue
            if st["day_open"] <= 0:
                continue

            abnormality = 0.0
            tags = {}
            dimensions = 0

            # 1. Volume abnormality
            if st["daily_volumes"] and st["session_volume"] > 0:
                avg = sum(st["daily_volumes"]) / len(st["daily_volumes"])
                if avg > 0:
                    vol_abn = st["session_volume"] / avg
                    tags["vol_x"] = round(vol_abn, 2)
                    abnormality += min(vol_abn, 5.0)
                    dimensions += 1

            # 2. Range abnormality
            if (st["daily_ranges"] and st["session_high"] and st["session_low"]
                    and st["session_low"] > 0):
                curr = (st["session_high"] - st["session_low"]) / st["session_low"] * 100
                avg = sum(st["daily_ranges"]) / len(st["daily_ranges"])
                if avg > 0:
                    range_abn = curr / avg
                    tags["range_x"] = round(range_abn, 2)
                    abnormality += min(range_abn, 5.0)
                    dimensions += 1

            # 3. Return abnormality
            if st["daily_abs_returns"] and st["day_open"] > 0:
                curr = abs((st["prev_close"] - st["day_open"]) / st["day_open"] * 100)
                avg = sum(st["daily_abs_returns"]) / len(st["daily_abs_returns"])
                if avg > 0:
                    ret_abn = curr / avg
                    tags["ret_x"] = round(ret_abn, 2)
                    abnormality += min(ret_abn, 5.0)
                    dimensions += 1

            # 4. Gap abnormality
            if st["daily_abs_gaps"] and len(st["daily_closes"]) > 0:
                prev_c = st["daily_closes"][-1]
                if prev_c > 0 and st["day_open"]:
                    curr_gap = abs((st["day_open"] - prev_c) / prev_c * 100)
                    avg_gap = sum(st["daily_abs_gaps"]) / len(st["daily_abs_gaps"])
                    if avg_gap > 0:
                        gap_abn = curr_gap / avg_gap
                        tags["gap_x"] = round(gap_abn, 2)
                        abnormality += min(gap_abn, 5.0)
                        dimensions += 1

            # Normalize by dimensions
            if dimensions > 0:
                abnormality /= dimensions

            if abnormality >= self.min_abnormality:
                # Direction from intraday return
                ret = (st["prev_close"] - st["day_open"]) / st["day_open"] * 100
                rs = ret - self._spy_return
                direction = "long" if rs > 0 else "short"
                tags["rs"] = round(rs, 2)

                scored.append(ScoredStock(
                    symbol=sym, score=round(abnormality, 2),
                    direction_bias=direction, tags=tags,
                ))

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_n]
