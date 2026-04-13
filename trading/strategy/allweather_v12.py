"""All-Weather v12: Sector-Relative Strength.

Builds on v10 (margin overlay + 20-min exit) with sector-relative RS
for the bear sleeve. Instead of measuring each stock against SPY alone,
we measure it against its SECTOR ETF.

WHY THIS SHOULD HELP:
  - SPY-relative RS includes sector rotation noise. If XLK (tech) is down 2%
    but SPY is only down 0.5%, ALL tech stocks appear "weak vs SPY" — but
    most are just following their sector, not individually weak.
  - Sector-relative RS isolates IDIOSYNCRATIC weakness: NVDA down 3% while
    XLK down 2% means NVDA is weak FOR A TECH STOCK → better short signal.
  - This should reduce false short signals in sector-wide moves and improve
    the quality of RS short picks.

SECTOR MAPPING:
  XLK (Technology): NVDA, AAPL, MSFT, AMZN, META, GOOGL, AMD, NFLX, COIN, SHOP, PLTR
  XLF (Financials): JPM
  Others (use SPY): BA, TSLA, RIVN, QQQ

REQUIRES: XLK in symbol list. eod_flatten=False.
"""

from collections import deque
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")

SIGNAL_ONLY = {"VGK", "EFA", "EWG", "FXI", "EWJ", "UVXY", "VXX", "VIXY", "XLK", "XLF", "SMH"}

SECTOR_MAP = {
    "NVDA": "XLK", "AAPL": "XLK", "MSFT": "XLK", "AMZN": "XLK",
    "META": "XLK", "GOOGL": "XLK", "AMD": "XLK", "NFLX": "XLK",
    "COIN": "XLK", "SHOP": "XLK", "PLTR": "XLK",
    "JPM": "XLF",
    # BA, TSLA, RIVN, QQQ → use SPY (no dedicated sector ETF)
}


