"""Combined RS + Intraday Momentum — Two-Sleeve System.

Combines the proven bear sleeve (RS short) with a bull complement
(intraday time-series momentum long) in a single strategy.

Bear sleeve (RS short):
  - Only fires on bearish SPY sessions (below VWAP) with 3-day trend filter
  - Short stocks showing relative weakness vs SPY (RS < -threshold)
  - Entry: 15 min after open until 14:00 ET

Bull sleeve (Intraday Momentum long):
  - Only fires on bullish SPY sessions (above VWAP)
  - At 10:00 ET: long stocks up > momentum_threshold% from open
  - Captures bull-market continuation days

The two sleeves are naturally complementary:
  - Bear sessions: SPY below VWAP + 3d trend down → RS shorts fire, momentum longs blocked
  - Bull sessions: SPY above VWAP → momentum longs fire at 10:00, RS shorts blocked
"""

from collections import deque
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class CombinedRSMomentumStrategy(Strategy):
    name = "combined_rs_momentum"
    label = "Combined RS Short + Intraday Momentum"

    def __init__(
        self,
        symbols: List[str],
        # RS short params
        rs_threshold: float = 1.0,
        rs_stop_pct: float = 1.0,
        rs_profit_target_pct: float = 2.0,
        spy_trend_days: int = 3,
        rs_entry_after_min: int = 15,
        rs_entry_end_hour: int = 14,
        # ITM long params
        momentum_threshold: float = 0.3,
        itm_stop_pct: float = 1.5,
        itm_entry_hour: int = 10,
        itm_entry_minute: int = 0,
    ) -> None:
        super().__init__(symbols)
        self.rs_threshold = rs_threshold
        self.rs_stop_pct = rs_stop_pct
        self.rs_profit_target_pct = rs_profit_target_pct
        self.spy_trend_days = spy_trend_days
        self.rs_entry_after_min = rs_entry_after_min
        self.rs_entry_end_hour = rs_entry_end_hour
        self.momentum_threshold = momentum_threshold
        self.itm_stop_pct = itm_stop_pct
        self.itm_entry_hour = itm_entry_hour
        self.itm_entry_minute = itm_entry_minute
        self._state: Dict[str, dict] = {}
        self._spy_state: dict = {}

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "rs_traded": False,
            "itm_attempted": False,
            "itm_traded": False,
            "stop_level": None,
            "take_profit": None,
            "position_type": None,  # "rs_short" | "itm_long"
        }

    def _fresh_spy(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "vwap_num": 0.0,
            "vwap_den": 0.0,
            "vwap": None,
            "prev_close": None,
            "daily_closes": deque(maxlen=max(self.spy_trend_days, 1)),
        }

    def on_start(self) -> None:
        self._state = {sym: self._fresh_sym() for sym in self.symbols}
        self._spy_state = self._fresh_spy()

    def rules(self) -> List[str]:
        return [
            "=== BEAR SLEEVE (RS Short) ===",
            f"Active on: bearish SPY sessions (below VWAP) + SPY < close {self.spy_trend_days} days ago",
            f"SHORT when stock RS < -{self.rs_threshold}% vs SPY",
            f"Stop: {self.rs_stop_pct}% | Target: {self.rs_profit_target_pct}%",
            f"Entry window: {self.rs_entry_after_min} min after open → {self.rs_entry_end_hour}:00 ET",
            "=== BULL SLEEVE (Intraday Momentum Long) ===",
            f"Active on: bullish SPY sessions (above VWAP)",
            f"LONG at {self.itm_entry_hour}:{self.itm_entry_minute:02d} ET when return > +{self.momentum_threshold}% from open",
            f"Stop: {self.itm_stop_pct}% | Hold to EOD",
            "One trade per sleeve per symbol per day",
            "EOD flatten at 15:55 ET",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # ── Process SPY ───────────────────────────────────────────────────────
        spy_bar = bars.get("SPY")
        spy_return_pct: Optional[float] = None
        spy_vwap: Optional[float] = None
        spy_price: Optional[float] = None
        spy_bearish = False
        spy_bullish = False

        if spy_bar is not None:
            et_spy = spy_bar.timestamp.astimezone(ET)
            spy_today = et_spy.date()
            spy = self._spy_state

            if spy["current_date"] != spy_today:
                if spy["prev_close"] is not None:
                    spy["daily_closes"].append(spy["prev_close"])
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

            spy_price = spy_bar.close
            spy_vwap = spy["vwap"]
            spy["prev_close"] = spy_price

            if spy["day_open"] and spy["day_open"] > 0:
                spy_return_pct = (spy_price - spy["day_open"]) / spy["day_open"] * 100

            spy_bullish = spy_vwap is not None and spy_price > spy_vwap
            spy_bearish = spy_vwap is not None and spy_price < spy_vwap

            # Multi-day trend check
            if self.spy_trend_days > 0 and spy_price is not None:
                closes = spy["daily_closes"]
                if len(closes) >= self.spy_trend_days:
                    spy_bearish = spy_bearish and spy_price < closes[0]

        # ── Per-symbol logic ──────────────────────────────────────────────────
        for symbol in self.symbols:
            if symbol == "SPY":
                continue

            bar = bars.get(symbol)
            if bar is None:
                continue

            et = bar.timestamp.astimezone(ET)
            today = et.date()
            st = self._state[symbol]

            if st["current_date"] != today:
                st["current_date"] = today
                st["day_open"] = bar.open
                st["rs_traded"] = False
                st["itm_attempted"] = False
                st["itm_traded"] = False
                st["stop_level"] = None
                st["take_profit"] = None
                st["position_type"] = None

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # Manage open position
            if current_qty > 0:
                if st["stop_level"] is not None and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason=f"{st['position_type']} stop"))
                elif st["take_profit"] is not None and price >= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason=f"{st['position_type']} target"))
                continue

            if current_qty < 0:
                if st["stop_level"] is not None and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason=f"{st['position_type']} stop"))
                elif st["take_profit"] is not None and price <= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason=f"{st['position_type']} target"))
                continue

            if st["day_open"] is None or st["day_open"] == 0:
                continue

            bar_mins = et.hour * 60 + et.minute
            open_mins = 9 * 60 + 30

            # ── BEAR SLEEVE: RS short ─────────────────────────────────────────
            if (not st["rs_traded"]
                    and spy_bearish
                    and spy_return_pct is not None
                    and bar_mins >= open_mins + self.rs_entry_after_min
                    and et.hour < self.rs_entry_end_hour):

                stock_return_pct = (price - st["day_open"]) / st["day_open"] * 100
                rs = stock_return_pct - spy_return_pct

                if rs < -self.rs_threshold:
                    st["rs_traded"] = True
                    st["stop_level"] = price * (1 + self.rs_stop_pct / 100)
                    st["take_profit"] = (price * (1 - self.rs_profit_target_pct / 100)
                                         if self.rs_profit_target_pct > 0 else None)
                    st["position_type"] = "rs_short"
                    signals.append(Signal(
                        symbol, Direction.SHORT,
                        reason=f"RS={rs:.2f}%<-{self.rs_threshold}% bear session"
                    ))
                continue  # don't also check ITM if RS check ran

            # ── BULL SLEEVE: ITM long ─────────────────────────────────────────
            itm_entry_mins = self.itm_entry_hour * 60 + self.itm_entry_minute

            if (not st["itm_attempted"]
                    and not st["itm_traded"]
                    and spy_bullish
                    and bar_mins >= itm_entry_mins):

                st["itm_attempted"] = True

                if bar_mins <= itm_entry_mins + 5:  # 5-min window
                    return_pct = (price - st["day_open"]) / st["day_open"] * 100
                    if return_pct > self.momentum_threshold:
                        st["itm_traded"] = True
                        st["stop_level"] = price * (1 - self.itm_stop_pct / 100)
                        st["take_profit"] = None  # hold to EOD
                        st["position_type"] = "itm_long"
                        signals.append(Signal(
                            symbol, Direction.LONG,
                            reason=f"ITM +{return_pct:.2f}%>+{self.momentum_threshold}% bull session"
                        ))

        return signals
