"""RSI Intraday Mean Reversion — intraday, same-day close.

Idea: When RSI hits an extreme level intraday (very overbought or oversold),
price is extended and likely to snap back. Fade the extreme.

Key difference from the base RSI strategy: RSI state resets every session,
so the indicator measures intraday momentum only (not multi-day drift).

Rules:
  1. RSI state (avg_gain / avg_loss) resets at the start of every trading day.
  2. Entry window: opens at 9:30 ET, closes at `entry_end_hour` (default 13:00).
  3. SHORT when intraday RSI > `overbought` (overbought spike — expect pullback).
  4. LONG when intraday RSI < `oversold` (oversold flush — expect bounce).
  5. Exit: target is `exit_short` RSI (recovery for short) / `exit_long` (recovery for long).
  6. Stop loss: `stop_pct`% from entry.
  7. Optional SPY VWAP regime filter:
       - When SPY is below VWAP (bearish day) → only take SHORT entries.
       - When SPY is above VWAP (bullish day)  → only take LONG entries.
       - Direction overrides the regime filter if set to long_only / short_only.
  8. One trade per symbol per day.
  9. EOD flatten at 15:55 ET (engine handles this).
"""

from datetime import date
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class RSIIntradayStrategy(Strategy):
    name = "rsi_intraday"
    label = "RSI Intraday Reversion"

    def __init__(
        self,
        symbols: List[str],
        rsi_period: int = 14,
        overbought: float = 75.0,
        oversold: float = 25.0,
        exit_short: float = 55.0,   # RSI recovery target for short exit
        exit_long: float = 45.0,    # RSI recovery target for long exit
        stop_pct: float = 1.0,       # % stop from entry
        profit_target_pct: float = 0.0,  # % profit target from entry (0 = use RSI exit instead)
        direction: str = "both",    # "both" | "long_only" | "short_only"
        regime_filter: bool = True,  # use SPY VWAP to restrict direction by session bias
        entry_end_hour: int = 13,   # no new entries after this ET hour (default 13:00)
    ) -> None:
        super().__init__(symbols)
        self.rsi_period = rsi_period
        self.overbought = overbought
        self.oversold = oversold
        self.exit_short = exit_short
        self.exit_long = exit_long
        self.stop_pct = stop_pct
        self.profit_target_pct = profit_target_pct
        self.direction = direction
        self.regime_filter = regime_filter
        self.entry_end_hour = entry_end_hour
        self._state: Dict[str, dict] = {}
        self._spy_state: dict = {}

    def _fresh_rsi(self) -> dict:
        """Per-symbol per-day RSI accumulator."""
        return {
            "bars": 0,
            "prev_close": None,
            "avg_gain": None,
            "avg_loss": None,
            "_gains": [],
            "_losses": [],
        }

    def _fresh_day(self) -> dict:
        return {
            "current_date": None,
            "traded_today": False,
            "stop_level": None,
            "take_profit": None,
            "position_side": None,
            "rsi": self._fresh_rsi(),
        }

    def _fresh_spy(self) -> dict:
        return {
            "current_date": None,
            "vwap_num": 0.0,
            "vwap_den": 0.0,
            "vwap": None,
        }

    def on_start(self) -> None:
        self._state = {sym: self._fresh_day() for sym in self.symbols}
        self._spy_state = self._fresh_spy()

    def rules(self) -> List[str]:
        regime_note = ("SPY VWAP regime filter — only short on bearish sessions, "
                       "only long on bullish sessions") if self.regime_filter else "No regime filter"
        return [
            f"Intraday RSI({self.rsi_period}) — state resets every session at open",
            f"SHORT entry when RSI > {self.overbought} (overbought spike)",
            f"LONG entry when RSI < {self.oversold} (oversold flush)",
            f"Exit SHORT when RSI drops below {self.exit_short} (momentum exhausted)",
            f"Exit LONG when RSI rises above {self.exit_long}",
            f"Stop loss: {self.stop_pct}% from entry",
            f"Direction: {self.direction}",
            f"{regime_note}",
            f"No new entries after {self.entry_end_hour}:00 ET",
            f"One trade per symbol per day",
            f"EOD flatten at 15:55 ET",
        ]

    def _compute_rsi(self, rsi_st: dict, close: float) -> Optional[float]:
        """Wilder RSI on 1m closes. Returns RSI or None until warm-up complete."""
        prev = rsi_st["prev_close"]
        rsi_st["prev_close"] = close
        rsi_st["bars"] += 1

        if prev is None:
            return None

        change = close - prev
        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        if rsi_st["avg_gain"] is None:
            # Warm-up phase: accumulate rsi_period bars
            rsi_st["_gains"].append(gain)
            rsi_st["_losses"].append(loss)
            if rsi_st["bars"] >= self.rsi_period:
                rsi_st["avg_gain"] = sum(rsi_st["_gains"]) / self.rsi_period
                rsi_st["avg_loss"] = sum(rsi_st["_losses"]) / self.rsi_period
                # Don't return yet — need one more bar to produce first value
            return None
        else:
            # Wilder smoothing
            rsi_st["avg_gain"] = (rsi_st["avg_gain"] * (self.rsi_period - 1) + gain) / self.rsi_period
            rsi_st["avg_loss"] = (rsi_st["avg_loss"] * (self.rsi_period - 1) + loss) / self.rsi_period

        if rsi_st["avg_loss"] == 0:
            return 100.0
        rs = rsi_st["avg_gain"] / rsi_st["avg_loss"]
        return 100 - 100 / (1 + rs)

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

        # Update SPY VWAP
        spy_bar = bars.get("SPY")
        spy_vwap: Optional[float] = None
        spy_price: Optional[float] = None
        if spy_bar is not None:
            et_spy = spy_bar.timestamp.astimezone(ET)
            spy_vwap = self._update_spy_vwap(spy_bar, et_spy.date())
            spy_price = spy_bar.close

        for symbol in self.symbols:
            bar = bars.get(symbol)
            if bar is None:
                continue

            ts = bar.timestamp
            et = ts.astimezone(ET)
            today = et.date()
            st = self._state[symbol]

            # Day reset — also resets RSI accumulator
            if st["current_date"] != today:
                st["current_date"] = today
                st["traded_today"] = False
                st["stop_level"] = None
                st["position_side"] = None
                st["rsi"] = self._fresh_rsi()

            rsi = self._compute_rsi(st["rsi"], bar.close)
            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # Manage open position (stop + profit target or RSI exit)
            if current_qty > 0:  # long
                if st["stop_level"] is not None and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason=f"RSI long stop"))
                elif st["take_profit"] is not None and price >= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason=f"RSI long TP"))
                elif st["take_profit"] is None and rsi is not None and rsi > self.exit_long:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"RSI={rsi:.1f}>{self.exit_long} long exit"))
                continue

            if current_qty < 0:  # short
                if st["stop_level"] is not None and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason=f"RSI short stop"))
                elif st["take_profit"] is not None and price <= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason=f"RSI short TP"))
                elif st["take_profit"] is None and rsi is not None and rsi < self.exit_short:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"RSI={rsi:.1f}<{self.exit_short} short exit"))
                continue

            # Entry checks
            if rsi is None or st["traded_today"] or et.hour >= self.entry_end_hour:
                continue

            # Regime + direction gate
            spy_bullish = (spy_vwap is not None and spy_price is not None and spy_price > spy_vwap)
            spy_bearish = (spy_vwap is not None and spy_price is not None and spy_price < spy_vwap)

            allow_long  = self.direction in ("both", "long_only")
            allow_short = self.direction in ("both", "short_only")

            if self.regime_filter:
                allow_long  = allow_long  and spy_bullish
                allow_short = allow_short and spy_bearish

            # SHORT on overbought spike
            if rsi > self.overbought and allow_short:
                st["traded_today"] = True
                st["stop_level"] = price * (1 + self.stop_pct / 100)
                st["take_profit"] = (price * (1 - self.profit_target_pct / 100)
                                     if self.profit_target_pct > 0 else None)
                st["position_side"] = "short"
                signals.append(Signal(symbol, Direction.SHORT,
                                      reason=f"RSI={rsi:.1f}>{self.overbought} overbought"))

            # LONG on oversold flush
            elif rsi < self.oversold and allow_long:
                st["traded_today"] = True
                st["stop_level"] = price * (1 - self.stop_pct / 100)
                st["take_profit"] = (price * (1 + self.profit_target_pct / 100)
                                     if self.profit_target_pct > 0 else None)
                st["position_side"] = "long"
                signals.append(Signal(symbol, Direction.LONG,
                                      reason=f"RSI={rsi:.1f}<{self.oversold} oversold"))

        return signals
