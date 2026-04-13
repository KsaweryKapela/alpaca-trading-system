"""Closing-Auction Momentum: Last-N-Minute Signal for Overnight Holds.

NEW STRATEGY FAMILY — genuinely different from all prior approaches.

THESIS: Institutional MOC (Market-on-Close) orders create predictable
price pressure in the last 10-30 minutes. Stocks being actively bought
into the close (positive last-15-min momentum) have larger overnight gaps.
Stocks being sold into the close fade.

DIFFERENCE FROM PRIOR WORK:
  - Previous overnight strategies use FULL-DAY RS at 15:30.
  - This uses LAST-15-MINUTE momentum as the selection criterion.
  - Full-day RS measures "how did this stock do today?" → noise from
    morning gaps, lunchtime drift, etc.
  - Last-15-min momentum measures "who is actively buying/selling NOW?"
    → captures institutional closing flow.

STRUCTURE:
  Bear sleeve: RS shorts (same as v10 — proven)
  Bull sleeve: Closing-momentum overnight longs
    - At 15:30, compute each stock's return from 15:15 to 15:30
    - Buy the top-K accelerating stocks (positive close momentum)
    - Also buy the bottom-K decelerating stocks (contrarian dip at close)
    - Hold overnight, exit 20 min after next open

MARGIN OVERLAY: Inherited from v10 (delayed RS close at 15:35).

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


class ClosingMomentumStrategy(Strategy):
    name = "closing_momentum"
    label = "Closing-Auction Momentum (Last-N-Min)"

    def __init__(
        self,
        symbols: List[str],
        # Bear sleeve
        rs_threshold: float = 1.0,
        rs_stop_pct: float = 1.0,
        rs_target_pct: float = 3.0,
        spy_trend_days: int = 3,
        rs_entry_after_min: int = 15,
        rs_entry_end_hour: int = 14,
        rs_close_hour: int = 15,
        rs_close_minute: int = 35,
        # Closing momentum overnight
        close_lookback_min: int = 15,    # measure momentum over last N minutes
        overnight_top_k: int = 4,
        overnight_bottom_k: int = 4,
        overnight_stop_pct: float = 2.0,
        overnight_min_close_move: float = 0.1,  # min last-N-min move to qualify
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
        self.rs_threshold = rs_threshold
        self.rs_stop_pct = rs_stop_pct
        self.rs_target_pct = rs_target_pct
        self.spy_trend_days = spy_trend_days
        self.rs_entry_after_min = rs_entry_after_min
        self.rs_entry_end_hour = rs_entry_end_hour
        self.rs_close_hour = rs_close_hour
        self.rs_close_minute = rs_close_minute
        self.close_lookback_min = close_lookback_min
        self.overnight_top_k = overnight_top_k
        self.overnight_bottom_k = overnight_bottom_k
        self.overnight_stop_pct = overnight_stop_pct
        self.overnight_min_close_move = overnight_min_close_move
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
            # Price buffer for close-momentum calculation
            "price_buffer": deque(maxlen=self.close_lookback_min + 5),
        }

    def _fresh_signal(self) -> dict:
        return {"current_date": None, "day_open": None}

    def rules(self) -> List[str]:
        return [
            "=== BEAR SLEEVE (RS Short — margin overlay) ===",
            f"RS < -{self.rs_threshold}% | Stop {self.rs_stop_pct}% | Target {self.rs_target_pct}%",
            "=== BULL SLEEVE (Closing-Auction Momentum) ===",
            f"Selection: last {self.close_lookback_min}-min momentum (NOT full-day RS)",
            f"T1: {self.overnight_top_k}+{self.overnight_bottom_k} | T2: {self.tier2_top_k}+{self.tier2_bottom_k}",
            f"Min close move: {self.overnight_min_close_move}%",
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
        close_momentum: List[Tuple[str, float, float]] = []  # (sym, close_mom, price)
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
                st["price_buffer"].clear()

            price = bar.close
            st["price_buffer"].append(price)

            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0
            sym_bar_mins = et.hour * 60 + et.minute

            # ── Exit overnight ───────────────────────────────────────────
            if st["holding_overnight"] and st["overnight_entry_date"] != today:
                if st["stop_level"] is not None and current_qty > 0 and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="cm stop"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                    continue
                if sym_bar_mins >= open_mins + self.overnight_exit_after_min:
                    signals.append(Signal(symbol, Direction.FLAT, reason="cm exit"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            # ── Manage RS short (delayed close) ──────────────────────────
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="cm RS stop"))
                    st["position_type"] = None
                elif st["target_level"] and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="cm RS target"))
                    st["position_type"] = None
                elif (et.hour > self.rs_close_hour or
                      (et.hour == self.rs_close_hour and et.minute >= self.rs_close_minute)):
                    signals.append(Signal(symbol, Direction.FLAT, reason="cm RS close"))
                    st["position_type"] = None
                continue

            # Same-day overnight stop
            if current_qty > 0 and st["holding_overnight"] and st["overnight_entry_date"] == today:
                if st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="cm stop (day)"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            if current_qty != 0:
                continue
            if not st["day_open"] or st["day_open"] == 0:
                continue

            stock_ret = (price - st["day_open"]) / st["day_open"] * 100
            rs = stock_ret - spy_return_pct if spy_return_pct is not None else 0

            # ── Bear: RS short ───────────────────────────────────────────
            if (not st["rs_traded"] and spy_bearish_full
                    and sym_bar_mins >= open_mins + self.rs_entry_after_min
                    and et.hour < self.rs_entry_end_hour):
                if rs < -self.rs_threshold:
                    st["rs_traded"] = True
                    st["stop_level"] = price * (1 + self.rs_stop_pct / 100)
                    st["target_level"] = price * (1 - self.rs_target_pct / 100) if self.rs_target_pct > 0 else None
                    st["position_type"] = "rs_short"
                    signals.append(Signal(symbol, Direction.SHORT, reason=f"cm RS={rs:.1f}%"))
                continue

            # ── Bull: compute closing momentum ───────────────────────────
            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
            if (sym_bar_mins >= entry_mins and sym_bar_mins <= entry_mins + 5
                    and not st["overnight_traded"]):
                buf = list(st["price_buffer"])
                if len(buf) >= self.close_lookback_min:
                    ref_price = buf[-self.close_lookback_min]
                    if ref_price > 0:
                        close_mom = (price - ref_price) / ref_price * 100
                        close_momentum.append((symbol, close_mom, price))

        # ── OVERNIGHT ENTRY (closing momentum) ──────────────────────────────
        et = spy_bar.timestamp.astimezone(ET)
        today = et.date()
        bar_mins = et.hour * 60 + et.minute
        entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute

        if (close_momentum and bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                and self._overnight_done_today != today):

            self._overnight_done_today = today
            global_bullish = global_return is not None and global_return > self.global_min_return

            if spy_bullish_vwap:
                top_k, bot_k, tier = self.overnight_top_k, self.overnight_bottom_k, 1
            elif global_bullish:
                top_k, bot_k, tier = self.tier2_top_k, self.tier2_bottom_k, 2
            else:
                top_k, bot_k, tier = 0, 0, 0

            if top_k > 0 or bot_k > 0:
                # Sort by closing momentum (highest = strongest close buyers)
                close_momentum.sort(key=lambda x: x[1], reverse=True)

                # Top-K: stocks with strongest closing momentum (institutional buying)
                for sym, cm, px in close_momentum:
                    if top_k <= 0:
                        break
                    if cm < self.overnight_min_close_move:
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
                    st["position_type"] = f"cm_t{tier}"
                    signals.append(Signal(sym, Direction.LONG, reason=f"cm T{tier} close+{cm:.2f}%"))
                    top_k -= 1

                # Bottom-K: stocks with weakest closing momentum (contrarian dip)
                losers = sorted(
                    [x for x in close_momentum if x[1] < -self.overnight_min_close_move],
                    key=lambda x: x[1]
                )
                for sym, cm, px in losers:
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
                    st["position_type"] = f"cm_t{tier}"
                    signals.append(Signal(sym, Direction.LONG, reason=f"cm T{tier} close{cm:.2f}%"))
                    bot_k -= 1

        return signals
