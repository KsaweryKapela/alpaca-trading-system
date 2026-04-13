"""All-Weather Global: RS Short + Global-Signal Overnight Long.

Key innovation: Uses international ETF performance (VGK/EFA) as an
INDEPENDENT signal for overnight entry decisions. European markets
close by 11:30 ET — by our 15:30 entry time, we know the full
European session result.

The hypothesis: when Europe has a strong day, the overnight gap
for US stocks tends to be positive even if SPY had a weak intraday
session. This allows us to override the VWAP filter on nights where
global sentiment confirms bullishness, attacking the 35-40% coverage
gap that limits our 2025 returns.

Three-tier overnight system:
  Tier 1: SPY above VWAP → full allocation (high confidence)
  Tier 2: SPY below VWAP BUT global ETF up → reduced allocation (global confirmation)
  Tier 3: SPY below VWAP AND global ETF down → no overnight (bear night)

This extends coverage from ~60% to ~75% of 2025 nights.

Bear sleeve: RS short intraday (unchanged).
REQUIRES: VGK and/or EFA in the symbol list. eod_flatten=False.
"""

from collections import deque
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")

# International signal ETFs (not traded, only used for signal)
GLOBAL_SIGNAL_SYMBOLS = {"VGK", "EFA", "EWG", "FXI", "EWJ"}


class AllWeatherGlobalStrategy(Strategy):
    name = "allweather_global"
    label = "All-Weather Global (International Signal)"

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
        overnight_exit_after_min: int = 15,
        # Global signal params
        global_signal_symbol: str = "VGK",   # which international ETF to use
        global_min_return: float = 0.3,      # global ETF must be up this % for tier-2
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
        self._state: Dict[str, dict] = {}
        self._spy_state: dict = {}
        self._global_state: dict = {}
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
            "daily_closes": deque(maxlen=max(self.spy_trend_days, 1)),
        }

    def _fresh_global(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
        }

    def on_start(self) -> None:
        self._state = {sym: self._fresh_sym() for sym in self.symbols
                       if sym not in GLOBAL_SIGNAL_SYMBOLS}
        self._spy_state = self._fresh_spy()
        self._global_state = self._fresh_global()
        self._overnight_done_today = None

    def rules(self) -> List[str]:
        return [
            "=== BEAR SLEEVE (RS Short) ===",
            f"RS < -{self.rs_threshold}% on bearish sessions (VWAP + {self.spy_trend_days}d trend)",
            "=== BULL SLEEVE (Global-Signal Overnight) ===",
            f"Tier 1 (SPY > VWAP): {self.overnight_top_k} winners + {self.overnight_bottom_k} dip buys",
            f"Tier 2 (SPY < VWAP BUT {self.global_signal_symbol} > +{self.global_min_return}%): {self.tier2_top_k}+{self.tier2_bottom_k}",
            f"Global signal: {self.global_signal_symbol} session return (Europe/International)",
            f"Overnight stop: {self.overnight_stop_pct}% | Exit {self.overnight_exit_after_min}min",
        ]

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

        # ── Global signal ETF ─────────────────────────────────────────────────
        global_bar = bars.get(self.global_signal_symbol)
        global_return_pct: Optional[float] = None

        if global_bar is not None:
            et_g = global_bar.timestamp.astimezone(ET)
            g_today = et_g.date()
            gs = self._global_state

            if gs["current_date"] != g_today:
                gs["current_date"] = g_today
                gs["day_open"] = global_bar.open

            if gs["day_open"] and gs["day_open"] > 0:
                global_return_pct = (global_bar.close - gs["day_open"]) / gs["day_open"] * 100

        # ── Per-symbol ────────────────────────────────────────────────────────
        stock_rs: List[Tuple[str, float, float]] = []

        tradable_symbols = [s for s in self.symbols if s not in GLOBAL_SIGNAL_SYMBOLS and s != "SPY"]

        for symbol in tradable_symbols:
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

            # Exit overnight from previous day
            if st["holding_overnight"] and st["overnight_entry_date"] != today:
                if st["stop_level"] is not None and current_qty > 0 and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="awg overnight stop"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                    continue
                if bar_mins >= open_mins + self.overnight_exit_after_min:
                    signals.append(Signal(symbol, Direction.FLAT, reason="awg overnight exit"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            # Manage RS short
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["stop_level"] is not None and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="awg RS stop"))
                    st["position_type"] = None
                elif st["target_level"] is not None and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="awg RS target"))
                    st["position_type"] = None
                elif et.hour == 15 and et.minute >= 25:
                    signals.append(Signal(symbol, Direction.FLAT, reason="awg RS pre-close"))
                    st["position_type"] = None
                continue

            # Manage overnight on entry day
            if current_qty > 0 and st["holding_overnight"] and st["overnight_entry_date"] == today:
                if st["stop_level"] is not None and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="awg overnight stop (day)"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            if current_qty != 0:
                continue
            if st["day_open"] is None or st["day_open"] == 0:
                continue

            # Bear sleeve: RS short
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
                    signals.append(Signal(symbol, Direction.SHORT, reason=f"awg RS={rs:.1f}%"))
                continue

            # Collect overnight candidates
            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
            if (bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                    and not st["overnight_traded"] and spy_return_pct is not None):
                stock_return = (price - st["day_open"]) / st["day_open"] * 100
                rs = stock_return - spy_return_pct
                stock_rs.append((symbol, rs, price))

        # ── TIERED OVERNIGHT ENTRY with GLOBAL SIGNAL ─────────────────────────
        sample_bar = bars.get("SPY") or next((bars[s] for s in self.symbols if s in bars), None)
        if sample_bar is None:
            return signals
        et = sample_bar.timestamp.astimezone(ET)
        today = et.date()
        bar_mins = et.hour * 60 + et.minute
        entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute

        if (stock_rs and bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                and self._overnight_done_today != today):

            # Determine tier using SPY VWAP + Global signal
            global_bullish = (global_return_pct is not None
                              and global_return_pct > self.global_min_return)

            if spy_bullish_vwap:
                # Tier 1: SPY bullish → full allocation
                top_k = self.overnight_top_k
                bot_k = self.overnight_bottom_k
                tier = 1
            elif global_bullish:
                # Tier 2: SPY weak BUT Europe/Global strong → reduced allocation
                top_k = self.tier2_top_k
                bot_k = self.tier2_bottom_k
                tier = 2
            else:
                # No entry: both SPY and global weak
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
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"overnight_t{tier}"
                    signals.append(Signal(sym, Direction.LONG,
                                          reason=f"awg T{tier} mom RS={rs:.1f}%"))
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
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"overnight_t{tier}"
                    signals.append(Signal(sym, Direction.LONG,
                                          reason=f"awg T{tier} rev RS={rs:.1f}%"))
                    bot_k -= 1

        return signals
