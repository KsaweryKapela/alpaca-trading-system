"""VWAP Momentum — intraday, same-day close.

Trades WITH the deviation from VWAP rather than against it.  In a trending
intraday regime, when price breaks away from VWAP it often continues — we
ride that continuation.

Rules:
  1. Calculate running VWAP from market open each day.
  2. Entry window: market open through `entry_end_hour` ET (default 14:00).
  3. Go LONG when close > VWAP × (1 + entry_dev_pct / 100).
  4. Go SHORT when close < VWAP × (1 − entry_dev_pct / 100).
  5. Profit target: `profit_target_mult` × entry_dev_pct from entry (default 2×).
  6. Stop loss: entry_dev_pct from entry (1:1 loss cap by default, tunable).
  7. Only one trade per asset per day.
  8. EOD flatten enforced by the engine at 15:55 ET.
"""

from datetime import date
from typing import Dict, List
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class VWAPMomentumStrategy(Strategy):
    name = "vwap_momentum"
    label = "VWAP Momentum"

    def __init__(
        self,
        symbols: List[str],
        entry_dev_pct: float = 0.3,       # % deviation from VWAP to trigger entry
        profit_target_mult: float = 2.0,  # profit target = mult × entry_dev_pct from entry
        stop_mult: float = 1.0,           # stop = mult × entry_dev_pct from entry
        entry_end_hour: int = 14,         # no new entries after this ET hour
    ) -> None:
        super().__init__(symbols)
        self.entry_dev_pct = entry_dev_pct
        self.profit_target_mult = profit_target_mult
        self.stop_mult = stop_mult
        self.entry_end_hour = entry_end_hour
        self._state: Dict[str, dict] = {}

    def _fresh_day(self) -> dict:
        return {
            "current_date": None,
            "vwap_num": 0.0,
            "vwap_den": 0.0,
            "vwap": None,
            "traded_today": False,
            "entry_price": None,
            "take_profit": None,
            "stop_level": None,
            "position_side": None,
        }

    def on_start(self) -> None:
        self._state = {sym: self._fresh_day() for sym in self.symbols}

    def rules(self) -> List[str]:
        pt = self.profit_target_mult * self.entry_dev_pct
        sl = self.stop_mult * self.entry_dev_pct
        return [
            f"Calculate running VWAP from market open each day",
            f"Go LONG when price rises {self.entry_dev_pct}% above VWAP (momentum breakout up)",
            f"Go SHORT when price falls {self.entry_dev_pct}% below VWAP (momentum breakout down)",
            f"Profit target: {pt:.2f}% from entry ({self.profit_target_mult}× entry deviation)",
            f"Stop loss: {sl:.2f}% from entry ({self.stop_mult}× entry deviation)",
            f"No new entries after {self.entry_end_hour}:00 ET",
            f"One trade per asset per day — no re-entry",
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

            if st["current_date"] != today:
                st.update(self._fresh_day())
                st["current_date"] = today

            # Update VWAP
            typical = (bar.high + bar.low + bar.close) / 3
            st["vwap_num"] += typical * bar.volume
            st["vwap_den"] += bar.volume
            if st["vwap_den"] > 0:
                st["vwap"] = st["vwap_num"] / st["vwap_den"]

            if st["vwap"] is None:
                continue

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # Manage open position
            if current_qty > 0:   # long — riding upward momentum
                if st["stop_level"] is not None and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"stop {price:.2f}<={st['stop_level']:.2f}"))
                elif st["take_profit"] is not None and price >= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"target {price:.2f}>={st['take_profit']:.2f}"))
                continue

            if current_qty < 0:   # short — riding downward momentum
                if st["stop_level"] is not None and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"stop {price:.2f}>={st['stop_level']:.2f}"))
                elif st["take_profit"] is not None and price <= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"target {price:.2f}<={st['take_profit']:.2f}"))
                continue

            # Entry signals
            if st["traded_today"] or et.hour >= self.entry_end_hour:
                continue

            if st["vwap"] is None:
                continue

            long_threshold  = st["vwap"] * (1 + self.entry_dev_pct / 100)
            short_threshold = st["vwap"] * (1 - self.entry_dev_pct / 100)
            dev_pts = price * self.entry_dev_pct / 100

            if price > long_threshold:
                st["traded_today"] = True
                st["entry_price"] = price
                st["take_profit"] = price * (1 + self.profit_target_mult * self.entry_dev_pct / 100)
                st["stop_level"]  = price * (1 - self.stop_mult * self.entry_dev_pct / 100)
                st["position_side"] = "long"
                signals.append(Signal(symbol, Direction.LONG,
                                      reason=f"VWAP+{self.entry_dev_pct}% mom {price:.2f}>{long_threshold:.2f}"))

            elif price < short_threshold:
                st["traded_today"] = True
                st["entry_price"] = price
                st["take_profit"] = price * (1 - self.profit_target_mult * self.entry_dev_pct / 100)
                st["stop_level"]  = price * (1 + self.stop_mult * self.entry_dev_pct / 100)
                st["position_side"] = "short"
                signals.append(Signal(symbol, Direction.SHORT,
                                      reason=f"VWAP-{self.entry_dev_pct}% mom {price:.2f}<{short_threshold:.2f}"))

        return signals
