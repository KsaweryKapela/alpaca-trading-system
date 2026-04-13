"""Momentum Spike — intraday, volume-confirmed breakout.

Idea: When a stock breaks a recent high/low on abnormally high volume, that breakout
is more likely to be genuine (institutional order flow) than random noise.
Ride the directional momentum for the rest of the session.

Rules:
  1. Track rolling `vol_window`-bar average volume.
  2. Track rolling `breakout_window`-bar high and low.
  3. If volume > `vol_mult` × avg_volume AND price breaks above the `breakout_window`-bar high:
     → LONG signal (momentum breakout up).
  4. If volume > `vol_mult` × avg_volume AND price breaks below the `breakout_window`-bar low:
     → SHORT signal (momentum breakdown down).
  5. Stop loss: `stop_pct`% from entry in the adverse direction.
  6. Optional SPY VWAP regime filter: only enter in the SPY trend direction.
  7. No new entries after `entry_end_hour` ET.
  8. One trade per symbol per day.
  9. EOD flatten at 15:55 ET (handled by engine).
"""

from collections import deque
from datetime import date
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class MomentumSpikeStrategy(Strategy):
    name = "momentum_spike"
    label = "Momentum Spike"

    def __init__(
        self,
        symbols: List[str],
        vol_window: int = 20,           # bars for rolling avg volume baseline
        vol_mult: float = 2.0,          # volume must exceed vol_mult × avg
        breakout_window: int = 10,      # bars for rolling high/low breakout level
        stop_pct: float = 1.5,          # % stop from entry
        direction: str = "both",        # "both" | "long_only" | "short_only"
        regime_filter: bool = True,     # require SPY above/below VWAP to match direction
        entry_end_hour: int = 14,       # no new entries after this ET hour
    ) -> None:
        super().__init__(symbols)
        self.vol_window = vol_window
        self.vol_mult = vol_mult
        self.breakout_window = breakout_window
        self.stop_pct = stop_pct
        self.direction = direction
        self.regime_filter = regime_filter
        self.entry_end_hour = entry_end_hour
        self._state: Dict[str, dict] = {}
        self._spy_state: dict = {}

    def _fresh_day(self) -> dict:
        return {
            "current_date": None,
            "traded_today": False,
            "stop_level": None,
            "position_side": None,
            # Rolling buffers — persist across days (volume baseline needs history)
            "vol_buf": None,    # deque, initialised once
            "high_buf": None,   # deque
            "low_buf": None,    # deque
        }

    def _fresh_spy(self) -> dict:
        return {
            "current_date": None,
            "vwap_num": 0.0,
            "vwap_den": 0.0,
            "vwap": None,
        }

    def on_start(self) -> None:
        self._state = {}
        for sym in self.symbols:
            self._state[sym] = {
                "current_date": None,
                "traded_today": False,
                "stop_level": None,
                "position_side": None,
                "vol_buf":  deque(maxlen=self.vol_window),
                "high_buf": deque(maxlen=self.breakout_window),
                "low_buf":  deque(maxlen=self.breakout_window),
            }
        self._spy_state = self._fresh_spy()

    def rules(self) -> List[str]:
        regime_note = "SPY VWAP regime filter active — only enter in SPY trend direction" if self.regime_filter else "No regime filter"
        return [
            f"Rolling {self.vol_window}-bar average volume baseline",
            f"Rolling {self.breakout_window}-bar high/low breakout levels",
            f"Enter LONG when volume > {self.vol_mult}× avg AND price breaks {self.breakout_window}-bar high",
            f"Enter SHORT when volume > {self.vol_mult}× avg AND price breaks {self.breakout_window}-bar low",
            f"Stop loss: {self.stop_pct}% from entry",
            f"Direction: {self.direction}",
            f"{regime_note}",
            f"No new entries after {self.entry_end_hour}:00 ET",
            f"One trade per symbol per day",
            f"EOD flatten at 15:55 ET",
        ]

    def _update_spy_vwap(self, bar: Bar, et_date: date) -> Optional[float]:
        spy = self._spy_state
        if spy["current_date"] != et_date:
            spy["current_date"] = et_date
            spy["vwap_num"] = 0.0
            spy["vwap_den"] = 0.0
            spy["vwap"] = None
        typical = (bar.high + bar.low + bar.close) / 3
        spy["vwap_num"] += typical * bar.volume
        spy["vwap_den"] += bar.volume
        if spy["vwap_den"] > 0:
            spy["vwap"] = spy["vwap_num"] / spy["vwap_den"]
        return spy["vwap"]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # Update SPY VWAP for regime filter
        spy_bar = bars.get("SPY")
        spy_vwap: Optional[float] = None
        spy_price: Optional[float] = None
        if spy_bar is not None:
            et = spy_bar.timestamp.astimezone(ET)
            spy_vwap = self._update_spy_vwap(spy_bar, et.date())
            spy_price = spy_bar.close

        for symbol in self.symbols:
            if symbol == "SPY" and self.direction == "short_only":
                # Don't trade SPY against itself when regime-filtering
                pass
            bar = bars.get(symbol)
            if bar is None:
                continue

            ts = bar.timestamp
            et = ts.astimezone(ET)
            today = et.date()
            st = self._state[symbol]

            # Day reset (traded_today flag only — buffers persist)
            if st["current_date"] != today:
                st["current_date"] = today
                st["traded_today"] = False
                st["stop_level"] = None
                st["position_side"] = None

            # Update rolling buffers
            st["vol_buf"].append(bar.volume)
            st["high_buf"].append(bar.high)
            st["low_buf"].append(bar.low)

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # Manage open position
            if current_qty > 0:  # long
                if st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"momentum spike long stop"))
                continue

            if current_qty < 0:  # short
                if st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"momentum spike short stop"))
                continue

            # No new entries after cutoff
            if et.hour >= self.entry_end_hour:
                continue

            if st["traded_today"]:
                continue

            # Need enough bars in buffers (need vol_window-1 prior bars + 1 current)
            if (len(st["vol_buf"]) < 2 or len(st["vol_buf"]) < self.vol_window or
                    len(st["high_buf"]) < self.breakout_window):
                continue

            # Avg volume from prior bars only (exclude current bar which was just appended)
            vol_list = list(st["vol_buf"])
            prior_vols = vol_list[:-1]
            avg_vol = sum(prior_vols) / len(prior_vols) if prior_vols else 0
            if avg_vol == 0:
                continue

            vol_spike = bar.volume >= self.vol_mult * avg_vol

            # Previous bar highs/lows (exclude current bar from the level)
            prev_highs = list(st["high_buf"])[:-1]
            prev_lows  = list(st["low_buf"])[:-1]
            if not prev_highs:
                continue
            resist = max(prev_highs)
            support = min(prev_lows)

            # Regime filter: SPY above VWAP → bullish (prefer longs), below → bearish (prefer shorts)
            spy_bullish = (spy_vwap is not None and spy_price is not None and spy_price > spy_vwap)
            spy_bearish = (spy_vwap is not None and spy_price is not None and spy_price < spy_vwap)

            allow_long  = self.direction in ("both", "long_only")
            allow_short = self.direction in ("both", "short_only")

            if self.regime_filter:
                allow_long  = allow_long  and spy_bullish
                allow_short = allow_short and spy_bearish

            # Long signal: price breaks above resistance on volume spike
            if vol_spike and price > resist and allow_long:
                st["traded_today"] = True
                st["stop_level"] = price * (1 - self.stop_pct / 100)
                st["position_side"] = "long"
                signals.append(Signal(symbol, Direction.LONG,
                                      reason=f"vol_spike {bar.volume:.0f}>{self.vol_mult:.1f}×avg, break>{resist:.2f}"))

            # Short signal: price breaks below support on volume spike
            elif vol_spike and price < support and allow_short:
                st["traded_today"] = True
                st["stop_level"] = price * (1 + self.stop_pct / 100)
                st["position_side"] = "short"
                signals.append(Signal(symbol, Direction.SHORT,
                                      reason=f"vol_spike {bar.volume:.0f}>{self.vol_mult:.1f}×avg, break<{support:.2f}"))

        return signals
