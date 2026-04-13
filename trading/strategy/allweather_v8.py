"""All-Weather v8: Asymmetric Hold — Keep Winners, Cut Losers.

CORE INNOVATION: Previous overnight strategies exit ALL positions 15 min after
open. This treats winners and losers the same. v8 applies asymmetric logic:

  WINNERS (position profitable at 9:45): Hold through the day. Exit at 15:25.
    - Captures regular-session continuation (the other ~50% of daily returns)
    - In 2025 bull, most positions are winners → double holding period → ~2× return

  LOSERS (position unprofitable at 9:45): Exit immediately.
    - Limits damage. Gap was wrong direction. Cut and move on.
    - In 2026 bear, most positions are losers → quick exit → similar to current

WHY THIS SHOULD BREAK THE 10% CEILING:
  - Current overnight: captures gap only (~50% of daily return, 18h hold)
  - With asymmetric hold: captures gap + continuation on winners (~80% of daily return)
  - Winners become close-to-close holds. Losers stay overnight-only.
  - Net effect: ~1.5-2× the return of simple overnight in bull markets.

REGIME STRUCTURE (unchanged from v5):
  - Tier 1 (SPY > VWAP): full allocation
  - Tier 2 (Global signal): reduced allocation
  - Bear sleeve: RS shorts intraday (proven)

NEW: Optional multi-day extension. If a position is a winner at 15:25 AND
the day was bullish, don't exit — hold into next overnight too. This creates
a self-reinforcing trend-following effect where winning positions "graduate"
from overnight-only to multi-day holds.

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


class AllWeatherV8Strategy(Strategy):
    name = "allweather_v8"
    label = "All-Weather v8 (Asymmetric Hold)"

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
        # Overnight entry
        overnight_top_k: int = 3,
        overnight_bottom_k: int = 3,
        overnight_stop_pct: float = 2.0,
        overnight_min_move: float = 0.3,
        overnight_entry_hour: int = 15,
        overnight_entry_minute: int = 30,
        # Asymmetric exit
        loser_exit_min: int = 15,         # exit losers this many min after open
        winner_hold_until_hour: int = 15,  # hold winners until this hour
        winner_hold_until_min: int = 25,   # ... and this minute
        # Multi-day extension: keep winners that are still winning at EOD
        multiday_extend: bool = False,     # if True, winners at EOD hold another night
        max_extend_days: int = 3,          # max days a position can be extended
        extend_stop_pct: float = 3.0,      # trailing stop for extended positions
        # Global signal (tier 2)
        global_signal_symbol: str = "VGK",
        tier2_top_k: int = 1,
        tier2_bottom_k: int = 1,
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
        self.loser_exit_min = loser_exit_min
        self.winner_hold_until_hour = winner_hold_until_hour
        self.winner_hold_until_min = winner_hold_until_min
        self.multiday_extend = multiday_extend
        self.max_extend_days = max_extend_days
        self.extend_stop_pct = extend_stop_pct
        self.global_signal_symbol = global_signal_symbol
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
            # Position state
            "position_type": None,  # "rs_short", "overnight", "winner_hold", "extended"
            "entry_price": None,
            "entry_date": None,
            "holding_overnight": False,
            "loser_checked": False,  # did we check win/lose at morning exit time?
            "is_winner": False,
            "extend_days": 0,
            "peak_price": None,
            "stop_level": None,
            "target_level": None,
        }

    def _fresh_signal(self) -> dict:
        return {"current_date": None, "day_open": None}

    def rules(self) -> List[str]:
        r = [
            "=== BEAR SLEEVE (RS Short) ===",
            f"RS < -{self.rs_threshold}% on bearish sessions (VWAP + {self.spy_trend_days}d trend)",
            "=== BULL SLEEVE (Overnight + Asymmetric Hold) ===",
            f"T1 (SPY>VWAP): {self.overnight_top_k}+{self.overnight_bottom_k}",
            f"T2 ({self.global_signal_symbol}>0): {self.tier2_top_k}+{self.tier2_bottom_k}",
            "=== ASYMMETRIC EXIT ===",
            f"Losers: exit at 9:30+{self.loser_exit_min}min",
            f"Winners: hold until {self.winner_hold_until_hour}:{self.winner_hold_until_min:02d}",
        ]
        if self.multiday_extend:
            r.append(f"Extend winners up to {self.max_extend_days} days (trail stop {self.extend_stop_pct}%)")
        return r

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

        # ── SPY ──────────────────────────────────────────────────────────────
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

        # ── Global signal ────────────────────────────────────────────────────
        global_return = None
        if self.global_signal_symbol in bars:
            global_return = self._update_signal(self.global_signal_symbol, bars[self.global_signal_symbol])

        # ── Per-symbol ───────────────────────────────────────────────────────
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
                if not st["holding_overnight"] and st["position_type"] not in ("winner_hold", "extended"):
                    st["rs_traded"] = False
                    st["overnight_traded"] = False
                st["current_date"] = today
                st["day_open"] = bar.open
                st["loser_checked"] = False
                st["is_winner"] = False

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0
            sym_bar_mins = et.hour * 60 + et.minute

            # ── MANAGE OVERNIGHT POSITIONS (asymmetric exit) ─────────────
            if current_qty > 0 and st["position_type"] in ("overnight", "winner_hold", "extended"):
                is_next_day = st["entry_date"] != today

                # Extended position management (multi-day holds)
                if st["position_type"] == "extended":
                    # Update trailing stop
                    if st["peak_price"] is None or price > st["peak_price"]:
                        st["peak_price"] = price
                        st["stop_level"] = price * (1 - self.extend_stop_pct / 100)

                    if st["stop_level"] and price <= st["stop_level"]:
                        signals.append(Signal(symbol, Direction.FLAT, reason="v8 ext trail"))
                        self._reset_sym(st)
                        continue

                    if st["extend_days"] >= self.max_extend_days:
                        # Max extension reached — exit at loser_exit_min
                        if is_next_day and sym_bar_mins >= open_mins + self.loser_exit_min:
                            signals.append(Signal(symbol, Direction.FLAT, reason="v8 ext max"))
                            self._reset_sym(st)
                        continue

                    # At EOD, check if still winning for another extension
                    if (sym_bar_mins >= self.winner_hold_until_hour * 60 + self.winner_hold_until_min
                            and sym_bar_mins < self.winner_hold_until_hour * 60 + self.winner_hold_until_min + 5):
                        if st["entry_price"] and price > st["entry_price"]:
                            st["extend_days"] += 1
                            # Keep holding
                        else:
                            signals.append(Signal(symbol, Direction.FLAT, reason="v8 ext exit"))
                            self._reset_sym(st)
                    continue

                # Overnight/winner_hold: first check at loser_exit_min
                if is_next_day and not st["loser_checked"] and sym_bar_mins >= open_mins + self.loser_exit_min:
                    st["loser_checked"] = True
                    if st["entry_price"] and price < st["entry_price"]:
                        # LOSER: exit immediately
                        signals.append(Signal(symbol, Direction.FLAT, reason="v8 loser exit"))
                        self._reset_sym(st)
                        continue
                    else:
                        # WINNER: hold through the day
                        st["position_type"] = "winner_hold"
                        st["is_winner"] = True
                        continue

                # Winner hold: exit at winner_hold time
                if (st["position_type"] == "winner_hold"
                        and sym_bar_mins >= self.winner_hold_until_hour * 60 + self.winner_hold_until_min
                        and sym_bar_mins < self.winner_hold_until_hour * 60 + self.winner_hold_until_min + 5):

                    if self.multiday_extend and st["entry_price"] and price > st["entry_price"]:
                        # Still winning at EOD — extend to next day
                        st["position_type"] = "extended"
                        st["extend_days"] = 1
                        st["peak_price"] = price
                        st["stop_level"] = price * (1 - self.extend_stop_pct / 100)
                        continue
                    else:
                        signals.append(Signal(symbol, Direction.FLAT, reason="v8 winner exit"))
                        self._reset_sym(st)
                        continue

                # Overnight stop (same day as entry or early next day)
                if st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v8 stop"))
                    self._reset_sym(st)
                    continue

                continue

            # ── MANAGE RS SHORT ──────────────────────────────────────────
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v8 RS stop"))
                    st["position_type"] = None
                elif st["target_level"] and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v8 RS target"))
                    st["position_type"] = None
                elif et.hour == 15 and et.minute >= 25:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v8 RS close"))
                    st["position_type"] = None
                continue

            if current_qty != 0:
                continue
            if not st["day_open"] or st["day_open"] == 0:
                continue

            stock_ret = (price - st["day_open"]) / st["day_open"] * 100
            rs = stock_ret - spy_return_pct if spy_return_pct is not None else 0

            # ── BEAR: RS short ───────────────────────────────────────────
            if (not st["rs_traded"] and spy_bearish_full
                    and sym_bar_mins >= open_mins + self.rs_entry_after_min
                    and et.hour < self.rs_entry_end_hour):
                if rs < -self.rs_threshold:
                    st["rs_traded"] = True
                    st["stop_level"] = price * (1 + self.rs_stop_pct / 100)
                    st["target_level"] = price * (1 - self.rs_target_pct / 100) if self.rs_target_pct > 0 else None
                    st["position_type"] = "rs_short"
                    signals.append(Signal(symbol, Direction.SHORT, reason=f"v8 RS={rs:.1f}%"))
                continue

            # ── BULL: collect overnight candidates ───────────────────────
            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
            if (sym_bar_mins >= entry_mins and sym_bar_mins <= entry_mins + 5
                    and not st["overnight_traded"] and spy_return_pct is not None):
                stock_rs.append((symbol, rs, price))

        # ── OVERNIGHT ENTRY (tiered) ────────────────────────────────────────
        sample = spy_bar
        et = sample.timestamp.astimezone(ET)
        today = et.date()
        bar_mins = et.hour * 60 + et.minute
        entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute

        if (stock_rs and bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                and self._overnight_done_today != today):

            self._overnight_done_today = today

            global_bullish = global_return is not None and global_return > 0

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
                    st["entry_date"] = today
                    st["entry_price"] = px
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = "overnight"
                    signals.append(Signal(sym, Direction.LONG, reason=f"v8 T{tier} +{rs:.1f}%"))
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
                    st["entry_date"] = today
                    st["entry_price"] = px
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = "overnight"
                    signals.append(Signal(sym, Direction.LONG, reason=f"v8 T{tier} dip {rs:.1f}%"))
                    bot_k -= 1

        return signals

    def _reset_sym(self, st: dict) -> None:
        st["holding_overnight"] = False
        st["position_type"] = None
        st["entry_price"] = None
        st["entry_date"] = None
        st["loser_checked"] = False
        st["is_winner"] = False
        st["extend_days"] = 0
        st["peak_price"] = None
        st["stop_level"] = None
        st["target_level"] = None
