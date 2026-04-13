"""All-Weather v10: Margin Overlay — Short Proceeds Fund Longs.

CRITICAL INSIGHT: In previous allweather strategies, RS shorts close at 15:25
and overnight longs enter at 15:30. The 5-minute gap means short cash proceeds
are no longer available when longs enter. Cash reverts to baseline, limiting
overnight longs to ~2 positions.

V10 FIX: Delay RS short close to 15:35-15:40 (AFTER long entry at 15:30).
At 15:30, the portfolio still holds shorts (cash inflated by short proceeds).
The risk manager sees more available cash → allows MORE long positions.
When shorts close at 15:35, cash decreases but longs are already entered.

EFFECTIVE LEVERAGE: With 3 shorts at $50K proceeds each = $150K extra cash.
$100K base + $150K short proceeds = $250K available for longs.
Instead of 2 overnight longs, we can now enter 5 = 2.5x effective leverage.

This creates the same economics as a real margin account where short proceeds
collateralize long positions — but entirely within the simulation framework.

STRUCTURE:
  Bear sleeve: RS shorts (9:45 → 15:35) — delayed close by 10 min
  Bull sleeve: Overnight longs (15:30 → next 9:45)
  Overlap window: 15:30-15:35 — both shorts and longs held simultaneously
  Global signal: VGK (tier 2 for more trading nights)

REQUIRES: eod_flatten=False.
"""

from collections import deque
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")

SIGNAL_ONLY = {"VGK", "EFA", "EWG", "FXI", "EWJ", "UVXY", "VXX", "VIXY"}


