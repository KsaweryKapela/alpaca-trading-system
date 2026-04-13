"""Opening Range Breakout (ORB) — intraday, same-day close.

Rules:
  1. First `range_minutes` bars of each trading day establish the range:
       range_high = max(close) over first N bars
       range_low  = min(close) over first N bars
  2. After range is set, watch for a breakout:
       close > range_high → LONG
       close < range_low  → SHORT
  3. Only one trade per asset per day (no re-entry after an exit).
  4. Stop loss at `stop_pct` below/above entry.
  5. EOD flatten enforced by the engine at 15:55 ET.

All timestamps handled in ET via the engine's EOD logic.
"""

from datetime import date, datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30


class ORBStrategy(Strategy):
    name = "orb"
    label = "Opening Range Breakout"

    def __init__(
        self,
        symbols: List[str],
        range_minutes: int = 15,
        stop_pct: float = 0.5,
        direction: str = "both",  # "both" | "long_only" | "short_only"
    ) -> None:
        super().__init__(symbols)
        self.range_minutes = range_minutes
        self.stop_pct = stop_pct
        self.direction = direction
        self._state: Dict[str, dict] = {}

    def _fresh_day_state(self) -> dict:
        return {
            "range_bars": 0,
            "range_high": None,
            "range_low": None,
            "range_established": False,
            "traded_today": False,
            "stop_level": None,
            "position_side": None,   # "long" or "short"
            "current_date": None,
        }

    def on_start(self) -> None:
        self._state = {sym: self._fresh_day_state() for sym in self.symbols}

    def rules(self) -> List[str]:
        direction_rule = {
            "both": "Trade LONG breakouts above range-high AND SHORT breakdowns below range-low",
            "long_only": "Trade LONG breakouts above range-high only (no shorts)",
            "short_only": "Trade SHORT breakdowns below range-low only (no longs)",
        }.get(self.direction, f"Direction: {self.direction}")
        return [
            f"Observe first {self.range_minutes} minutes of each day to establish the opening range",
            direction_rule,
            f"Stop loss: {self.stop_pct}% from entry price",
            f"Only one trade per asset per day — no re-entry after exit",
            f"All positions closed by 15:55 ET (EOD flatten by engine)",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        for symbol in self.symbols:
            bar = bars.get(symbol)
            if bar is None:
                continue

            ts = bar.timestamp
            et = ts.astimezone(ET) if hasattr(ts, "astimezone") else ts
            today = et.date()
            st = self._state[symbol]

            # New day: reset state
            if st["current_date"] != today:
                st.update(self._fresh_day_state())
                st["current_date"] = today

            # During opening range accumulation
            if not st["range_established"]:
                # Only count bars after 9:30 ET
                if et.hour > MARKET_OPEN_HOUR or (et.hour == MARKET_OPEN_HOUR and et.minute >= MARKET_OPEN_MINUTE):
                    minutes_since_open = (et.hour - MARKET_OPEN_HOUR) * 60 + (et.minute - MARKET_OPEN_MINUTE)
                    if minutes_since_open < self.range_minutes:
                        # Accumulate range
                        if st["range_high"] is None:
                            st["range_high"] = bar.close
                            st["range_low"] = bar.close
                        else:
                            st["range_high"] = max(st["range_high"], bar.high)
                            st["range_low"] = min(st["range_low"], bar.low)
                        st["range_bars"] += 1
                    else:
                        st["range_established"] = True
                continue  # no signals during range accumulation

            if st["traded_today"]:
                # Check stop loss on open position
                pos = portfolio.get_position(symbol)
                if pos and pos.quantity != 0 and st["stop_level"] is not None:
                    if pos.quantity > 0 and bar.close <= st["stop_level"]:
                        signals.append(Signal(symbol, Direction.FLAT, reason=f"stop hit @ {bar.close:.2f}"))
                        st["traded_today"] = True
                    elif pos.quantity < 0 and bar.close >= st["stop_level"]:
                        signals.append(Signal(symbol, Direction.FLAT, reason=f"stop hit @ {bar.close:.2f}"))
                        st["traded_today"] = True
                continue

            # Look for breakout
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            if (bar.close > st["range_high"] and current_qty == 0
                    and self.direction in ("both", "long_only")):
                signals.append(Signal(symbol, Direction.LONG, reason=f"ORB breakout up {bar.close:.2f}>{st['range_high']:.2f}"))
                st["traded_today"] = True
                st["position_side"] = "long"
                st["stop_level"] = bar.close * (1 - self.stop_pct / 100)

            elif (bar.close < st["range_low"] and current_qty == 0
                    and self.direction in ("both", "short_only")):
                signals.append(Signal(symbol, Direction.SHORT, reason=f"ORB breakdown {bar.close:.2f}<{st['range_low']:.2f}"))
                st["traded_today"] = True
                st["position_side"] = "short"
                st["stop_level"] = bar.close * (1 + self.stop_pct / 100)

        return signals
