"""Overnight Momentum — buy near close, capture the overnight gap.

Hypothesis:
  In bull markets, the majority of returns accrue overnight (close-to-open
  gap). Intraday strategies systematically miss this. A strategy that
  enters near close and exits next morning after the open captures the
  primary source of bull-market returns.

  The strategy buys stocks showing relative strength during the session
  (up vs SPY) near the close, holds overnight, and sells after the next
  open. On bearish sessions, it can short weak stocks and cover next morning.

  This requires eod_flatten=False in the engine.

Rules:
  1. At entry_hour ET (e.g., 15:30), evaluate each stock:
     - Compute session return (close vs open) and RS vs SPY.
  2. LONG when: stock return > min_return_pct% AND SPY is bullish (above VWAP)
     → stock is strong on a strong day → expect positive overnight gap.
  3. SHORT when: stock return < -min_return_pct% AND SPY is bearish
     → stock is weak on a weak day → expect negative overnight gap.
  4. Next day: exit at exit_after_min minutes after open.
  5. Stop: stop_pct% from entry (checked on next day bars).
  6. One trade per symbol per day.
  7. NO EOD flatten — positions held overnight by design.
"""

from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class OvernightMomentumStrategy(Strategy):
    name = "overnight_momentum"
    label = "Overnight Momentum (swing)"

    def __init__(
        self,
        symbols: List[str],
        min_return_pct: float = 0.5,     # stock must be up/down this % from open at entry time
        stop_pct: float = 2.0,           # stop from entry (wider for overnight holds)
        direction: str = "both",         # "both" | "long_only" | "short_only"
        regime_filter: bool = True,      # SPY VWAP regime filter
        entry_hour: int = 15,            # ET hour for entry (near close)
        entry_minute: int = 30,          # ET minute for entry
        exit_after_min: int = 15,        # exit this many minutes after next day open
    ) -> None:
        super().__init__(symbols)
        self.min_return_pct = min_return_pct
        self.stop_pct = stop_pct
        self.direction = direction
        self.regime_filter = regime_filter
        self.entry_hour = entry_hour
        self.entry_minute = entry_minute
        self.exit_after_min = exit_after_min
        self._state: Dict[str, dict] = {}
        self._spy_state: dict = {}

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "entry_attempted": False,
            "holding_overnight": False,
            "entry_price": None,
            "stop_level": None,
            "entry_date": None,
        }

    def _fresh_spy(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "vwap_num": 0.0,
            "vwap_den": 0.0,
            "vwap": None,
        }

    def on_start(self) -> None:
        self._state = {sym: self._fresh_sym() for sym in self.symbols}
        self._spy_state = self._fresh_spy()

    def rules(self) -> List[str]:
        regime_note = "SPY VWAP regime filter" if self.regime_filter else "No regime filter"
        return [
            f"At {self.entry_hour}:{self.entry_minute:02d} ET: evaluate each stock's session return",
            f"LONG when return > +{self.min_return_pct}% and SPY bullish → hold overnight",
            f"SHORT when return < -{self.min_return_pct}% and SPY bearish → hold overnight",
            f"Exit: {self.exit_after_min} min after next day open",
            f"Stop: {self.stop_pct}% from entry",
            f"Direction: {self.direction}",
            regime_note,
            f"Positions held overnight — NO EOD flatten",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # SPY regime
        spy_bar = bars.get("SPY")
        spy_bullish = False
        spy_bearish = False

        if spy_bar is not None:
            et_spy = spy_bar.timestamp.astimezone(ET)
            spy_today = et_spy.date()
            spy = self._spy_state

            if spy["current_date"] != spy_today:
                spy["current_date"] = spy_today
                spy["day_open"] = spy_bar.open
                spy["vwap_num"] = 0.0
                spy["vwap_den"] = 0.0
                spy["vwap"] = None

            typical = (spy_bar.high + spy_bar.low + spy_bar.close) / 3
            spy["vwap_num"] += typical * spy_bar.volume
            spy["vwap_den"] += spy_bar.volume
            if spy["vwap_den"] > 0:
                spy["vwap"] = spy["vwap_num"] / spy["vwap_den"]

            if spy["vwap"] is not None:
                spy_bullish = spy_bar.close > spy["vwap"]
                spy_bearish = spy_bar.close < spy["vwap"]

        for symbol in self.symbols:
            if symbol == "SPY":
                continue

            bar = bars.get(symbol)
            if bar is None:
                continue

            et = bar.timestamp.astimezone(ET)
            today = et.date()
            st = self._state[symbol]

            # Day reset — track new day
            if st["current_date"] != today:
                # If we are holding overnight, mark that we need to exit today
                if not st["holding_overnight"]:
                    st["entry_attempted"] = False
                st["current_date"] = today
                st["day_open"] = bar.open

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0
            bar_mins = et.hour * 60 + et.minute
            open_mins = 9 * 60 + 30

            # Exit logic: if holding overnight, exit after exit_after_min on new day
            if st["holding_overnight"] and st["entry_date"] != today:
                # Check stop
                if current_qty > 0 and st["stop_level"] is not None and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="overnight long stop"))
                    st["holding_overnight"] = False
                    st["entry_attempted"] = False
                    continue
                if current_qty < 0 and st["stop_level"] is not None and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="overnight short stop"))
                    st["holding_overnight"] = False
                    st["entry_attempted"] = False
                    continue

                # Time-based exit
                if bar_mins >= open_mins + self.exit_after_min:
                    reason = f"overnight exit +{self.exit_after_min}min"
                    signals.append(Signal(symbol, Direction.FLAT, reason=reason))
                    st["holding_overnight"] = False
                    st["entry_attempted"] = False
                continue

            # If holding overnight but same day (entry day), just monitor stop
            if current_qty != 0 and st["holding_overnight"]:
                if current_qty > 0 and st["stop_level"] is not None and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="overnight long stop (entry day)"))
                    st["holding_overnight"] = False
                elif current_qty < 0 and st["stop_level"] is not None and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="overnight short stop (entry day)"))
                    st["holding_overnight"] = False
                continue

            # Entry logic: at entry time
            if st["entry_attempted"]:
                continue
            if st["day_open"] is None or st["day_open"] == 0:
                continue

            entry_mins = self.entry_hour * 60 + self.entry_minute
            if bar_mins < entry_mins:
                continue

            st["entry_attempted"] = True
            if bar_mins > entry_mins + 5:
                continue  # missed window

            return_pct = (price - st["day_open"]) / st["day_open"] * 100

            allow_long = self.direction in ("both", "long_only")
            allow_short = self.direction in ("both", "short_only")

            if self.regime_filter:
                allow_long = allow_long and spy_bullish
                allow_short = allow_short and spy_bearish

            if return_pct > self.min_return_pct and allow_long:
                st["holding_overnight"] = True
                st["entry_price"] = price
                st["entry_date"] = today
                st["stop_level"] = price * (1 - self.stop_pct / 100)
                signals.append(Signal(
                    symbol, Direction.LONG,
                    reason=f"overnight long: +{return_pct:.1f}% at close, bullish session"
                ))

            elif return_pct < -self.min_return_pct and allow_short:
                st["holding_overnight"] = True
                st["entry_price"] = price
                st["entry_date"] = today
                st["stop_level"] = price * (1 + self.stop_pct / 100)
                signals.append(Signal(
                    symbol, Direction.SHORT,
                    reason=f"overnight short: {return_pct:.1f}% at close, bearish session"
                ))

        return signals
