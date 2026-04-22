"""Modular Strategy: Selector + Executor Architecture.

This strategy separates stock SELECTION from trade EXECUTION.
The selector ranks stocks each day. The executor trades only selected stocks.

ARCHITECTURE:
  Selector (pluggable):
    - CompositeSelector: multi-factor scoring (RVOL, range, momentum, gap, RS)
    - MomentumSelector: pure momentum ranking
    - (future: ML-based, sector-relative, etc.)

  Executor (built-in, based on proven v10 logic):
    - Bear: RS shorts on selected weak stocks (margin overlay)
    - Bull: Overnight longs on selected strong stocks (20-min exit)

  The selector updates on every bar. At key times:
    - 10:00 ET: selection computed, stocks ranked
    - 10:00-14:00: RS shorts on bear-biased selected stocks
    - 15:30: overnight longs on bull-biased selected stocks
    - 15:35: RS shorts close (margin overlay)
    - Next 9:50: overnight exits

EXPERIMENT TRACKING:
  The selection is logged in each trade's reason field, so we can
  analyze which selected stocks performed best.
"""

from typing import Dict, List, Optional, Tuple
from collections import deque
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio
from ..selection.base import Selector, ScoredStock
from ..selection.composite import CompositeSelector

ET = ZoneInfo("America/New_York")

SIGNAL_ONLY = {"VGK", "EFA", "EWG", "FXI", "EWJ", "UVXY", "VXX", "VIXY",
               "XLK", "XLF", "SMH", "IWM", "TQQQ"}


