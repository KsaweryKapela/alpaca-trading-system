"""Dynamic Stock Selection Strategy.

FUNDAMENTALLY NEW ARCHITECTURE: Instead of running the same tactic on a fixed
universe, this strategy SELECTS which stocks to trade each day based on
real-time characteristics, then executes tactics only on selected stocks.

STOCK SELECTION (computed at 10:00 ET from first 30 min):
  1. RELATIVE VOLUME (RVOL): today's first-30-min volume vs 20-day average
     - High RVOL = institutional interest, stock is "in play"
     - Low RVOL = quiet, no edge
  2. RANGE EXPANSION: today's first-30-min range vs 20-day average range
     - Wide range = catalyst-driven move, directional opportunity
     - Narrow range = noise, avoid
  3. GAP SIZE: overnight gap from prior close
     - Large gap = catalyst/news event
     - Stocks with catalysts have more predictable follow-through
  4. MULTI-DAY MOMENTUM: 5-day price change direction
     - Stocks trending with the market have better continuation

SCORING: tradability = RVOL_score + range_score + gap_score + momentum_score
Only trade the top-N stocks by tradability each day.

TACTICS (applied to selected stocks only):
  BEAR REGIME (SPY < VWAP + trend): RS shorts on selected stocks
  BULL REGIME (SPY > VWAP): Overnight longs on selected stocks

This means on quiet days with few "in play" stocks, we trade less (capital
preservation). On active days, we concentrate on the highest-opportunity names.

MARGIN OVERLAY: Inherited from v10.
REQUIRES: eod_flatten=False.
"""

from collections import deque
from typing import Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")

SIGNAL_ONLY = {"VGK", "EFA", "EWG", "FXI", "EWJ", "UVXY", "VXX", "VIXY", "XLK", "XLF", "SMH"}


