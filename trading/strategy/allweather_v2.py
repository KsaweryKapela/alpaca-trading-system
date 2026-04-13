"""All-Weather v2: RS Short Intraday + Adaptive Overnight Long.

Key change from v1: The bull sleeve uses a MULTI-DAY trend signal
instead of (or in addition to) the intraday VWAP filter.

The v1 VWAP filter blocks ~35-40% of 2025 sessions even though
the multi-week trend is bullish. V2 uses:
  - SPY above its N-day SMA → bullish multi-day trend → overnight long allowed
  - SPY below its N-day SMA → bearish trend → overnight blocked

In 2025 (bull), SPY was above its 20-SMA ~80% of the time vs ~60% for VWAP.
This should increase overnight coverage from ~55% to ~80% of sessions.

Additionally, v2 selects stocks for overnight by RELATIVE STRENGTH:
  - Rank stocks by return from open at 15:30
  - Buy top K strongest stocks on the session (RS > 0 vs SPY)
  - These are stocks with institutional buying that day → likely positive overnight gap

Bear sleeve unchanged: RS short with VWAP + 3-day trend filter.

REQUIRES: eod_flatten=False
"""

from collections import deque
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class AllWeatherV2Strategy(Strategy):
    name = "allweather_v2"
    label = "All-Weather v2 (SMA trend + RS selection)"

    def __init__(
        self,
        symbols: List[str],
        # Bear sleeve: RS short
        rs_threshold: float = 1.0,
        rs_stop_pct: float = 1.0,
        rs_target_pct: float = 2.0,
        spy_trend_days: int = 3,
        rs_entry_after_min: int = 15,
        rs_entry_end_hour: int = 14,
        # Bull sleeve: Overnight long
        sma_period: int = 10,            # SPY SMA period for bull trend (10 = ~2 weeks)
        overnight_top_k: int = 5,        # buy top K RS stocks each night
        overnight_min_rs: float = 0.0,   # minimum RS vs SPY to qualify (0 = any outperformer)
        overnight_stop_pct: float = 2.0,
        overnight_exit_after_min: int = 5,
        overnight_entry_hour: int = 15,
        overnight_entry_minute: int = 30,
        # Use intraday VWAP as secondary filter?
        require_vwap_bull: bool = False,
    ) -> None:
        super().__init__(symbols)
        # Bear
        self.rs_threshold = rs_threshold
        self.rs_stop_pct = rs_stop_pct
        self.rs_target_pct = rs_target_pct
        self.spy_trend_days = spy_trend_days
        self.rs_entry_after_min = rs_entry_after_min
        self.rs_entry_end_hour = rs_entry_end_hour
        # Bull
        self.sma_period = sma_period
        self.overnight_top_k = overnight_top_k
        self.overnight_min_rs = overnight_min_rs
        self.overnight_stop_pct = overnight_stop_pct
        self.overnight_exit_after_min = overnight_exit_after_min
        self.overnight_entry_hour = overnight_entry_hour
        self.overnight_entry_minute = overnight_entry_minute
        self.require_vwap_bull = require_vwap_bull
        # State
        self._state: Dict[str, dict] = {}
        self._spy_state: dict = {}
        self._overnight_done_today = None

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "rs_traded": False,
            "overnight_traded": False,
            "holding_overnight": False,
            "overnight_entry_date": None,
            "stop_level": None,
            "target_level": None,
            "position_type": None,
        }

    def _fresh_spy(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "vwap_num": 0.0,
            "vwap_den": 0.0,
            "vwap": None,
            "prev_close": None,
            "daily_closes": deque(maxlen=max(self.spy_trend_days, self.sma_period, 1)),
        }

    def on_start(self) -> None:
        self._state = {sym: self._fresh_sym() for sym in self.symbols}
        self._spy_state = self._fresh_spy()
        self._overnight_done_today = None

    def rules(self) -> List[str]:
        return [
            "=== BEAR SLEEVE (RS Short, Intraday) ===",
            f"SPY below VWAP + SPY < close {self.spy_trend_days} days ago → RS SHORT",
            f"RS < -{self.rs_threshold}% vs SPY | Stop {self.rs_stop_pct}% | TP {self.rs_target_pct}%",
            "=== BULL SLEEVE (Overnight Long, SMA trend) ===",
            f"SPY above {self.sma_period}-day SMA → overnight long allowed",
            f"At {self.overnight_entry_hour}:{self.overnight_entry_minute:02d}: rank stocks by session RS",
            f"Buy top {self.overnight_top_k} with RS > {self.overnight_min_rs}%",
            f"Hold overnight, exit {self.overnight_exit_after_min} min after next open",
            f"Stop: {self.overnight_stop_pct}%",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # ── SPY state ──────────────────────────────────────────────────────────
        spy_bar = bars.get("SPY")
        spy_return_pct: Optional[float] = None
        spy_price: Optional[float] = None
        spy_vwap: Optional[float] = None
        spy_bullish_vwap = False
        spy_bearish_full = False
        spy_above_sma = False

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

            spy_bullish_vwap = spy_vwap is not None and spy_price > spy_vwap
            spy_bearish = spy_vwap is not None and spy_price < spy_vwap

            # Bear check: VWAP + N-day trend
            spy_bearish_full = spy_bearish
            if self.spy_trend_days > 0 and spy_price is not None:
                closes = spy["daily_closes"]
                if len(closes) >= self.spy_trend_days:
                    spy_bearish_full = spy_bearish_full and spy_price < closes[0]

            # Bull SMA check: SPY above N-day SMA
            if len(spy["daily_closes"]) >= self.sma_period:
                recent = list(spy["daily_closes"])[-self.sma_period:]
                sma = sum(recent) / len(recent)
                spy_above_sma = spy_price > sma

        # ── Collect RS rankings for overnight entry ───────────────────────────
        stock_rs: List[Tuple[str, float, float]] = []  # (symbol, rs, price)

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
                    st["rs_traded"] = False
                    st["overnight_traded"] = False
                st["current_date"] = today
                st["day_open"] = bar.open

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0
            bar_mins = et.hour * 60 + et.minute
            open_mins = 9 * 60 + 30

            # ── EXIT: Overnight from previous day ─────────────────────────────
            if st["holding_overnight"] and st["overnight_entry_date"] != today:
                if st["stop_level"] is not None and current_qty > 0 and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw2 overnight stop"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                    continue
                if bar_mins >= open_mins + self.overnight_exit_after_min:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw2 overnight exit"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            # ── MANAGE: RS short ──────────────────────────────────────────────
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["stop_level"] is not None and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw2 RS stop"))
                    st["position_type"] = None
                elif st["target_level"] is not None and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw2 RS target"))
                    st["position_type"] = None
                elif et.hour == 15 and et.minute >= 25:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw2 RS pre-close"))
                    st["position_type"] = None
                continue

            # ── MANAGE: Overnight long on entry day ───────────────────────────
            if current_qty > 0 and st["holding_overnight"] and st["overnight_entry_date"] == today:
                if st["stop_level"] is not None and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw2 overnight stop (day)"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            if current_qty != 0:
                continue

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
                    st["stop_level"] = price * (1 + self.rs_stop_pct / 100)
                    st["target_level"] = (price * (1 - self.rs_target_pct / 100)
                                          if self.rs_target_pct > 0 else None)
                    st["position_type"] = "rs_short"
                    signals.append(Signal(symbol, Direction.SHORT,
                                          reason=f"aw2 RS={rs:.1f}% bear"))
                continue

            # ── COLLECT: Overnight candidates ─────────────────────────────────
            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
            if (bar_mins >= entry_mins
                    and bar_mins <= entry_mins + 5
                    and not st["overnight_traded"]
                    and spy_return_pct is not None):
                stock_return = (price - st["day_open"]) / st["day_open"] * 100
                rs = stock_return - spy_return_pct
                stock_rs.append((symbol, rs, price))

        # ── RANK & ENTER: Overnight top-K ─────────────────────────────────────
        sample_bar = bars.get("SPY") or next((bars[s] for s in self.symbols if s in bars), None)
        if sample_bar is None:
            return signals

        et = sample_bar.timestamp.astimezone(ET)
        today = et.date()
        bar_mins = et.hour * 60 + et.minute
        entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute

        if (stock_rs
                and bar_mins >= entry_mins
                and bar_mins <= entry_mins + 5
                and self._overnight_done_today != today):

            # Check bull regime
            bull_ok = spy_above_sma
            if self.require_vwap_bull:
                bull_ok = bull_ok and spy_bullish_vwap

            if bull_ok:
                self._overnight_done_today = today

                # Rank by RS, pick top K with RS > min_rs
                stock_rs.sort(key=lambda x: x[1], reverse=True)
                entered = 0
                for sym, rs, px in stock_rs:
                    if entered >= self.overnight_top_k:
                        break
                    if rs < self.overnight_min_rs:
                        continue
                    st = self._state[sym]
                    if st["overnight_traded"] or st["holding_overnight"]:
                        continue
                    # Check no existing position
                    pos = portfolio.get_position(sym)
                    if pos and pos.quantity != 0:
                        continue

                    st["overnight_traded"] = True
                    st["holding_overnight"] = True
                    st["overnight_entry_date"] = today
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = "overnight_long"
                    signals.append(Signal(sym, Direction.LONG,
                                          reason=f"aw2 overnight RS={rs:.1f}% top-{self.overnight_top_k}"))
                    entered += 1
            else:
                self._overnight_done_today = today

        return signals
