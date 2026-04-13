"""All-Weather v9: Calendar-Enhanced Overnight.

CORE INSIGHT (from academic research):
  - 100% of monthly equity returns concentrate in ~5 "turn-of-month" (TOM) days:
    the last trading day of the month + first 3 trading days of the next month.
  - The remaining ~16 trading days contribute zero or negative returns on average.
  - Pre-holiday days show 8-15x normal daily returns.
  - Higher-beta stocks have larger overnight premiums.

STRATEGY:
  This strategy concentrates overnight positions on CALENDAR-OPTIMAL days,
  reducing or eliminating positions on statistically neutral/negative days.

  TOM DAYS (day -1 to +3 of month):
    - Full allocation: top_k + bottom_k positions
    - Higher conviction → can afford more positions

  NON-TOM DAYS:
    - Reduced allocation (base_top_k + base_bottom_k, typically 1+1 or 0+0)
    - Only trade if signal quality is very strong

  PRE-HOLIDAY DAYS:
    - Same as TOM: full allocation (holidays are structural bullish events)

  BEAR SLEEVE: RS short intraday (unchanged, proven)

  STOCK PERSONALITY (integrated):
    - Track each stock's average daily range (proxy for beta)
    - On TOM days: prefer high-beta names (TSLA, COIN, AMD, RIVN)
    - On non-TOM days: prefer low-beta names (MSFT, AAPL, JPM) — if trading at all

REQUIRES: eod_flatten=False.
"""

from collections import deque
from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")

SIGNAL_ONLY = {"VGK", "EFA", "EWG", "FXI", "EWJ", "UVXY", "VXX", "VIXY"}

# US market holidays (2025-2026)
US_HOLIDAYS: Set[date] = {
    # 2025
    date(2025, 1, 1), date(2025, 1, 20), date(2025, 2, 17),
    date(2025, 4, 18), date(2025, 5, 26), date(2025, 6, 19),
    date(2025, 7, 4), date(2025, 9, 1), date(2025, 11, 27),
    date(2025, 12, 25),
    # 2026
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16),
    date(2026, 4, 3), date(2026, 5, 25), date(2026, 6, 19),
    date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26),
    date(2026, 12, 25),
}


def _is_tom_day(d: date) -> bool:
    """True if d is within the turn-of-month window: day -1 to +3."""
    import calendar
    _, last_day = calendar.monthrange(d.year, d.month)

    # Last 2 trading days of month (approximate: last 2 calendar days)
    if d.day >= last_day - 1:
        return True

    # First 4 calendar days of month (covers first 3 trading days)
    if d.day <= 4:
        return True

    return False


def _is_pre_holiday(d: date) -> bool:
    """True if tomorrow or the next 2 days include a market holiday."""
    for offset in range(1, 4):
        candidate = d + timedelta(days=offset)
        if candidate in US_HOLIDAYS:
            return True
        # Stop at the first weekday
        if candidate.weekday() < 5:
            break
    return False