class DynamicSelectStrategy(Strategy):
    name = "dynamic_select"
    label = "Dynamic Stock Selection + Tactics"

    def __init__(
        self,
        symbols: List[str],
        # Stock selection params
        selection_after_min: int = 30,    # compute selection 30 min after open
        min_rvol: float = 1.0,            # minimum RVOL to be "in play" (1.0 = average)
        max_selected: int = 10,           # max stocks to trade per day
        rvol_lookback: int = 20,          # days for RVOL baseline
        # Bear sleeve: RS shorts on selected stocks
        rs_threshold: float = 1.0,
        rs_stop_pct: float = 3.0,
        rs_target_pct: float = 3.0,
        spy_trend_days: int = 3,
        rs_entry_after_min: int = 30,     # entry starts after selection time
        rs_entry_end_hour: int = 14,
        rs_close_hour: int = 15,
        rs_close_minute: int = 35,
        # Bull sleeve: overnight longs on selected stocks
        overnight_top_k: int = 4,
        overnight_bottom_k: int = 4,
        overnight_stop_pct: float = 2.0,
        overnight_min_move: float = 0.3,
        overnight_entry_hour: int = 15,
        overnight_entry_minute: int = 30,
        overnight_exit_after_min: int = 20,
        # Global signal
        global_signal_symbol: str = "VGK",
        global_min_return: float = 0.0,
        tier2_top_k: int = 2,
        tier2_bottom_k: int = 2,
    ) -> None:
        super().__init__(symbols)
        self.selection_after_min = selection_after_min
        self.min_rvol = min_rvol
        self.max_selected = max_selected
        self.rvol_lookback = rvol_lookback
        self.rs_threshold = rs_threshold
        self.rs_stop_pct = rs_stop_pct
        self.rs_target_pct = rs_target_pct
        self.spy_trend_days = spy_trend_days
        self.rs_entry_after_min = rs_entry_after_min
        self.rs_entry_end_hour = rs_entry_end_hour
        self.rs_close_hour = rs_close_hour
        self.rs_close_minute = rs_close_minute
        self.overnight_top_k = overnight_top_k
        self.overnight_bottom_k = overnight_bottom_k
        self.overnight_stop_pct = overnight_stop_pct
        self.overnight_min_move = overnight_min_move
        self.overnight_entry_hour = overnight_entry_hour
        self.overnight_entry_minute = overnight_entry_minute
        self.overnight_exit_after_min = overnight_exit_after_min
        self.global_signal_symbol = global_signal_symbol
        self.global_min_return = global_min_return
        self.tier2_top_k = tier2_top_k
        self.tier2_bottom_k = tier2_bottom_k

        self._spy: dict = {}
        self._sym: Dict[str, dict] = {}
        self._signal_states: Dict[str, dict] = {}
        self._overnight_done_today = None
        self._selected_today: Set[str] = set()
        self._selection_done_today = None

    def on_start(self) -> None:
        self._spy = {
            "current_date": None, "day_open": None,
            "vwap_num": 0.0, "vwap_den": 0.0, "vwap": None,
            "prev_close": None,
            "daily_closes": deque(maxlen=max(self.spy_trend_days, 1) + 1),
        }
        self._sym = {}
        self._signal_states = {}
        self._overnight_done_today = None
        self._selected_today = set()
        self._selection_done_today = None

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None, "day_open": None,
            "prev_close": None,
            "rs_traded": False, "overnight_traded": False,
            "holding_overnight": False, "overnight_entry_date": None,
            "stop_level": None, "target_level": None, "position_type": None,
            # Volume tracking for RVOL
            "session_volume": 0.0,          # accumulated volume today
            "first_30min_volumes": deque(maxlen=self.rvol_lookback),  # historical first-30-min volumes
            # Range tracking
            "session_high": None,
            "session_low": None,
            "first_30min_ranges": deque(maxlen=self.rvol_lookback),  # historical first-30-min ranges
            # Multi-day momentum
            "daily_closes_5d": deque(maxlen=6),  # for 5-day momentum
        }

    def _fresh_signal(self) -> dict:
        return {"current_date": None, "day_open": None}

    def rules(self) -> List[str]:
        return [
            "=== STOCK SELECTION (10:00 ET) ===",
            f"Score by: RVOL + range expansion + gap + momentum",
            f"Min RVOL: {self.min_rvol}x | Max selected: {self.max_selected}/day",
            "=== BEAR SLEEVE (RS Short on selected) ===",
            f"RS < -{self.rs_threshold}% | Stop {self.rs_stop_pct}% | Target {self.rs_target_pct}%",
            "=== BULL SLEEVE (Overnight on selected) ===",
            f"T1: {self.overnight_top_k}+{self.overnight_bottom_k} | T2: {self.tier2_top_k}+{self.tier2_bottom_k}",
            f"Exit {self.overnight_exit_after_min}min | {self.global_signal_symbol} signal",
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

        spy_bar = bars.get("SPY")
        if spy_bar is None:
            return signals

        et_spy = spy_bar.timestamp.astimezone(ET)
        spy_today = et_spy.date()
        spy = self._spy

        if spy["current_date"] != spy_today:
            if spy["prev_close"] is not None:
                spy["daily_closes"].append(spy["prev_close"])
            spy["current_date"] = spy_today
            spy["day_open"] = spy_bar.open
            spy["vwap_num"] = 0.0
            spy["vwap_den"] = 0.0
            spy["vwap"] = None
            self._selected_today = set()
            self._selection_done_today = None
            self._overnight_done_today = None

        typical = (spy_bar.high + spy_bar.low + spy_bar.close) / 3
        spy["vwap_num"] += typical * spy_bar.volume
        spy["vwap_den"] += spy_bar.volume
        if spy["vwap_den"] > 0:
            spy["vwap"] = spy["vwap_num"] / spy["vwap_den"]

        spy_price = spy_bar.close
        spy["prev_close"] = spy_price

        spy_return_pct = None
        if spy["day_open"] and spy["day_open"] > 0:
            spy_return_pct = (spy_price - spy["day_open"]) / spy["day_open"] * 100

        spy_bullish_vwap = spy["vwap"] is not None and spy_price > spy["vwap"]
        spy_bearish = spy["vwap"] is not None and spy_price < spy["vwap"]
        spy_bearish_full = spy_bearish
        if self.spy_trend_days > 0:
            closes = list(spy["daily_closes"])
            if len(closes) >= self.spy_trend_days:
                spy_bearish_full = spy_bearish and spy_price < closes[-self.spy_trend_days]

        bar_mins = et_spy.hour * 60 + et_spy.minute
        open_mins = 9 * 60 + 30

        # Global signal
        global_return = None
        if self.global_signal_symbol in bars:
            global_return = self._update_signal(self.global_signal_symbol, bars[self.global_signal_symbol])

        # ── Per-symbol: update tracking + manage positions ───────────────
        tradable = [s for s in self.symbols if s not in SIGNAL_ONLY and s != "SPY"]
        stock_scores: List[Tuple[str, float]] = []
        stock_rs_overnight: List[Tuple[str, float, float]] = []

        for symbol in tradable:
            bar = bars.get(symbol)
            if bar is None:
                continue

            et = bar.timestamp.astimezone(ET)
            today = et.date()

            if symbol not in self._sym:
                self._sym[symbol] = self._fresh_sym()
            st = self._sym[symbol]

            if st["current_date"] != today:
                # Save previous day's first-30-min stats
                if st["session_volume"] > 0 and st["current_date"] is not None:
                    st["first_30min_volumes"].append(st.get("_first_30_vol", 0))
                    st["first_30min_ranges"].append(st.get("_first_30_range", 0))
                if st["prev_close"] is not None:
                    st["daily_closes_5d"].append(st["prev_close"])

                if not st["holding_overnight"]:
                    st["rs_traded"] = False
                    st["overnight_traded"] = False
                st["current_date"] = today
                st["day_open"] = bar.open
                st["session_volume"] = 0.0
                st["session_high"] = bar.high
                st["session_low"] = bar.low
                st["_first_30_vol"] = 0
                st["_first_30_range"] = 0

            price = bar.close
            st["session_volume"] += bar.volume
            if bar.high > (st["session_high"] or 0):
                st["session_high"] = bar.high
            if st["session_low"] is None or bar.low < st["session_low"]:
                st["session_low"] = bar.low
            st["prev_close"] = price

            sym_bar_mins = et.hour * 60 + et.minute

            # Track first-30-min stats
            if sym_bar_mins <= open_mins + 30:
                st["_first_30_vol"] = st["session_volume"]
                if st["session_high"] and st["session_low"] and st["session_low"] > 0:
                    st["_first_30_range"] = (st["session_high"] - st["session_low"]) / st["session_low"] * 100

            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # ── Exit overnight longs ─────────────────────────────────────
            if st["holding_overnight"] and st["overnight_entry_date"] != today:
                if st["stop_level"] is not None and current_qty > 0 and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="ds stop"))
                    st["holding_overnight"] = False; st["position_type"] = None; continue
                if sym_bar_mins >= open_mins + self.overnight_exit_after_min:
                    signals.append(Signal(symbol, Direction.FLAT, reason="ds exit"))
                    st["holding_overnight"] = False; st["position_type"] = None
                continue

            # ── Manage RS short ──────────────────────────────────────────
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="ds RS stop"))
                    st["position_type"] = None
                elif st["target_level"] and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="ds RS target"))
                    st["position_type"] = None
                elif (et.hour > self.rs_close_hour or
                      (et.hour == self.rs_close_hour and et.minute >= self.rs_close_minute)):
                    signals.append(Signal(symbol, Direction.FLAT, reason="ds RS close"))
                    st["position_type"] = None
                continue

            if current_qty > 0 and st["holding_overnight"] and st["overnight_entry_date"] == today:
                if st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="ds stop (day)"))
                    st["holding_overnight"] = False; st["position_type"] = None
                continue

            if current_qty != 0:
                continue

            # ── STOCK SELECTION at selection_after_min ────────────────────
            if (self._selection_done_today != today
                    and sym_bar_mins >= open_mins + self.selection_after_min
                    and sym_bar_mins < open_mins + self.selection_after_min + 5):

                # Compute tradability score
                score = 0.0

                # 1. RVOL
                avg_vol = sum(st["first_30min_volumes"]) / len(st["first_30min_volumes"]) if st["first_30min_volumes"] else 0
                if avg_vol > 0:
                    rvol = st["_first_30_vol"] / avg_vol
                    if rvol >= self.min_rvol:
                        score += min(rvol, 5.0)  # cap at 5x to avoid outlier domination

                # 2. Range expansion
                avg_range = sum(st["first_30min_ranges"]) / len(st["first_30min_ranges"]) if st["first_30min_ranges"] else 0
                if avg_range > 0 and st["_first_30_range"] > 0:
                    range_ratio = st["_first_30_range"] / avg_range
                    score += min(range_ratio, 3.0)

                # 3. Gap size (absolute)
                if st["day_open"] and st["day_open"] > 0 and len(st["daily_closes_5d"]) > 0:
                    prev_c = st["daily_closes_5d"][-1]
                    if prev_c > 0:
                        gap_pct = abs(st["day_open"] - prev_c) / prev_c * 100
                        score += min(gap_pct, 3.0)

                # 4. Multi-day momentum magnitude
                if len(st["daily_closes_5d"]) >= 5:
                    mom_5d = abs(st["daily_closes_5d"][-1] - st["daily_closes_5d"][0]) / st["daily_closes_5d"][0] * 100
                    score += min(mom_5d / 2, 2.0)  # normalize

                if score > 0:
                    stock_scores.append((symbol, score))

            # ── RS SHORT entry (only on selected stocks) ─────────────────
            if (symbol in self._selected_today
                    and not st["rs_traded"] and spy_bearish_full
                    and sym_bar_mins >= open_mins + self.rs_entry_after_min
                    and et.hour < self.rs_entry_end_hour
                    and spy_return_pct is not None
                    and st["day_open"] and st["day_open"] > 0):
                stock_ret = (price - st["day_open"]) / st["day_open"] * 100
                rs = stock_ret - spy_return_pct
                if rs < -self.rs_threshold:
                    st["rs_traded"] = True
                    st["stop_level"] = price * (1 + self.rs_stop_pct / 100)
                    st["target_level"] = price * (1 - self.rs_target_pct / 100) if self.rs_target_pct > 0 else None
                    st["position_type"] = "rs_short"
                    signals.append(Signal(symbol, Direction.SHORT, reason=f"ds RS={rs:.1f}%"))
                continue

            # ── Collect overnight candidates (only selected stocks) ──────
            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
            if (symbol in self._selected_today
                    and sym_bar_mins >= entry_mins and sym_bar_mins <= entry_mins + 5
                    and not st["overnight_traded"] and spy_return_pct is not None
                    and st["day_open"] and st["day_open"] > 0):
                stock_ret = (price - st["day_open"]) / st["day_open"] * 100
                rs = stock_ret - spy_return_pct
                stock_rs_overnight.append((symbol, rs, price))

        # ── PERFORM STOCK SELECTION ──────────────────────────────────────
        if (stock_scores and self._selection_done_today != spy_today
                and bar_mins >= open_mins + self.selection_after_min
                and bar_mins < open_mins + self.selection_after_min + 5):
            self._selection_done_today = spy_today
            stock_scores.sort(key=lambda x: x[1], reverse=True)
            self._selected_today = {s for s, _ in stock_scores[:self.max_selected]}

        # ── OVERNIGHT ENTRY ──────────────────────────────────────────────
        entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
        if (stock_rs_overnight and bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                and self._overnight_done_today != spy_today):

            self._overnight_done_today = spy_today
            global_bullish = global_return is not None and global_return > self.global_min_return

            if spy_bullish_vwap:
                top_k, bot_k, tier = self.overnight_top_k, self.overnight_bottom_k, 1
            elif global_bullish:
                top_k, bot_k, tier = self.tier2_top_k, self.tier2_bottom_k, 2
            else:
                top_k, bot_k, tier = 0, 0, 0

            if top_k > 0 or bot_k > 0:
                stock_rs_overnight.sort(key=lambda x: x[1], reverse=True)

                for sym, rs, px in stock_rs_overnight:
                    if top_k <= 0: break
                    if rs < self.overnight_min_move: continue
                    st = self._sym.get(sym)
                    if not st or st["overnight_traded"] or st["holding_overnight"]: continue
                    pos = portfolio.get_position(sym)
                    if pos and pos.quantity != 0: continue
                    st["overnight_traded"] = True
                    st["holding_overnight"] = True
                    st["overnight_entry_date"] = spy_today
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"on_t{tier}"
                    signals.append(Signal(sym, Direction.LONG, reason=f"ds T{tier} +{rs:.1f}%"))
                    top_k -= 1

                losers = sorted([x for x in stock_rs_overnight if x[1] < -self.overnight_min_move], key=lambda x: x[1])
                for sym, rs, px in losers:
                    if bot_k <= 0: break
                    st = self._sym.get(sym)
                    if not st or st["overnight_traded"] or st["holding_overnight"]: continue
                    pos = portfolio.get_position(sym)
                    if pos and pos.quantity != 0: continue
                    st["overnight_traded"] = True
                    st["holding_overnight"] = True
                    st["overnight_entry_date"] = spy_today
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"on_t{tier}"
                    signals.append(Signal(sym, Direction.LONG, reason=f"ds T{tier} dip {rs:.1f}%"))
                    bot_k -= 1

        return signals