class AllWeatherV12Strategy(Strategy):
    name = "allweather_v12"
    label = "All-Weather v12 (Sector-Relative RS)"

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
        rs_close_hour: int = 15,
        rs_close_minute: int = 35,
        use_sector_rs: bool = True,       # use sector-relative RS for shorts
        # Overnight longs
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
        self.rs_threshold = rs_threshold
        self.rs_stop_pct = rs_stop_pct
        self.rs_target_pct = rs_target_pct
        self.spy_trend_days = spy_trend_days
        self.rs_entry_after_min = rs_entry_after_min
        self.rs_entry_end_hour = rs_entry_end_hour
        self.rs_close_hour = rs_close_hour
        self.rs_close_minute = rs_close_minute
        self.use_sector_rs = use_sector_rs
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
        self._sector_states: Dict[str, dict] = {}  # XLK, XLF etc.
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
        self._sector_states = {}
        self._sym = {}
        self._signal_states = {}
        self._overnight_done_today = None

    def _fresh_sector(self) -> dict:
        return {"current_date": None, "day_open": None, "return_pct": None}

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
            "=== BEAR SLEEVE (Sector-Relative RS Short) ===",
            f"RS vs SECTOR < -{self.rs_threshold}% (XLK for tech, SPY for others)",
            f"Close at {self.rs_close_hour}:{self.rs_close_minute:02d} (margin overlay)",
            "=== BULL SLEEVE (Overnight Long) ===",
            f"T1: {self.overnight_top_k}+{self.overnight_bottom_k} | T2: {self.tier2_top_k}+{self.tier2_bottom_k}",
            f"Exit {self.overnight_exit_after_min}min after open",
            f"Global: {self.global_signal_symbol}",
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

    def _get_sector_return(self, symbol: str, spy_return: float) -> float:
        """Get sector return for this symbol. Falls back to SPY if no sector ETF."""
        if not self.use_sector_rs:
            return spy_return
        sector_sym = SECTOR_MAP.get(symbol)
        if sector_sym and sector_sym in self._sector_states:
            r = self._sector_states[sector_sym].get("return_pct")
            if r is not None:
                return r
        return spy_return

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

        # ── Update sector ETFs ───────────────────────────────────────────
        for sector_sym in ("XLK", "XLF", "SMH"):
            if sector_sym in bars:
                sb = bars[sector_sym]
                if sector_sym not in self._sector_states:
                    self._sector_states[sector_sym] = self._fresh_sector()
                ss = self._sector_states[sector_sym]
                et_s = sb.timestamp.astimezone(ET)
                today_s = et_s.date()
                if ss["current_date"] != today_s:
                    ss["current_date"] = today_s
                    ss["day_open"] = sb.open
                if ss["day_open"] and ss["day_open"] > 0:
                    ss["return_pct"] = (sb.close - ss["day_open"]) / ss["day_open"] * 100

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

            # Exit overnight
            if st["holding_overnight"] and st["overnight_entry_date"] != today:
                if st["stop_level"] is not None and current_qty > 0 and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v12 stop"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                    continue
                if sym_bar_mins >= open_mins + self.overnight_exit_after_min:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v12 exit"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            # Manage RS short (delayed close)
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v12 RS stop"))
                    st["position_type"] = None
                elif st["target_level"] and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v12 RS target"))
                    st["position_type"] = None
                elif (et.hour > self.rs_close_hour or
                      (et.hour == self.rs_close_hour and et.minute >= self.rs_close_minute)):
                    signals.append(Signal(symbol, Direction.FLAT, reason="v12 RS close"))
                    st["position_type"] = None
                continue

            # Same-day overnight stop
            if current_qty > 0 and st["holding_overnight"] and st["overnight_entry_date"] == today:
                if st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v12 stop (day)"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            if current_qty != 0:
                continue
            if not st["day_open"] or st["day_open"] == 0:
                continue

            stock_ret = (price - st["day_open"]) / st["day_open"] * 100

            # ── BEAR: Sector-relative RS short ───────────────────────────
            if (not st["rs_traded"] and spy_bearish_full
                    and sym_bar_mins >= open_mins + self.rs_entry_after_min
                    and et.hour < self.rs_entry_end_hour
                    and spy_return_pct is not None):
                # SECTOR-RELATIVE RS: compare stock to its sector, not just SPY
                sector_ret = self._get_sector_return(symbol, spy_return_pct)
                sector_rs = stock_ret - sector_ret

                if sector_rs < -self.rs_threshold:
                    st["rs_traded"] = True
                    st["stop_level"] = price * (1 + self.rs_stop_pct / 100)
                    st["target_level"] = price * (1 - self.rs_target_pct / 100) if self.rs_target_pct > 0 else None
                    st["position_type"] = "rs_short"
                    sect = SECTOR_MAP.get(symbol, "SPY")
                    signals.append(Signal(symbol, Direction.SHORT,
                                          reason=f"v12 sRS={sector_rs:.1f}% vs {sect}"))
                continue

            # ── BULL: collect overnight candidates (RS vs SPY, not sector) ──
            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
            if (sym_bar_mins >= entry_mins and sym_bar_mins <= entry_mins + 5
                    and not st["overnight_traded"] and spy_return_pct is not None):
                rs = stock_ret - spy_return_pct
                stock_rs.append((symbol, rs, price))

        # ── OVERNIGHT ENTRY ──────────────────────────────────────────────────
        et = spy_bar.timestamp.astimezone(ET)
        today = et.date()
        bar_mins = et.hour * 60 + et.minute
        entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute

        if (stock_rs and bar_mins >= entry_mins and bar_mins <= entry_mins + 5
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
                stock_rs.sort(key=lambda x: x[1], reverse=True)

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
                    signals.append(Signal(sym, Direction.LONG, reason=f"v12 T{tier} +{rs:.1f}%"))
                    top_k -= 1

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
                    signals.append(Signal(sym, Direction.LONG, reason=f"v12 T{tier} dip {rs:.1f}%"))
                    bot_k -= 1

        return signals
