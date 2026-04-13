"""All-Weather v5: Multi-Signal Overnight with Fear Reversion + Day-of-Week.

Extends v3/Global with three new signal dimensions for the overnight sleeve:

1. FEAR REVERSION: When UVXY (VIX proxy) is up >fear_threshold% on the day,
   add overnight longs even on bearish sessions. Rationale: after panic,
   overnight gap tends to be positive as fear mean-reverts.

2. SHARP SELLOFF REVERSION: When SPY drops >selloff_pct% intraday,
   add overnight longs on the dip-buy thesis.

3. DAY-OF-WEEK WEIGHTING: Allow more positions on Tue-Thu nights
   (documented better overnight returns) vs Mon/Fri.

These target the ~30% of nights currently blocked by VWAP+VGK filters.

Tier structure:
  Tier 1: SPY > VWAP → full allocation (3+3)
  Tier 2: VGK positive → reduced (1+1)
  Tier 3: UVXY up >fear_threshold OR SPY down >selloff_pct → fear/dip buy (1+1)
  Skip: none of the above

Bear sleeve: RS short intraday (unchanged).
REQUIRES: UVXY and VGK in symbol list. eod_flatten=False.
"""

from collections import deque
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")

SIGNAL_ONLY = {"VGK", "EFA", "EWG", "FXI", "EWJ", "UVXY", "VXX", "VIXY"}


