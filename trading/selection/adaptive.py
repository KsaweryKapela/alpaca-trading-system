"""Adaptive Feature-Weighted Stock Selector.

GENUINELY CREATIVE: Instead of hand-crafting selection rules, this selector
LEARNS which features predict overnight returns by tracking feature-return
correlations over a rolling window.

HOW IT WORKS:
  1. For each stock, compute N features daily (momentum, RVOL, gap, etc.)
  2. Track each stock's ACTUAL overnight return (close → next open)
  3. Correlate each feature with next-day overnight returns over 40-day window
  4. Weight features by their predictive correlation
  5. Score stocks using learned weights → select top-N

The weights adapt over time — if momentum stops predicting overnight returns,
its weight drops. If RVOL becomes predictive, its weight rises.

FEATURES TRACKED:
  1. intraday_return: stock's return from open today
  2. rs_vs_spy: relative strength vs SPY
  3. rvol: relative volume (vs 20-day avg)
  4. gap_pct: overnight gap (prev close → open)
  5. range_pct: intraday range relative to average
  6. distance_from_high: how far below 20-day high
  7. avg_overnight_gap: stock's historical avg overnight return
  8. momentum_5d: 5-day price momentum

This is NOT ML — it's a rolling correlation model. Simple, interpretable,
and adapts to changing market conditions.
"""

from collections import deque
from datetime import date
from typing import Dict, List, Optional, Tuple
import math

from .base import Selector, ScoredStock
from ..models import Bar


SKIP = {"VGK", "EFA", "EWG", "FXI", "EWJ", "UVXY", "VXX", "VIXY",
        "XLK", "XLF", "SMH", "SPY", "QQQ", "IWM", "TQQQ"}

FEATURE_NAMES = [
    "intraday_return", "rs_vs_spy", "rvol", "gap_pct",
    "range_pct", "dist_from_high", "avg_on_gap", "momentum_5d",
]