class AllWeatherV9Strategy(Strategy):
    name = "allweather_v9"
    label = "All-Weather v9 (Calendar-Enhanced)"

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
        # TOM overnight (calendar-optimal days)
        tom_top_k: int = 5,
        tom_bottom_k: int = 5,
        # Non-TOM overnight (reduced)
        base_top_k: int = 1,
        base_bottom_k: int = 1,
        # Overnight common
        overnight_stop_pct: float = 2.0,
        overnight_min_move: float = 0.3,
        overnight_entry_hour: int = 15,
        overnight_entry_minute: int = 30,
        overnight_exit_after_min: int = 15,
        # Global signal
        global_signal_symbol: str = "VGK",
        global_min_return: float = 0.0,
        # Stock personality: prefer high beta on TOM
        prefer_high_beta_tom: bool = True,
    ) -> None:
        super().__init__(symbols)
        self.rs_threshold = rs_threshold
        self.rs_stop_pct = rs_stop_pct
        self.rs_target_pct = rs_target_pct
        self.spy_trend_days = spy_trend_days
        self.rs_entry_after_min = rs_entry_after_min
        self.rs_entry_end_hour = rs_entry_end_hour
        self.tom_top_k = tom_top_k
        self.tom_bottom_k = tom_bottom_k
        self.base_top_k = base_top_k
        self.base_bottom_k = base_bottom_k
        self.overnight_stop_pct = overnight_stop_pct
        self.overnight_min_move = overnight_min_move
        self.overnight_entry_hour = overnight_entry_hour
        self.overnight_entry_minute = overnight_entry_minute
        self.overnight_exit_after_min = overnight_exit_after_min
        self.global_signal_symbol = global_signal_symbol
        self.global_min_return = global_min_return
        self.prefer_high_beta_tom = prefer_high_beta_tom

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
            # Stock personality
            "daily_ranges": deque(maxlen=20),
            "prev_day_high": None, "prev_day_low": None,
            "day_high": None, "day_low": None,
        }

    def _fresh_signal(self) -> dict:
        return {"current_date": None, "day_open": None}

    def rules(self) -> List[str]:
        return [
            "=== BEAR SLEEVE (RS Short) ===",
            f"RS < -{self.rs_threshold}% on bearish sessions",
            "=== BULL SLEEVE (Calendar-Enhanced Overnight) ===",
            f"TOM days (day -1 to +3): {self.tom_top_k}+{self.tom_bottom_k} positions",
            f"Non-TOM days: {self.base_top_k}+{self.base_bottom_k} positions",
            "Pre-holiday: same as TOM",
            f"Global signal: {self.global_signal_symbol} > {self.global_min_return}%",
            f"Exit {self.overnight_exit_after_min}min after open",
            "Stock personality: high-beta preferred on TOM, low-beta on non-TOM",
        ]

    def _stock_beta(self, sym: str) -> float:
        """Average daily range as beta proxy."""
        st = self._sym.get(sym)
        if not st or len(st["daily_ranges"]) < 3:
            return 1.0
        ranges = list(st["daily_ranges"])
        return sum(ranges) / len(ranges)

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

        # Calendar classification
        is_tom = _is_tom_day(spy_today)
        is_holiday = _is_pre_holiday(spy_today)
        is_calendar_boost = is_tom or is_holiday

        # Global signal
        global_return = None
        if self.global_signal_symbol in bars:
            global_return = self._update_signal(self.global_signal_symbol, bars[self.global_signal_symbol])

        # Per-symbol
        stock_rs: List[Tuple[str, float, float, float]] = []  # (sym, rs, price, beta)
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
                # Track daily range for beta proxy
                if st["day_high"] is not None and st["day_low"] is not None and st["day_low"] > 0:
                    daily_range = (st["day_high"] - st["day_low"]) / st["day_low"] * 100
                    st["daily_ranges"].append(daily_range)
                if not st["holding_overnight"]:
                    st["rs_traded"] = False
                    st["overnight_traded"] = False
                st["current_date"] = today
                st["day_open"] = bar.open
                st["day_high"] = bar.high
                st["day_low"] = bar.low
            else:
                if bar.high > (st["day_high"] or 0):
                    st["day_high"] = bar.high
                if st["day_low"] is None or bar.low < st["day_low"]:
                    st["day_low"] = bar.low

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0
            sym_bar_mins = et.hour * 60 + et.minute

            # Exit overnight
            if st["holding_overnight"] and st["overnight_entry_date"] != today:
                if st["stop_level"] is not None and current_qty > 0 and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v9 stop"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                    continue
                if sym_bar_mins >= open_mins + self.overnight_exit_after_min:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v9 exit"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            # Manage RS short
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v9 RS stop"))
                    st["position_type"] = None
                elif st["target_level"] and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v9 RS target"))
                    st["position_type"] = None
                elif et.hour == 15 and et.minute >= 25:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v9 RS close"))
                    st["position_type"] = None
                continue

            # Same-day overnight stop
            if current_qty > 0 and st["holding_overnight"] and st["overnight_entry_date"] == today:
                if st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v9 stop (day)"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            if current_qty != 0:
                continue
            if not st["day_open"] or st["day_open"] == 0:
                continue

            stock_ret = (price - st["day_open"]) / st["day_open"] * 100
            rs = stock_ret - spy_return_pct if spy_return_pct is not None else 0

            # Bear sleeve: RS short
            if (not st["rs_traded"] and spy_bearish_full
                    and sym_bar_mins >= open_mins + self.rs_entry_after_min
                    and et.hour < self.rs_entry_end_hour):
                if rs < -self.rs_threshold:
                    st["rs_traded"] = True
                    st["stop_level"] = price * (1 + self.rs_stop_pct / 100)
                    st["target_level"] = price * (1 - self.rs_target_pct / 100) if self.rs_target_pct > 0 else None
                    st["position_type"] = "rs_short"
                    signals.append(Signal(symbol, Direction.SHORT, reason=f"v9 RS={rs:.1f}%"))
                continue

            # Collect overnight candidates
            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
            if (sym_bar_mins >= entry_mins and sym_bar_mins <= entry_mins + 5
                    and not st["overnight_traded"] and spy_return_pct is not None):
                beta = self._stock_beta(symbol)
                stock_rs.append((symbol, rs, price, beta))

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

            # Determine position count based on calendar + market regime
            if spy_bullish_vwap:
                if is_calendar_boost:
                    top_k = self.tom_top_k
                    bot_k = self.tom_bottom_k
                else:
                    top_k = self.base_top_k
                    bot_k = self.base_bottom_k
                tier = 1
            elif global_bullish:
                if is_calendar_boost:
                    top_k = max(self.tom_top_k // 2, 1)
                    bot_k = max(self.tom_bottom_k // 2, 1)
                else:
                    top_k = max(self.base_top_k, 1)
                    bot_k = max(self.base_bottom_k, 1)
                tier = 2
            else:
                top_k, bot_k, tier = 0, 0, 0

            if top_k > 0 or bot_k > 0:
                # Sort by beta: high beta for TOM (bigger overnight moves),
                # low beta for non-TOM (safer)
                if is_calendar_boost and self.prefer_high_beta_tom:
                    stock_rs.sort(key=lambda x: (-x[3], -x[1]))  # high beta first, then high RS
                else:
                    stock_rs.sort(key=lambda x: x[1], reverse=True)  # high RS first

                # Winners (momentum)
                for sym, rs, px, beta in stock_rs:
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
                    tag = "TOM" if is_calendar_boost else "base"
                    signals.append(Signal(sym, Direction.LONG, reason=f"v9 {tag} +{rs:.1f}%"))
                    top_k -= 1

                # Losers (dip buys — research shows "stocks down intraday" have better overnight returns)
                losers = sorted([x for x in stock_rs if x[1] < -self.overnight_min_move], key=lambda x: x[1])
                for sym, rs, px, beta in losers:
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
                    tag = "TOM" if is_calendar_boost else "base"
                    signals.append(Signal(sym, Direction.LONG, reason=f"v9 {tag} dip {rs:.1f}%"))
                    bot_k -= 1

        return signals