class AllWeatherV5Strategy(Strategy):
    name = "allweather_v5"
    label = "All-Weather v5 (Multi-Signal Overnight)"

    def __init__(
        self,
        symbols: List[str],
        # Bear sleeve
        rs_threshold: float = 1.0,
        rs_stop_pct: float = 1.0,
        rs_target_pct: float = 2.0,
        spy_trend_days: int = 3,
        rs_entry_after_min: int = 15,
        rs_entry_end_hour: int = 14,
        # Overnight base
        overnight_top_k: int = 3,
        overnight_bottom_k: int = 3,
        overnight_stop_pct: float = 2.0,
        overnight_min_move: float = 0.3,
        overnight_entry_hour: int = 15,
        overnight_entry_minute: int = 30,
        overnight_exit_after_min: int = 15,
        # VGK signal (tier 2)
        global_signal_symbol: str = "VGK",
        tier2_top_k: int = 1,
        tier2_bottom_k: int = 1,
        # Fear reversion (tier 3)
        fear_symbol: str = "UVXY",
        fear_threshold: float = 3.0,      # UVXY must be up this % for fear signal
        selloff_threshold: float = 1.0,    # SPY must be down this % for selloff signal
        tier3_top_k: int = 1,
        tier3_bottom_k: int = 1,
        # Day-of-week boost
        dow_boost_days: str = "TUE,WED,THU",  # comma-separated
        dow_extra_k: int = 1,              # extra positions on boost days
    ) -> None:
        super().__init__(symbols)
        self.rs_threshold = rs_threshold
        self.rs_stop_pct = rs_stop_pct
        self.rs_target_pct = rs_target_pct
        self.spy_trend_days = spy_trend_days
        self.rs_entry_after_min = rs_entry_after_min
        self.rs_entry_end_hour = rs_entry_end_hour
        self.overnight_top_k = overnight_top_k
        self.overnight_bottom_k = overnight_bottom_k
        self.overnight_stop_pct = overnight_stop_pct
        self.overnight_min_move = overnight_min_move
        self.overnight_entry_hour = overnight_entry_hour
        self.overnight_entry_minute = overnight_entry_minute
        self.overnight_exit_after_min = overnight_exit_after_min
        self.global_signal_symbol = global_signal_symbol
        self.tier2_top_k = tier2_top_k
        self.tier2_bottom_k = tier2_bottom_k
        self.fear_symbol = fear_symbol
        self.fear_threshold = fear_threshold
        self.selloff_threshold = selloff_threshold
        self.tier3_top_k = tier3_top_k
        self.tier3_bottom_k = tier3_bottom_k
        self.dow_boost_days = set(dow_boost_days.upper().split(","))
        self.dow_extra_k = dow_extra_k
        self._state: Dict[str, dict] = {}
        self._spy_state: dict = {}
        self._signal_states: Dict[str, dict] = {}
        self._overnight_done_today = None

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None, "day_open": None,
            "rs_traded": False, "overnight_traded": False,
            "holding_overnight": False, "overnight_entry_date": None,
            "stop_level": None, "target_level": None, "position_type": None,
        }

    def _fresh_spy(self) -> dict:
        return {
            "current_date": None, "day_open": None,
            "vwap_num": 0.0, "vwap_den": 0.0, "vwap": None,
            "prev_close": None,
            "daily_closes": deque(maxlen=max(self.spy_trend_days, 1)),
        }

    def _fresh_signal(self) -> dict:
        return {"current_date": None, "day_open": None}

    def on_start(self) -> None:
        self._state = {s: self._fresh_sym() for s in self.symbols if s not in SIGNAL_ONLY}
        self._spy_state = self._fresh_spy()
        self._signal_states = {}
        self._overnight_done_today = None

    def rules(self) -> List[str]:
        return [
            "=== BEAR SLEEVE ===",
            f"RS SHORT on bearish sessions (VWAP + {self.spy_trend_days}d trend)",
            "=== BULL SLEEVE (Multi-Signal Overnight) ===",
            f"T1 (SPY>VWAP): {self.overnight_top_k}+{self.overnight_bottom_k}",
            f"T2 ({self.global_signal_symbol}>0): {self.tier2_top_k}+{self.tier2_bottom_k}",
            f"T3 ({self.fear_symbol}>+{self.fear_threshold}% OR SPY<-{self.selloff_threshold}%): {self.tier3_top_k}+{self.tier3_bottom_k}",
            f"DoW boost ({','.join(self.dow_boost_days)}): +{self.dow_extra_k} extra positions",
            f"Exit {self.overnight_exit_after_min}min after open",
        ]

    def _update_signal(self, sym: str, bar) -> Optional[float]:
        if sym not in self._signal_states:
            self._signal_states[sym] = self._fresh_signal()
        ss = self._signal_states[sym]
        et = bar.timestamp.astimezone(ET)
        today = et.date()
        if ss["current_date"] != today:
            ss["current_date"] = today
            ss["day_open"] = bar.open
        if ss["day_open"] and ss["day_open"] > 0:
            return (bar.close - ss["day_open"]) / ss["day_open"] * 100
        return None

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # ── SPY ───────────────────────────────────────────────────────────────
        spy_bar = bars.get("SPY")
        spy_return_pct: Optional[float] = None
        spy_price: Optional[float] = None
        spy_bullish_vwap = False
        spy_bearish_full = False

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
            spy["prev_close"] = spy_price
            if spy["day_open"] and spy["day_open"] > 0:
                spy_return_pct = (spy_price - spy["day_open"]) / spy["day_open"] * 100
            spy_bullish_vwap = spy["vwap"] is not None and spy_price > spy["vwap"]
            spy_bearish = spy["vwap"] is not None and spy_price < spy["vwap"]
            spy_bearish_full = spy_bearish
            if self.spy_trend_days > 0 and spy_price is not None:
                closes = spy["daily_closes"]
                if len(closes) >= self.spy_trend_days:
                    spy_bearish_full = spy_bearish_full and spy_price < closes[0]

        # ── Signal ETFs ───────────────────────────────────────────────────────
        global_return = None
        fear_return = None
        if self.global_signal_symbol in bars:
            global_return = self._update_signal(self.global_signal_symbol, bars[self.global_signal_symbol])
        if self.fear_symbol in bars:
            fear_return = self._update_signal(self.fear_symbol, bars[self.fear_symbol])

        # ── Per-symbol ────────────────────────────────────────────────────────
        stock_rs: List[Tuple[str, float, float]] = []
        tradable = [s for s in self.symbols if s not in SIGNAL_ONLY and s != "SPY"]

        for symbol in tradable:
            bar = bars.get(symbol)
            if bar is None:
                continue
            et = bar.timestamp.astimezone(ET)
            today = et.date()
            if symbol not in self._state:
                self._state[symbol] = self._fresh_sym()
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

            # Exit overnight
            if st["holding_overnight"] and st["overnight_entry_date"] != today:
                if st["stop_level"] is not None and current_qty > 0 and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw5 stop"))
                    st["holding_overnight"] = False; st["position_type"] = None; continue
                if bar_mins >= open_mins + self.overnight_exit_after_min:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw5 exit"))
                    st["holding_overnight"] = False; st["position_type"] = None
                continue

            # Manage RS short
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw5 RS stop"))
                    st["position_type"] = None
                elif st["target_level"] and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw5 RS target"))
                    st["position_type"] = None
                elif et.hour == 15 and et.minute >= 25:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw5 RS close"))
                    st["position_type"] = None
                continue

            if current_qty > 0 and st["holding_overnight"] and st["overnight_entry_date"] == today:
                if st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw5 stop (day)"))
                    st["holding_overnight"] = False; st["position_type"] = None
                continue

            if current_qty != 0:
                continue
            if not st["day_open"] or st["day_open"] == 0:
                continue

            # Bear sleeve
            if (not st["rs_traded"] and spy_bearish_full and spy_return_pct is not None
                    and bar_mins >= open_mins + self.rs_entry_after_min
                    and et.hour < self.rs_entry_end_hour):
                stock_ret = (price - st["day_open"]) / st["day_open"] * 100
                rs = stock_ret - spy_return_pct
                if rs < -self.rs_threshold:
                    st["rs_traded"] = True
                    st["stop_level"] = price * (1 + self.rs_stop_pct / 100)
                    st["target_level"] = price * (1 - self.rs_target_pct / 100) if self.rs_target_pct > 0 else None
                    st["position_type"] = "rs_short"
                    signals.append(Signal(symbol, Direction.SHORT, reason=f"aw5 RS={rs:.1f}%"))
                continue

            # Collect overnight
            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
            if (bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                    and not st["overnight_traded"] and spy_return_pct is not None):
                stock_ret = (price - st["day_open"]) / st["day_open"] * 100
                rs = stock_ret - spy_return_pct
                stock_rs.append((symbol, rs, price))

        # ── MULTI-SIGNAL OVERNIGHT ENTRY ──────────────────────────────────────
        sample = bars.get("SPY") or next((bars[s] for s in self.symbols if s in bars), None)
        if not sample:
            return signals
        et = sample.timestamp.astimezone(ET)
        today = et.date()
        bar_mins = et.hour * 60 + et.minute
        entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute

        if (stock_rs and bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                and self._overnight_done_today != today):

            self._overnight_done_today = today

            # Determine tier
            global_bullish = global_return is not None and global_return > 0
            fear_spike = fear_return is not None and fear_return > self.fear_threshold
            spy_selloff = spy_return_pct is not None and spy_return_pct < -self.selloff_threshold

            if spy_bullish_vwap:
                top_k, bot_k, tier = self.overnight_top_k, self.overnight_bottom_k, 1
            elif global_bullish:
                top_k, bot_k, tier = self.tier2_top_k, self.tier2_bottom_k, 2
            elif fear_spike or spy_selloff:
                top_k, bot_k, tier = self.tier3_top_k, self.tier3_bottom_k, 3
            else:
                top_k, bot_k, tier = 0, 0, 0

            # Day-of-week boost
            day_name = today.strftime("%a").upper()[:3]
            if day_name in self.dow_boost_days and tier > 0:
                top_k += self.dow_extra_k
                bot_k += self.dow_extra_k

            if top_k > 0 or bot_k > 0:
                stock_rs.sort(key=lambda x: x[1], reverse=True)

                # Winners
                for sym, rs, px in stock_rs:
                    if top_k <= 0: break
                    if rs < self.overnight_min_move: continue
                    st = self._state.get(sym)
                    if not st or st["overnight_traded"] or st["holding_overnight"]: continue
                    pos = portfolio.get_position(sym)
                    if pos and pos.quantity != 0: continue
                    st["overnight_traded"] = True
                    st["holding_overnight"] = True
                    st["overnight_entry_date"] = today
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"on_t{tier}"
                    signals.append(Signal(sym, Direction.LONG, reason=f"aw5 T{tier} +{rs:.1f}%"))
                    top_k -= 1

                # Losers (dip buys)
                losers = sorted([x for x in stock_rs if x[1] < -self.overnight_min_move], key=lambda x: x[1])
                for sym, rs, px in losers:
                    if bot_k <= 0: break
                    st = self._state.get(sym)
                    if not st or st["overnight_traded"] or st["holding_overnight"]: continue
                    pos = portfolio.get_position(sym)
                    if pos and pos.quantity != 0: continue
                    st["overnight_traded"] = True
                    st["holding_overnight"] = True
                    st["overnight_entry_date"] = today
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"on_t{tier}"
                    signals.append(Signal(sym, Direction.LONG, reason=f"aw5 T{tier} dip {rs:.1f}%"))
                    bot_k -= 1

        return signals
