"""All-Weather v4: Tiered Overnight Coverage + Adaptive Exit.

The v3 ceiling (~8.4% in 2025) comes from VWAP blocking ~40% of nights.
V4 attacks this with TWO changes:

1. TIERED OVERNIGHT ENTRY:
   - Tier 1: SPY above VWAP → full allocation (top_k + bottom_k positions)
   - Tier 2: SPY below VWAP BUT above N-day SMA → half allocation (top 1 + bottom 1)
   This captures ~80% of 2025 nights vs ~60% with VWAP-only.

2. ADAPTIVE EXIT:
   - If overnight position gaps UP at open → hold until exit_hold_min (15-30 min)
     to capture opening continuation
   - If overnight position gaps DOWN at open → exit immediately (5 min)
     to limit damage from failed gaps
   This improves the win/loss asymmetry.

Bear sleeve unchanged: RS short intraday.
REQUIRES: eod_flatten=False
"""

from collections import deque
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class AllWeatherV4Strategy(Strategy):
    name = "allweather_v4"
    label = "All-Weather v4 (Tiered + Adaptive Exit)"

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
        # Overnight params
        overnight_top_k: int = 3,
        overnight_bottom_k: int = 3,
        overnight_stop_pct: float = 2.0,
        overnight_min_move: float = 0.3,
        overnight_entry_hour: int = 15,
        overnight_entry_minute: int = 30,
        # Tiered params
        sma_period: int = 10,
        tier2_top_k: int = 1,           # reduced positions on tier-2 nights
        tier2_bottom_k: int = 1,
        # Adaptive exit
        exit_win_min: int = 15,          # hold winners 15 min after open
        exit_loss_min: int = 5,          # cut losers 5 min after open
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
        self.sma_period = sma_period
        self.tier2_top_k = tier2_top_k
        self.tier2_bottom_k = tier2_bottom_k
        self.exit_win_min = exit_win_min
        self.exit_loss_min = exit_loss_min
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
            "overnight_entry_price": None,
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
            "=== BEAR SLEEVE (RS Short) ===",
            f"RS < -{self.rs_threshold}% on bearish sessions (VWAP + {self.spy_trend_days}d trend)",
            "=== BULL SLEEVE (Tiered Overnight) ===",
            f"Tier 1 (SPY > VWAP): top {self.overnight_top_k} + bottom {self.overnight_bottom_k} positions",
            f"Tier 2 (SPY < VWAP but > {self.sma_period}-SMA): top {self.tier2_top_k} + bottom {self.tier2_bottom_k}",
            f"Adaptive exit: winners hold {self.exit_win_min}min, losers exit {self.exit_loss_min}min",
            f"Overnight stop: {self.overnight_stop_pct}%",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # ── SPY ───────────────────────────────────────────────────────────────
        spy_bar = bars.get("SPY")
        spy_return_pct: Optional[float] = None
        spy_price: Optional[float] = None
        spy_bullish_vwap = False
        spy_above_sma = False
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

            if len(spy["daily_closes"]) >= self.sma_period:
                recent = list(spy["daily_closes"])[-self.sma_period:]
                spy_above_sma = spy_price > (sum(recent) / len(recent))

        # ── Per-symbol ────────────────────────────────────────────────────────
        stock_rs: List[Tuple[str, float, float]] = []

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

            # ── ADAPTIVE EXIT: overnight from previous day ────────────────────
            if st["holding_overnight"] and st["overnight_entry_date"] != today:
                # Check stop first
                if st["stop_level"] is not None and current_qty > 0 and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw4 overnight stop"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                    continue

                # Adaptive exit: check if position is winning or losing
                entry_px = st.get("overnight_entry_price")
                if entry_px and entry_px > 0:
                    is_winning = price > entry_px
                    exit_min = self.exit_win_min if is_winning else self.exit_loss_min
                else:
                    exit_min = self.exit_loss_min  # default to fast exit

                if bar_mins >= open_mins + exit_min:
                    tag = "win" if (entry_px and price > entry_px) else "loss"
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"aw4 overnight {tag} exit +{exit_min}min"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            # ── MANAGE: RS short ──────────────────────────────────────────────
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["stop_level"] is not None and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw4 RS stop"))
                    st["position_type"] = None
                elif st["target_level"] is not None and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw4 RS target"))
                    st["position_type"] = None
                elif et.hour == 15 and et.minute >= 25:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw4 RS pre-close"))
                    st["position_type"] = None
                continue

            # ── MANAGE: overnight on entry day ────────────────────────────────
            if current_qty > 0 and st["holding_overnight"] and st["overnight_entry_date"] == today:
                if st["stop_level"] is not None and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="aw4 overnight stop (day)"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            if current_qty != 0:
                continue
            if st["day_open"] is None or st["day_open"] == 0:
                continue

            # ── ENTRY: Bear sleeve ────────────────────────────────────────────
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
                    signals.append(Signal(symbol, Direction.SHORT, reason=f"aw4 RS={rs:.1f}%"))
                continue

            # ── COLLECT: overnight candidates ─────────────────────────────────
            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
            if (bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                    and not st["overnight_traded"] and spy_return_pct is not None):
                stock_return = (price - st["day_open"]) / st["day_open"] * 100
                rs = stock_return - spy_return_pct
                stock_rs.append((symbol, rs, price))

        # ── TIERED OVERNIGHT ENTRY ────────────────────────────────────────────
        sample_bar = bars.get("SPY") or next((bars[s] for s in self.symbols if s in bars), None)
        if sample_bar is None:
            return signals
        et = sample_bar.timestamp.astimezone(ET)
        today = et.date()
        bar_mins = et.hour * 60 + et.minute
        entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute

        if (stock_rs and bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                and self._overnight_done_today != today):

            # Determine tier
            if spy_bullish_vwap:
                top_k = self.overnight_top_k
                bot_k = self.overnight_bottom_k
                tier = 1
            elif spy_above_sma:
                top_k = self.tier2_top_k
                bot_k = self.tier2_bottom_k
                tier = 2
            else:
                top_k = 0
                bot_k = 0
                tier = 0

            self._overnight_done_today = today

            if top_k > 0 or bot_k > 0:
                stock_rs.sort(key=lambda x: x[1], reverse=True)

                # Winners (momentum)
                for sym, rs, px in stock_rs:
                    if top_k <= 0:
                        break
                    if rs < self.overnight_min_move:
                        continue
                    st = self._state[sym]
                    if st["overnight_traded"] or st["holding_overnight"]:
                        continue
                    pos = portfolio.get_position(sym)
                    if pos and pos.quantity != 0:
                        continue
                    st["overnight_traded"] = True
                    st["holding_overnight"] = True
                    st["overnight_entry_date"] = today
                    st["overnight_entry_price"] = px
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"overnight_t{tier}"
                    signals.append(Signal(sym, Direction.LONG,
                                          reason=f"aw4 ON-T{tier} mom RS={rs:.1f}%"))
                    top_k -= 1

                # Losers (reversal)
                losers = [x for x in stock_rs if x[1] < -self.overnight_min_move]
                losers.sort(key=lambda x: x[1])
                for sym, rs, px in losers:
                    if bot_k <= 0:
                        break
                    st = self._state[sym]
                    if st["overnight_traded"] or st["holding_overnight"]:
                        continue
                    pos = portfolio.get_position(sym)
                    if pos and pos.quantity != 0:
                        continue
                    st["overnight_traded"] = True
                    st["holding_overnight"] = True
                    st["overnight_entry_date"] = today
                    st["overnight_entry_price"] = px
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"overnight_t{tier}"
                    signals.append(Signal(sym, Direction.LONG,
                                          reason=f"aw4 ON-T{tier} rev RS={rs:.1f}%"))
                    bot_k -= 1

        return signals
