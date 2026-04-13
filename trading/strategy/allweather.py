"""All-Weather: RS Short Intraday + Overnight Long Swing.

The first strategy designed to earn in BOTH regimes:

Bear sleeve (intraday, during session):
  - RS short with SPY VWAP + 3-day trend filter
  - Enters 15 min after open, exits by EOD flatten or stop/target
  - Captures intraday relative weakness in bear markets

Bull sleeve (overnight, close → next open):
  - At 15:30 ET, buy stocks that are UP on bullish SPY sessions
  - Hold overnight, exit 5 min after next day open
  - Captures the overnight gap that drives bull-market returns

The two sleeves operate at DIFFERENT TIMES:
  - Bear sleeve: 9:45 → 15:55 ET (intraday only)
  - Bull sleeve: 15:30 → next day 9:35 ET (overnight only)

They can both be active on the same day if SPY transitions from
bearish to bullish (or vice versa), but in practice sessions tend
to be directionally consistent.

REQUIRES: eod_flatten=False (positions held overnight for bull sleeve).
The bear sleeve self-manages exits (stop + profit target before 15:55).
"""

from collections import deque
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class AllWeatherStrategy(Strategy):
    name = "allweather"
    label = "All-Weather (RS Short + Overnight Long)"

    def __init__(
        self,
        symbols: List[str],
        # Bear sleeve: RS short params
        rs_threshold: float = 1.0,
        rs_stop_pct: float = 1.0,
        rs_target_pct: float = 2.0,
        spy_trend_days: int = 3,
        rs_entry_after_min: int = 15,
        rs_entry_end_hour: int = 14,
        # Bull sleeve: Overnight long params
        overnight_min_return: float = 0.5,
        overnight_stop_pct: float = 2.0,
        overnight_entry_hour: int = 15,
        overnight_entry_minute: int = 30,
        overnight_exit_after_min: int = 5,
        bull_regime: str = "vwap",  # "vwap" = SPY > VWAP, "up_from_open" = SPY return > 0, "none" = always
    ) -> None:
        super().__init__(symbols)
        # Bear sleeve
        self.rs_threshold = rs_threshold
        self.rs_stop_pct = rs_stop_pct
        self.rs_target_pct = rs_target_pct
        self.spy_trend_days = spy_trend_days
        self.rs_entry_after_min = rs_entry_after_min
        self.rs_entry_end_hour = rs_entry_end_hour
        # Bull sleeve
        self.overnight_min_return = overnight_min_return
        self.overnight_stop_pct = overnight_stop_pct
        self.overnight_entry_hour = overnight_entry_hour
        self.overnight_entry_minute = overnight_entry_minute
        self.overnight_exit_after_min = overnight_exit_after_min
        self.bull_regime = bull_regime
        # State
        self._state: Dict[str, dict] = {}
        self._spy_state: dict = {}

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            # Bear sleeve state
            "rs_traded": False,
            "rs_stop": None,
            "rs_target": None,
            # Bull sleeve state
            "overnight_attempted": False,
            "holding_overnight": False,
            "overnight_entry_date": None,
            "overnight_stop": None,
            # Position tracking
            "position_type": None,  # "rs_short" | "overnight_long"
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
            "=== BEAR SLEEVE (RS Short, Intraday) ===",
            f"Active when: SPY below VWAP + SPY < close {self.spy_trend_days} days ago",
            f"SHORT when RS < -{self.rs_threshold}% vs SPY",
            f"Stop: {self.rs_stop_pct}% | Target: {self.rs_target_pct}%",
            f"Entry: {self.rs_entry_after_min} min after open → {self.rs_entry_end_hour}:00 ET",
            f"Exit: by stop/target or 15:55 (must be flat before overnight sleeve)",
            "=== BULL SLEEVE (Overnight Long, Swing) ===",
            f"Active when: SPY above VWAP at {self.overnight_entry_hour}:{self.overnight_entry_minute:02d} ET",
            f"LONG when stock return > +{self.overnight_min_return}% on bullish session",
            f"Hold overnight → exit {self.overnight_exit_after_min} min after next day open",
            f"Stop: {self.overnight_stop_pct}%",
            "=== TIMING ===",
            "Bear sleeve: 9:45 → 15:55 (intraday, exits before close)",
            "Bull sleeve: 15:30 → next day 9:35 (overnight only)",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # ── SPY state ──────────────────────────────────────────────────────────
        spy_bar = bars.get("SPY")
        spy_return_pct: Optional[float] = None
        spy_price: Optional[float] = None
        spy_vwap: Optional[float] = None
        spy_bullish = False
        spy_bearish_full = False  # bearish + trend filter

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

            # Full bear check: VWAP bearish + multi-day trend
            spy_bearish_full = spy_bearish
            if self.spy_trend_days > 0 and spy_price is not None:
                closes = spy["daily_closes"]
                if len(closes) >= self.spy_trend_days:
                    spy_bearish_full = spy_bearish_full and spy_price < closes[0]

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
                if not st["holding_overnight"]:
                    # Fresh day
                    st["rs_traded"] = False
                    st["overnight_attempted"] = False
                st["current_date"] = today
                st["day_open"] = bar.open

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0
            bar_mins = et.hour * 60 + et.minute
            open_mins = 9 * 60 + 30

            # ── EXIT: Overnight position from previous day ────────────────────
            if st["holding_overnight"] and st["overnight_entry_date"] != today:
                # Check stop
                if st["overnight_stop"] is not None and current_qty > 0 and price <= st["overnight_stop"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="allweather overnight stop"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                    continue

                # Time exit
                if bar_mins >= open_mins + self.overnight_exit_after_min:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"allweather overnight exit +{self.overnight_exit_after_min}min"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            # ── MANAGE: Intraday RS short position ────────────────────────────
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["rs_stop"] is not None and price >= st["rs_stop"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="allweather RS stop"))
                    st["position_type"] = None
                elif st["rs_target"] is not None and price <= st["rs_target"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="allweather RS target"))
                    st["position_type"] = None
                # Force close RS shorts by 15:25 (before overnight entry window)
                elif et.hour == 15 and et.minute >= 25:
                    signals.append(Signal(symbol, Direction.FLAT, reason="allweather RS pre-close flat"))
                    st["position_type"] = None
                continue

            # ── MANAGE: Overnight long on entry day ───────────────────────────
            if current_qty > 0 and st["holding_overnight"] and st["overnight_entry_date"] == today:
                if st["overnight_stop"] is not None and price <= st["overnight_stop"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="allweather overnight stop (entry day)"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            if current_qty != 0:
                continue  # position from unknown source, skip

            if st["day_open"] is None or st["day_open"] == 0:
                continue

            # ── ENTRY: Bear sleeve (RS short) ─────────────────────────────────
            if (not st["rs_traded"]
                    and spy_bearish_full
                    and spy_return_pct is not None
                    and bar_mins >= open_mins + self.rs_entry_after_min
                    and et.hour < self.rs_entry_end_hour):

                stock_return = (price - st["day_open"]) / st["day_open"] * 100
                rs = stock_return - spy_return_pct

                if rs < -self.rs_threshold:
                    st["rs_traded"] = True
                    st["rs_stop"] = price * (1 + self.rs_stop_pct / 100)
                    st["rs_target"] = (price * (1 - self.rs_target_pct / 100)
                                       if self.rs_target_pct > 0 else None)
                    st["position_type"] = "rs_short"
                    signals.append(Signal(
                        symbol, Direction.SHORT,
                        reason=f"allweather RS={rs:.1f}% bear sleeve"
                    ))
                continue

            # ── ENTRY: Bull sleeve (Overnight long) ───────────────────────────
            # Determine bull regime for overnight sleeve
            if self.bull_regime == "vwap":
                overnight_allowed = spy_bullish
            elif self.bull_regime == "up_from_open":
                overnight_allowed = spy_return_pct is not None and spy_return_pct > 0
            else:  # "none"
                overnight_allowed = True

            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
            if (not st["overnight_attempted"]
                    and not st["holding_overnight"]
                    and overnight_allowed
                    and bar_mins >= entry_mins):

                st["overnight_attempted"] = True
                if bar_mins <= entry_mins + 5:
                    return_pct = (price - st["day_open"]) / st["day_open"] * 100
                    if return_pct > self.overnight_min_return:
                        st["holding_overnight"] = True
                        st["overnight_entry_date"] = today
                        st["overnight_stop"] = price * (1 - self.overnight_stop_pct / 100)
                        st["position_type"] = "overnight_long"
                        signals.append(Signal(
                            symbol, Direction.LONG,
                            reason=f"allweather overnight +{return_pct:.1f}% bull session"
                        ))

        return signals
