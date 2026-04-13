"""Intraday Time-Series Momentum.

Hypothesis (grounded in published research, global sample):
  The return in the first ~30 minutes of the session predicts the
  direction for the remainder of the session. Stocks/ETFs that are up
  strongly in the first 30 minutes tend to continue higher into the
  close; those down strongly tend to continue lower.

  The strategy is naturally regime-adaptive: it goes long on bull days
  and short on bear days without an explicit regime filter. In a bull
  market (2025), most days open positive → long signals dominate.
  In a bear market (2026), many days open negative → short signals.

Rules:
  1. Track each symbol's % return from the day open.
  2. At entry_time ET (default 10:00 — 30 min after open):
       if return > +momentum_threshold% → LONG entry
       if return < -momentum_threshold% → SHORT entry
  3. Stop loss: stop_pct% from entry.
  4. Profit target: profit_target_pct% from entry (0 = hold to EOD).
  5. Direction filter: "both" | "long_only" | "short_only".
  6. One trade per symbol per day.
  7. EOD flatten at 15:55 ET (handled by engine).
"""

from typing import Dict, List
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class IntradayMomentumStrategy(Strategy):
    name = "intraday_momentum"
    label = "Intraday Time-Series Momentum"

    def __init__(
        self,
        symbols: List[str],
        momentum_threshold: float = 0.3,  # % from open needed to trigger entry
        stop_pct: float = 1.5,            # % stop from entry
        profit_target_pct: float = 0.0,   # % target from entry (0 = hold to EOD)
        direction: str = "both",          # "both" | "long_only" | "short_only"
        entry_hour: int = 10,             # ET hour for entry check
        entry_minute: int = 0,            # ET minute for entry check
    ) -> None:
        super().__init__(symbols)
        self.momentum_threshold = momentum_threshold
        self.stop_pct = stop_pct
        self.profit_target_pct = profit_target_pct
        self.direction = direction
        self.entry_hour = entry_hour
        self.entry_minute = entry_minute
        self._state: Dict[str, dict] = {}

    def _fresh_day(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "entry_attempted": False,
            "traded_today": False,
            "stop_level": None,
            "take_profit": None,
        }

    def on_start(self) -> None:
        self._state = {sym: self._fresh_day() for sym in self.symbols}

    def rules(self) -> List[str]:
        return [
            f"Track each symbol's % return from day open",
            f"Entry check at {self.entry_hour}:{self.entry_minute:02d} ET ({self.entry_hour*60+self.entry_minute - 9*60-30} min after open)",
            f"LONG if return > +{self.momentum_threshold}% at entry time",
            f"SHORT if return < -{self.momentum_threshold}% at entry time",
            f"Stop loss: {self.stop_pct}% from entry",
            *([] if self.profit_target_pct == 0 else
              [f"Profit target: {self.profit_target_pct}% from entry"]),
            f"Direction: {self.direction}",
            f"One trade per symbol per day",
            f"EOD flatten at 15:55 ET",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        for symbol in self.symbols:
            bar = bars.get(symbol)
            if bar is None:
                continue

            et = bar.timestamp.astimezone(ET)
            today = et.date()
            st = self._state[symbol]

            # Day reset
            if st["current_date"] != today:
                st["current_date"] = today
                st["day_open"] = bar.open
                st["entry_attempted"] = False
                st["traded_today"] = False
                st["stop_level"] = None
                st["take_profit"] = None

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # Manage open position
            if current_qty > 0:
                if st["stop_level"] is not None and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="ITM long stop"))
                elif st["take_profit"] is not None and price >= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="ITM long target"))
                continue

            if current_qty < 0:
                if st["stop_level"] is not None and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="ITM short stop"))
                elif st["take_profit"] is not None and price <= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="ITM short target"))
                continue

            # Skip if already attempted or traded today
            if st["entry_attempted"] or st["traded_today"]:
                continue
            if st["day_open"] is None or st["day_open"] == 0:
                continue

            # Entry gate: at the specific entry time (allow a 5-min window)
            bar_mins = et.hour * 60 + et.minute
            entry_mins = self.entry_hour * 60 + self.entry_minute

            if bar_mins < entry_mins:
                continue

            # Mark as attempted so we only try once per day
            st["entry_attempted"] = True

            if bar_mins > entry_mins + 5:
                # Missed the window — skip today
                continue

            return_pct = (price - st["day_open"]) / st["day_open"] * 100

            allow_long = self.direction in ("both", "long_only")
            allow_short = self.direction in ("both", "short_only")

            if return_pct > self.momentum_threshold and allow_long:
                st["traded_today"] = True
                st["stop_level"] = price * (1 - self.stop_pct / 100)
                st["take_profit"] = (price * (1 + self.profit_target_pct / 100)
                                     if self.profit_target_pct > 0 else None)
                signals.append(Signal(
                    symbol, Direction.LONG,
                    reason=f"ITM +{return_pct:.2f}%>+{self.momentum_threshold}% at {self.entry_hour}:{self.entry_minute:02d}ET"
                ))

            elif return_pct < -self.momentum_threshold and allow_short:
                st["traded_today"] = True
                st["stop_level"] = price * (1 + self.stop_pct / 100)
                st["take_profit"] = (price * (1 - self.profit_target_pct / 100)
                                     if self.profit_target_pct > 0 else None)
                signals.append(Signal(
                    symbol, Direction.SHORT,
                    reason=f"ITM {return_pct:.2f}%<-{self.momentum_threshold}% at {self.entry_hour}:{self.entry_minute:02d}ET"
                ))

        return signals