class ModularStrategy(Strategy):
    name = "modular"
    label = "Modular (Selector + Executor)"

    def __init__(
        self,
        symbols: List[str],
        # Selector config
        selector_type: str = "composite",
        select_top_n: int = 12,
        select_after_min: int = 30,
        # Bear executor
        rs_threshold: float = 1.0,
        rs_stop_pct: float = 3.0,
        rs_target_pct: float = 3.0,
        spy_trend_days: int = 3,
        rs_entry_after_min: int = 30,
        rs_entry_end_hour: int = 14,
        rs_close_hour: int = 15,
        rs_close_minute: int = 35,
        # Bull executor (overnight)
        overnight_top_k: int = 4,
        overnight_bottom_k: int = 4,
        overnight_stop_pct: float = 2.0,
        overnight_min_move: float = 0.3,
        overnight_entry_hour: int = 15,
        overnight_entry_minute: int = 30,
        overnight_exit_after_min: int = 20,
        # Global signal
        global_signal_symbol: str = "VGK",
    ) -> None:
        super().__init__(symbols)
        self.select_top_n = select_top_n
        self.select_after_min = select_after_min
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

        # Build selector
        tradable = [s for s in symbols if s not in SIGNAL_ONLY and s != "SPY"]
        if selector_type == "composite":
            self._selector = CompositeSelector(tradable)
        elif selector_type == "adaptive":
            from ..selection.adaptive import AdaptiveSelector
            self._selector = AdaptiveSelector(tradable)
        elif selector_type == "abnormality":
            from ..selection.abnormality import AbnormalitySelector
            self._selector = AbnormalitySelector(tradable)
        else:
            from ..selection.momentum import MomentumSelector
            self._selector = MomentumSelector(tradable)

        self._spy: dict = {}
        self._sym: Dict[str, dict] = {}
        self._signal_states: Dict[str, dict] = {}
        self._selected: List[ScoredStock] = []
        self._selected_syms: set = set()
        self._selection_done_today = None
        self._overnight_done_today = None

    def on_start(self) -> None:
        self._spy = {
            "current_date": None, "day_open": None,
            "vwap_num": 0.0, "vwap_den": 0.0, "vwap": None,
            "prev_close": None,
            "daily_closes": deque(maxlen=max(self.spy_trend_days, 1) + 1),
        }
        self._sym = {}
        self._signal_states = {}
        self._selected = []
        self._selected_syms = set()
        self._selection_done_today = None
        self._overnight_done_today = None

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None, "day_open": None,
            "rs_traded": False, "overnight_traded": False,
            "holding_overnight": False, "overnight_entry_date": None,
            "stop_level": None, "target_level": None, "position_type": None,
        }

    def _fresh_signal(self) -> dict:
        return {"current_date": None, "day_open": None}

    def rules(self) -> List[str]:
        return [
            f"=== SELECTOR: top {self.select_top_n} by composite score ===",
            f"Factors: RVOL + range + momentum + gap + RS",
            f"Selection at 9:30+{self.select_after_min}min",
            f"=== BEAR EXECUTOR: RS shorts on short-biased selected ===",
            f"RS < -{self.rs_threshold}% | Stop {self.rs_stop_pct}% | Target {self.rs_target_pct}%",
            f"=== BULL EXECUTOR: overnight longs on long-biased selected ===",
            f"{self.overnight_top_k}+{self.overnight_bottom_k} | Exit {self.overnight_exit_after_min}min",
        ]

    def _update_signal(self, sym, bar):
        if sym not in self._signal_states:
            self._signal_states[sym] = self._fresh_signal()
        ss = self._signal_states[sym]
        et = bar.timestamp.astimezone(ET)
        today = et.date()
        if ss["current_date"] != today:
            ss["current_date"] = today; ss["day_open"] = bar.open
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
            spy["vwap_num"] = 0.0; spy["vwap_den"] = 0.0; spy["vwap"] = None
            self._selection_done_today = None
            self._overnight_done_today = None

        typical = (spy_bar.high + spy_bar.low + spy_bar.close) / 3
        spy["vwap_num"] += typical * spy_bar.volume
        spy["vwap_den"] += spy_bar.volume
        if spy["vwap_den"] > 0:
            spy["vwap"] = spy["vwap_num"] / spy["vwap_den"]
        spy_price = spy_bar.close
        spy["prev_close"] = spy_price

        spy_return_pct = ((spy_price - spy["day_open"]) / spy["day_open"] * 100
                          if spy["day_open"] and spy["day_open"] > 0 else None)
        spy_bullish = spy["vwap"] is not None and spy_price > spy["vwap"]
        spy_bearish = spy["vwap"] is not None and spy_price < spy["vwap"]
        spy_bearish_full = spy_bearish
        if self.spy_trend_days > 0:
            closes = list(spy["daily_closes"])
            if len(closes) >= self.spy_trend_days:
                spy_bearish_full = spy_bearish and spy_price < closes[-self.spy_trend_days]

        bar_mins = et_spy.hour * 60 + et_spy.minute
        open_mins = 9 * 60 + 30

        # ── UPDATE SELECTOR ──────────────────────────────────────────────
        self._selector.update(bars, spy_today)

        # ── PERFORM SELECTION ────────────────────────────────────────────
        if (self._selection_done_today != spy_today
                and bar_mins >= open_mins + self.select_after_min
                and bar_mins < open_mins + self.select_after_min + 5):
            self._selection_done_today = spy_today
            self._selected = self._selector.select(top_n=self.select_top_n)
            self._selected_syms = {s.symbol for s in self._selected}

        # Global signal
        global_return = None
        if self.global_signal_symbol in bars:
            global_return = self._update_signal(self.global_signal_symbol, bars[self.global_signal_symbol])

        # ── PER-SYMBOL ───────────────────────────────────────────────────
        stock_rs_overnight: List[Tuple[str, float, float]] = []
        tradable = [s for s in self.symbols if s not in SIGNAL_ONLY and s != "SPY"]

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
                if not st["holding_overnight"]:
                    st["rs_traded"] = False; st["overnight_traded"] = False
                st["current_date"] = today; st["day_open"] = bar.open

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0
            sym_bar_mins = et.hour * 60 + et.minute

            # ── Exit overnight ───────────────────────────────────────────
            if st["holding_overnight"] and st["overnight_entry_date"] != today:
                if st["stop_level"] and current_qty > 0 and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="mod stop"))
                    st["holding_overnight"] = False; st["position_type"] = None; continue
                if sym_bar_mins >= open_mins + self.overnight_exit_after_min:
                    signals.append(Signal(symbol, Direction.FLAT, reason="mod exit"))
                    st["holding_overnight"] = False; st["position_type"] = None
                continue

            # ── RS short management ──────────────────────────────────────
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="mod RS stop"))
                    st["position_type"] = None
                elif st["target_level"] and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="mod RS target"))
                    st["position_type"] = None
                elif et.hour > self.rs_close_hour or (et.hour == self.rs_close_hour and et.minute >= self.rs_close_minute):
                    signals.append(Signal(symbol, Direction.FLAT, reason="mod RS close"))
                    st["position_type"] = None
                continue

            if current_qty > 0 and st["holding_overnight"] and st["overnight_entry_date"] == today:
                if st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="mod stop(d)"))
                    st["holding_overnight"] = False; st["position_type"] = None
                continue

            if current_qty != 0:
                continue
            if not st["day_open"] or st["day_open"] == 0 or spy_return_pct is None:
                continue

            stock_ret = (price - st["day_open"]) / st["day_open"] * 100
            rs = stock_ret - spy_return_pct

            # ── BEAR: RS short on SELECTED short-biased stocks ───────────
            if (symbol in self._selected_syms
                    and not st["rs_traded"] and spy_bearish_full
                    and sym_bar_mins >= open_mins + self.rs_entry_after_min
                    and et.hour < self.rs_entry_end_hour):
                if rs < -self.rs_threshold:
                    st["rs_traded"] = True
                    st["stop_level"] = price * (1 + self.rs_stop_pct / 100)
                    st["target_level"] = price * (1 - self.rs_target_pct / 100)
                    st["position_type"] = "rs_short"
                    signals.append(Signal(symbol, Direction.SHORT, reason=f"mod RS={rs:.1f}%"))
                continue

            # ── BULL: collect overnight from SELECTED stocks ─────────────
            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
            if (symbol in self._selected_syms
                    and sym_bar_mins >= entry_mins and sym_bar_mins <= entry_mins + 5
                    and not st["overnight_traded"]):
                stock_rs_overnight.append((symbol, rs, price))

        # ── OVERNIGHT ENTRY ──────────────────────────────────────────────
        entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
        if (stock_rs_overnight and bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                and self._overnight_done_today != spy_today):
            self._overnight_done_today = spy_today
            global_bullish = global_return is not None and global_return > 0

            if spy_bullish:
                top_k, bot_k, tier = self.overnight_top_k, self.overnight_bottom_k, 1
            elif global_bullish:
                top_k, bot_k, tier = 2, 2, 2
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
                    st["overnight_traded"] = True; st["holding_overnight"] = True
                    st["overnight_entry_date"] = spy_today
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"on_t{tier}"
                    signals.append(Signal(sym, Direction.LONG, reason=f"mod T{tier} +{rs:.1f}%"))
                    top_k -= 1

                losers = sorted([x for x in stock_rs_overnight if x[1] < -self.overnight_min_move], key=lambda x: x[1])
                for sym, rs, px in losers:
                    if bot_k <= 0: break
                    st = self._sym.get(sym)
                    if not st or st["overnight_traded"] or st["holding_overnight"]: continue
                    pos = portfolio.get_position(sym)
                    if pos and pos.quantity != 0: continue
                    st["overnight_traded"] = True; st["holding_overnight"] = True
                    st["overnight_entry_date"] = spy_today
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"on_t{tier}"
                    signals.append(Signal(sym, Direction.LONG, reason=f"mod T{tier} dip {rs:.1f}%"))
                    bot_k -= 1

        return signals