class AdaptiveSelector(Selector):
    """Self-learning stock selector using feature-return correlations."""

    def __init__(
        self,
        symbols: List[str],
        lookback: int = 40,         # days for correlation estimation
        vol_lookback: int = 20,     # days for volume/range baselines
        min_data_days: int = 15,    # minimum days before scoring starts
    ) -> None:
        super().__init__(symbols)
        self.lookback = lookback
        self.vol_lookback = vol_lookback
        self.min_data_days = min_data_days

        tradable = [s for s in symbols if s not in SKIP]
        self._state: Dict[str, dict] = {s: self._fresh() for s in tradable}
        self._spy_return: float = 0.0
        self._spy_open: Optional[float] = None
        self._current_date: Optional[date] = None

        # Feature-return correlation tracking (pooled across all stocks)
        self._feature_history: deque = deque(maxlen=lookback)
        # Each entry: list of (features_dict, actual_overnight_return) tuples

        # Learned feature weights
        self._weights: Dict[str, float] = {f: 1.0 for f in FEATURE_NAMES}

    def _fresh(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "prev_close": None,
            "session_volume": 0.0,
            "session_high": None,
            "session_low": None,
            "daily_volumes": deque(maxlen=self.vol_lookback),
            "daily_ranges": deque(maxlen=self.vol_lookback),
            "daily_closes": deque(maxlen=21),
            "daily_highs_20": deque(maxlen=20),
            "overnight_returns": deque(maxlen=self.vol_lookback),
            # Today's features (computed at 15:30)
            "today_features": None,
            # Yesterday's features (for correlation with today's overnight)
            "yesterday_features": None,
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
            # New day: save stats, compute overnight returns, update weights
            day_data: List[Tuple[Dict[str, float], float]] = []

            for sym, st in self._state.items():
                if st["current_date"] is not None:
                    # Save daily stats
                    if st["session_volume"] > 0:
                        st["daily_volumes"].append(st["session_volume"])
                    if st["session_high"] and st["session_low"] and st["session_low"] > 0:
                        st["daily_ranges"].append(
                            (st["session_high"] - st["session_low"]) / st["session_low"] * 100
                        )
                    if st["prev_close"] is not None:
                        st["daily_closes"].append(st["prev_close"])
                    if st["session_high"]:
                        st["daily_highs_20"].append(st["session_high"])

                    # Compute overnight return (prev_close → today's open)
                    bar = bars.get(sym)
                    if bar and st["prev_close"] and st["prev_close"] > 0:
                        on_ret = (bar.open - st["prev_close"]) / st["prev_close"] * 100
                        st["overnight_returns"].append(on_ret)

                        # If we have yesterday's features, record the feature→return pair
                        if st["yesterday_features"] is not None:
                            day_data.append((st["yesterday_features"], on_ret))

                    # Shift today's features to yesterday
                    st["yesterday_features"] = st["today_features"]
                    st["today_features"] = None

                # Reset for new day
                bar = bars.get(sym)
                st["current_date"] = current_date
                st["day_open"] = bar.open if bar else None
                st["session_volume"] = 0.0
                st["session_high"] = None
                st["session_low"] = None

            # Store pooled feature-return data
            if day_data:
                self._feature_history.append(day_data)

            # Re-estimate feature weights from correlation
            self._update_weights()
            self._current_date = current_date

        # Update intraday stats
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

    def _compute_features(self, sym: str) -> Optional[Dict[str, float]]:
        """Compute current features for a stock."""
        st = self._state.get(sym)
        if st is None or st["day_open"] is None or st["prev_close"] is None:
            return None
        if st["day_open"] <= 0:
            return None

        features = {}

        # 1. Intraday return
        features["intraday_return"] = (st["prev_close"] - st["day_open"]) / st["day_open"] * 100

        # 2. RS vs SPY
        features["rs_vs_spy"] = features["intraday_return"] - self._spy_return

        # 3. RVOL
        if st["daily_volumes"] and st["session_volume"] > 0:
            avg_vol = sum(st["daily_volumes"]) / len(st["daily_volumes"])
            features["rvol"] = st["session_volume"] / avg_vol if avg_vol > 0 else 1.0
        else:
            features["rvol"] = 1.0

        # 4. Gap %
        closes = list(st["daily_closes"])
        if closes:
            features["gap_pct"] = (st["day_open"] - closes[-1]) / closes[-1] * 100 if closes[-1] > 0 else 0
        else:
            features["gap_pct"] = 0.0

        # 5. Range expansion
        if (st["daily_ranges"] and st["session_high"] and st["session_low"]
                and st["session_low"] > 0):
            curr_range = (st["session_high"] - st["session_low"]) / st["session_low"] * 100
            avg_range = sum(st["daily_ranges"]) / len(st["daily_ranges"])
            features["range_pct"] = curr_range / avg_range if avg_range > 0 else 1.0
        else:
            features["range_pct"] = 1.0

        # 6. Distance from 20-day high
        if st["daily_highs_20"] and st["prev_close"] > 0:
            high_20 = max(st["daily_highs_20"])
            features["dist_from_high"] = (st["prev_close"] - high_20) / high_20 * 100
        else:
            features["dist_from_high"] = 0.0

        # 7. Average overnight gap (stock personality)
        if st["overnight_returns"]:
            features["avg_on_gap"] = sum(st["overnight_returns"]) / len(st["overnight_returns"])
        else:
            features["avg_on_gap"] = 0.0

        # 8. 5-day momentum
        if len(closes) >= 5 and closes[-5] > 0:
            features["momentum_5d"] = (closes[-1] - closes[-5]) / closes[-5] * 100
        else:
            features["momentum_5d"] = 0.0

        return features

    def _update_weights(self) -> None:
        """Re-estimate feature weights from rolling feature-return correlations."""
        if len(self._feature_history) < self.min_data_days:
            return  # not enough data yet

        # Pool all feature-return pairs from history
        all_pairs: List[Tuple[Dict[str, float], float]] = []
        for day_data in self._feature_history:
            all_pairs.extend(day_data)

        if len(all_pairs) < 30:
            return

        # Compute correlation of each feature with overnight return
        for feat_name in FEATURE_NAMES:
            feat_vals = [p[0].get(feat_name, 0) for p in all_pairs]
            ret_vals = [p[1] for p in all_pairs]

            corr = self._pearson(feat_vals, ret_vals)
            # Weight = absolute correlation (we want features that predict, regardless of sign)
            # But preserve sign for direction bias
            self._weights[feat_name] = corr if not math.isnan(corr) else 0.0

    @staticmethod
    def _pearson(x: List[float], y: List[float]) -> float:
        """Simple Pearson correlation."""
        n = len(x)
        if n < 5:
            return 0.0
        mx = sum(x) / n
        my = sum(y) / n
        cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        sx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
        sy = math.sqrt(sum((yi - my) ** 2 for yi in y))
        if sx == 0 or sy == 0:
            return 0.0
        return cov / (sx * sy)

    def select(self, top_n: int = 10) -> List[ScoredStock]:
        """Score all stocks using learned weights and return top-N."""
        scored: List[ScoredStock] = []

        for sym, st in self._state.items():
            features = self._compute_features(sym)
            if features is None:
                continue

            # Save features for tomorrow's correlation update
            st["today_features"] = features

            # Score = weighted sum of features
            # Positive weight × positive feature → long bias
            # Negative weight × negative feature → long bias (double negative)
            score = 0.0
            for feat_name in FEATURE_NAMES:
                w = self._weights.get(feat_name, 0)
                v = features.get(feat_name, 0)
                score += w * v

            # Absolute score for ranking (we want MAGNITUDE of predicted return)
            abs_score = abs(score)
            direction = "long" if score > 0 else "short" if score < 0 else "neutral"

            scored.append(ScoredStock(
                symbol=sym,
                score=round(abs_score, 4),
                direction_bias=direction,
                tags={k: round(v, 3) for k, v in features.items()},
            ))

        # Sort by absolute predicted return (highest conviction first)
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_n]

    def get_weights(self) -> Dict[str, float]:
        """Return current learned weights (for debugging/logging)."""
        return {k: round(v, 4) for k, v in self._weights.items()}
