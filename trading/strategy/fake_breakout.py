"""Fake Breakout (Liquidity Grab) — intraday, same-day close.

Idea: Retail traders place stop orders just above resistance / below support.
Market makers or large players briefly push price through those levels to
harvest the stops (the "liquidity grab"), then reverse hard. We enter on that
reversal and ride the snap-back into the range.

Detection logic:
  1. Track a rolling `window`-bar high (resistance) and low (support).
  2. "Break above resistance" = a bar's HIGH exceeds the prior-window high by
     at least `breakout_pct`%.
  3. "Fake" = that same bar CLOSES below the prior high (rejection candle).
     The break was a wick, not a real breakout.
  4. On a fake breakout ABOVE resistance → enter SHORT (trap buyers).
  5. On a fake breakdown BELOW support   → enter LONG  (trap sellers).
  6. Stop loss: above the wick high (for short) / below the wick low (for long)
     + a small `stop_buffer_pct` buffer.
  7. Profit target: VWAP or `target_pct`% from entry (whichever is first).
  8. Optional SPY VWAP regime filter: align direction with the session trend.
  9. No new entries after `entry_end_hour` ET.
 10. One trade per symbol per day.
 11. EOD flatten at 15:55 ET (handled by engine).
"""

from collections import deque
from datetime import date
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class FakeBreakoutStrategy(Strategy):
    name = "fake_breakout"
    label = "Fake Breakout"

    def __init__(
        self,
        symbols: List[str],
        window: int = 15,               # bars to define the range (resistance/support)
        breakout_pct: float = 0.1,      # minimum % pierce above/below the level
        stop_buffer_pct: float = 0.1,   # extra buffer above wick high for stop
        target_pct: float = 1.5,        # % profit target from entry
        direction: str = "both",        # "both" | "long_only" | "short_only"
        regime_filter: bool = True,     # SPY VWAP aligns direction to session bias
        entry_end_hour: int = 14,       # no new entries after this ET hour
    ) -> None:
        super().__init__(symbols)
        self.window = window
        self.breakout_pct = breakout_pct
        self.stop_buffer_pct = stop_buffer_pct
        self.target_pct = target_pct
        self.direction = direction
        self.regime_filter = regime_filter
        self.entry_end_hour = entry_end_hour
        self._state: Dict[str, dict] = {}
        self._spy_state: dict = {}

    def on_start(self) -> None:
        self._state = {}
        for sym in self.symbols:
            self._state[sym] = {
                "current_date": None,
                "traded_today": False,
                "stop_level": None,
                "take_profit": None,
                "position_side": None,
                "high_buf": deque(maxlen=self.window),
                "low_buf":  deque(maxlen=self.window),
                # VWAP per symbol (reset daily)
                "vwap_num": 0.0,
                "vwap_den": 0.0,
                "vwap": None,
            }
        self._spy_state = {
            "current_date": None,
            "vwap_num": 0.0,
            "vwap_den": 0.0,
            "vwap": None,
        }

    def rules(self) -> List[str]:
        regime_note = ("SPY VWAP regime filter — only short on bearish sessions, "
                       "only long on bullish") if self.regime_filter else "No regime filter"
        return [
            f"Rolling {self.window}-bar high/low defines the range (resistance/support)",
            f"Fake breakout UP: bar HIGH pierces {self.window}-bar high by ≥{self.breakout_pct}%, but CLOSE is below — trap",
            f"Fake breakdown DOWN: bar LOW pierces {self.window}-bar low by ≥{self.breakout_pct}%, but CLOSE is above — trap",
            f"Enter SHORT on fake breakout up (fade the liquidity grab)",
            f"Enter LONG on fake breakdown down",
            f"Stop loss: wick extreme + {self.stop_buffer_pct}% buffer",
            f"Profit target: {self.target_pct}% from entry OR VWAP (whichever first)",
            f"Direction: {self.direction}",
            f"{regime_note}",
            f"No new entries after {self.entry_end_hour}:00 ET",
            f"One trade per symbol per day",
            f"EOD flatten at 15:55 ET",
        ]

    def _update_vwap(self, state: dict, bar: Bar, today: date) -> Optional[float]:
        if state["current_date"] != today:
            state["current_date"] = today
            state["vwap_num"] = 0.0
            state["vwap_den"] = 0.0
            state["vwap"] = None
        typical = (bar.high + bar.low + bar.close) / 3
        state["vwap_num"] += typical * bar.volume
        state["vwap_den"] += bar.volume
        if state["vwap_den"] > 0:
            state["vwap"] = state["vwap_num"] / state["vwap_den"]
        return state["vwap"]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # Update SPY VWAP
        spy_bar = bars.get("SPY")
        spy_vwap: Optional[float] = None
        spy_price: Optional[float] = None
        if spy_bar is not None:
            et_spy = spy_bar.timestamp.astimezone(ET)
            spy_vwap = self._update_vwap(self._spy_state, spy_bar, et_spy.date())
            spy_price = spy_bar.close

        for symbol in self.symbols:
            bar = bars.get(symbol)
            if bar is None:
                continue

            ts = bar.timestamp
            et = ts.astimezone(ET)
            today = et.date()
            st = self._state[symbol]

            # Day reset
            if st["current_date"] != today:
                st["current_date"] = today
                st["traded_today"] = False
                st["stop_level"] = None
                st["take_profit"] = None
                st["position_side"] = None
                # Reset VWAP
                st["vwap_num"] = 0.0
                st["vwap_den"] = 0.0
                st["vwap"] = None

            # Update stock VWAP
            typical = (bar.high + bar.low + bar.close) / 3
            st["vwap_num"] += typical * bar.volume
            st["vwap_den"] += bar.volume
            if st["vwap_den"] > 0:
                st["vwap"] = st["vwap_num"] / st["vwap_den"]
            stock_vwap = st["vwap"]

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # Update rolling buffers before managing position
            # (use previous bar's values for entry detection, so append after check)

            # Manage open position
            if current_qty > 0:  # long
                hit_stop = st["stop_level"] and price <= st["stop_level"]
                hit_tp   = st["take_profit"] and price >= st["take_profit"]
                at_vwap  = stock_vwap is not None and price >= stock_vwap
                if hit_stop:
                    signals.append(Signal(symbol, Direction.FLAT, reason="fake_bo long stop"))
                elif hit_tp or at_vwap:
                    signals.append(Signal(symbol, Direction.FLAT, reason="fake_bo long target/VWAP"))
                st["high_buf"].append(bar.high)
                st["low_buf"].append(bar.low)
                continue

            if current_qty < 0:  # short
                hit_stop = st["stop_level"] and price >= st["stop_level"]
                hit_tp   = st["take_profit"] and price <= st["take_profit"]
                at_vwap  = stock_vwap is not None and price <= stock_vwap
                if hit_stop:
                    signals.append(Signal(symbol, Direction.FLAT, reason="fake_bo short stop"))
                elif hit_tp or at_vwap:
                    signals.append(Signal(symbol, Direction.FLAT, reason="fake_bo short target/VWAP"))
                st["high_buf"].append(bar.high)
                st["low_buf"].append(bar.low)
                continue

            # Entry logic
            if (st["traded_today"] or et.hour >= self.entry_end_hour
                    or len(st["high_buf"]) < self.window):
                st["high_buf"].append(bar.high)
                st["low_buf"].append(bar.low)
                continue

            prior_high = max(st["high_buf"])
            prior_low  = min(st["low_buf"])

            # Regime + direction gate
            spy_bullish = (spy_vwap is not None and spy_price is not None and spy_price > spy_vwap)
            spy_bearish = (spy_vwap is not None and spy_price is not None and spy_price < spy_vwap)

            allow_long  = self.direction in ("both", "long_only")
            allow_short = self.direction in ("both", "short_only")

            if self.regime_filter:
                allow_long  = allow_long  and spy_bullish
                allow_short = allow_short and spy_bearish

            # Fake breakout UP → short
            if allow_short:
                pierced_high = bar.high >= prior_high * (1 + self.breakout_pct / 100)
                close_below  = bar.close < prior_high  # closes back inside range
                if pierced_high and close_below:
                    wick_high = bar.high
                    stop = wick_high * (1 + self.stop_buffer_pct / 100)
                    tp   = bar.close * (1 - self.target_pct / 100)
                    st["traded_today"] = True
                    st["stop_level"]  = stop
                    st["take_profit"] = tp
                    st["position_side"] = "short"
                    signals.append(Signal(symbol, Direction.SHORT,
                                          reason=f"fake_break_up wick>{prior_high:.2f} close<level"))

            # Fake breakdown DOWN → long
            elif allow_long:
                pierced_low = bar.low <= prior_low * (1 - self.breakout_pct / 100)
                close_above = bar.close > prior_low   # closes back inside range
                if pierced_low and close_above:
                    wick_low = bar.low
                    stop = wick_low * (1 - self.stop_buffer_pct / 100)
                    tp   = bar.close * (1 + self.target_pct / 100)
                    st["traded_today"] = True
                    st["stop_level"]  = stop
                    st["take_profit"] = tp
                    st["position_side"] = "long"
                    signals.append(Signal(symbol, Direction.LONG,
                                          reason=f"fake_break_down wick<{prior_low:.2f} close>level"))

            st["high_buf"].append(bar.high)
            st["low_buf"].append(bar.low)

        return signals
