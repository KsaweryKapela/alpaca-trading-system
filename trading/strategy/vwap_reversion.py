"""VWAP Mean Reversion — intraday, same-day close.

Rules:
  1. Calculate running VWAP from market open each day.
  2. Entry window: market open through `entry_end_hour` ET (default 14:00).
  3. Go LONG when close < VWAP × (1 − entry_dev_pct / 100).
  4. Go SHORT when close > VWAP × (1 + entry_dev_pct / 100).
  5. Exit LONG when close >= VWAP (price returns to fair value).
  6. Exit SHORT when close <= VWAP.
  7. Stop loss at `stop_pct` from entry.
  8. Only one trade per asset per day.
  9. EOD flatten enforced by the engine at 15:55 ET.

VWAP = Σ(typical_price × volume) / Σ(volume)
typical_price = (high + low + close) / 3
"""

from datetime import date
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class VWAPReversionStrategy(Strategy):
    name = "vwap_reversion"
    label = "VWAP Mean Reversion"

    def __init__(
        self,
        symbols: List[str],
        entry_dev_pct: float = 0.3,   # % deviation from VWAP to trigger entry
        stop_pct: float = 0.4,         # % stop loss from entry price
        entry_end_hour: int = 14,      # no new entries after this ET hour
    ) -> None:
        super().__init__(symbols)
        self.entry_dev_pct = entry_dev_pct
        self.stop_pct = stop_pct
        self.entry_end_hour = entry_end_hour
        self._state: Dict[str, dict] = {}

    def _fresh_day(self) -> dict:
        return {
            "current_date": None,
            "vwap_num": 0.0,    # Σ(typical_price × volume)
            "vwap_den": 0.0,    # Σ(volume)
            "vwap": None,
            "traded_today": False,
            "stop_level": None,
            "entry_price": None,
            "position_side": None,
        }

    def on_start(self) -> None:
        self._state = {sym: self._fresh_day() for sym in self.symbols}

    def rules(self) -> List[str]:
        return [
            f"Calculate running VWAP from market open each day",
            f"Go LONG when price falls {self.entry_dev_pct}% below VWAP (oversold intraday)",
            f"Exit LONG when price returns to VWAP",
            f"Go SHORT when price rises {self.entry_dev_pct}% above VWAP (overbought intraday)",
            f"Exit SHORT when price returns to VWAP",
            f"Stop loss: {self.stop_pct}% from entry — applied immediately on next bar",
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

            vwap = st["vwap"]
            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # Manage open position
            if current_qty > 0:   # long
                if st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason=f"stop {price:.2f}<={st['stop_level']:.2f}"))
                elif price >= vwap:
                    signals.append(Signal(symbol, Direction.FLAT, reason=f"VWAP target {price:.2f}>={vwap:.2f}"))
                continue

            if current_qty < 0:   # short
                if st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason=f"stop {price:.2f}>={st['stop_level']:.2f}"))
                elif price <= vwap:
                    signals.append(Signal(symbol, Direction.FLAT, reason=f"VWAP target {price:.2f}<={vwap:.2f}"))
                continue

            # Entry signals (only if no trade today and within entry window)
            if st["traded_today"] or et.hour >= self.entry_end_hour:
                continue

            long_threshold  = vwap * (1 - self.entry_dev_pct / 100)
            short_threshold = vwap * (1 + self.entry_dev_pct / 100)

            if price < long_threshold:
                signals.append(Signal(symbol, Direction.LONG,
                                      reason=f"VWAP-{self.entry_dev_pct}% {price:.2f}<{long_threshold:.2f}"))
                st["traded_today"] = True
                st["entry_price"] = price
                st["stop_level"] = price * (1 - self.stop_pct / 100)
                st["position_side"] = "long"

            elif price > short_threshold:
                signals.append(Signal(symbol, Direction.SHORT,
                                      reason=f"VWAP+{self.entry_dev_pct}% {price:.2f}>{short_threshold:.2f}"))
                st["traded_today"] = True
                st["entry_price"] = price
                st["stop_level"] = price * (1 + self.stop_pct / 100)
                st["position_side"] = "short"

        return signals