class AllWeatherV10Strategy(Strategy):
    name = "allweather_v10"
    label = "All-Weather v10 (Margin Overlay)"

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
        rs_close_hour: int = 15,        # delayed close hour
        rs_close_minute: int = 35,       # delayed close minute (was 25 in v5)
        # Overnight longs
        overnight_top_k: int = 4,
        overnight_bottom_k: int = 4,
        overnight_stop_pct: float = 2.0,
        overnight_min_move: float = 0.3,
        overnight_entry_hour: int = 15,
        overnight_entry_minute: int = 30,
        overnight_exit_after_min: int = 15,
        # Global signal
        global_signal_symbol: str = "VGK",
        global_min_return: float = 0.0,
        tier2_top_k: int = 2,
        tier2_bottom_k: int = 2,
    ) -> None:
        super().__init__(symbols)
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
            "=== BEAR SLEEVE (RS Short — delayed close) ===",
            f"RS < -{self.rs_threshold}% on bearish sessions (VWAP + {self.spy_trend_days}d trend)",
            f"Close shorts at {self.rs_close_hour}:{self.rs_close_minute:02d} (AFTER overnight entry)",
            "=== BULL SLEEVE (Overnight Long — margin overlay) ===",
            f"T1 (SPY>VWAP): {self.overnight_top_k}+{self.overnight_bottom_k}",
            f"T2 ({self.global_signal_symbol}>0): {self.tier2_top_k}+{self.tier2_bottom_k}",
            f"Exit {self.overnight_exit_after_min}min after open",
            "=== MARGIN OVERLAY ===",
            "Short proceeds at 15:30 fund additional long positions",
            "15:30-15:35: overlapping shorts+longs = leveraged exposure",
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

        # Per-symbol
        stock_rs: List[Tuple[str, float, float]] = []
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
                    st["rs_traded"] = False
                    st["overnight_traded"] = False
                st["current_date"] = today
                st["day_open"] = bar.open

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0
            sym_bar_mins = et.hour * 60 + et.minute

            # ── Exit overnight longs ─────────────────────────────────────
            if st["holding_overnight"] and st["overnight_entry_date"] != today:
                if st["stop_level"] is not None and current_qty > 0 and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v10 stop"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                    continue
                if sym_bar_mins >= open_mins + self.overnight_exit_after_min:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v10 exit"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            # ── Manage RS short (DELAYED close at rs_close_hour:rs_close_minute) ──
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v10 RS stop"))
                    st["position_type"] = None
                elif st["target_level"] and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v10 RS target"))
                    st["position_type"] = None
                elif (et.hour > self.rs_close_hour or
                      (et.hour == self.rs_close_hour and et.minute >= self.rs_close_minute)):
                    signals.append(Signal(symbol, Direction.FLAT, reason="v10 RS close"))
                    st["position_type"] = None
                continue

            # Same-day overnight stop
            if current_qty > 0 and st["holding_overnight"] and st["overnight_entry_date"] == today:
                if st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v10 stop (day)"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            if current_qty != 0:
                continue
            if not st["day_open"] or st["day_open"] == 0:
                continue

            stock_ret = (price - st["day_open"]) / st["day_open"] * 100
            rs = stock_ret - spy_return_pct if spy_return_pct is not None else 0

            # ── Bear: RS short entry ─────────────────────────────────────
            if (not st["rs_traded"] and spy_bearish_full
                    and sym_bar_mins >= open_mins + self.rs_entry_after_min
                    and et.hour < self.rs_entry_end_hour):
                if rs < -self.rs_threshold:
                    st["rs_traded"] = True
                    st["stop_level"] = price * (1 + self.rs_stop_pct / 100)
                    st["target_level"] = price * (1 - self.rs_target_pct / 100) if self.rs_target_pct > 0 else None
                    st["position_type"] = "rs_short"
                    signals.append(Signal(symbol, Direction.SHORT, reason=f"v10 RS={rs:.1f}%"))
                continue

            # ── Bull: collect overnight candidates ───────────────────────
            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
            if (sym_bar_mins >= entry_mins and sym_bar_mins <= entry_mins + 5
                    and not st["overnight_traded"] and spy_return_pct is not None):
                stock_rs.append((symbol, rs, price))

        # ── OVERNIGHT ENTRY ──────────────────────────────────────────────────
        sample = spy_bar
        et = sample.timestamp.astimezone(ET)
        today = et.date()
        bar_mins = et.hour * 60 + et.minute
        entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute

        if (stock_rs and bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                and self._overnight_done_today != today):

            self._overnight_done_today = today

            global_bullish = global_return is not None and global_return > self.global_min_return

            if spy_bullish_vwap:
                top_k = self.overnight_top_k
                bot_k = self.overnight_bottom_k
                tier = 1
            elif global_bullish:
                top_k = self.tier2_top_k
                bot_k = self.tier2_bottom_k
                tier = 2
            else:
                top_k, bot_k, tier = 0, 0, 0

            if top_k > 0 or bot_k > 0:
                stock_rs.sort(key=lambda x: x[1], reverse=True)

                # Winners
                for sym, rs, px in stock_rs:
                    if top_k <= 0:
                        break
                    if rs < self.overnight_min_move:
                        continue
                    st = self._sym.get(sym)
                    if not st or st["overnight_traded"] or st["holding_overnight"]:
                        continue
                    pos = portfolio.get_position(sym)
                    if pos and pos.quantity != 0:
                        continue
                    st["overnight_traded"] = True
                    st["holding_overnight"] = True
                    st["overnight_entry_date"] = today
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"on_t{tier}"
                    signals.append(Signal(sym, Direction.LONG, reason=f"v10 T{tier} +{rs:.1f}%"))
                    top_k -= 1

                # Dip buys
                losers = sorted([x for x in stock_rs if x[1] < -self.overnight_min_move], key=lambda x: x[1])
                for sym, rs, px in losers:
                    if bot_k <= 0:
                        break
                    st = self._sym.get(sym)
                    if not st or st["overnight_traded"] or st["holding_overnight"]:
                        continue
                    pos = portfolio.get_position(sym)
                    if pos and pos.quantity != 0:
                        continue
                    st["overnight_traded"] = True
                    st["holding_overnight"] = True
                    st["overnight_entry_date"] = today
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"on_t{tier}"
                    signals.append(Signal(sym, Direction.LONG, reason=f"v10 T{tier} dip {rs:.1f}%"))
                    bot_k -= 1

        return signals
