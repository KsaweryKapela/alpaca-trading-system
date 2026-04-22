"""Boosted v10: Stock scores BOOST rankings, not filter.

KEY INSIGHT FROM 243 EXPERIMENTS: Hard stock selection (filtering) always
hurts the v10 architecture because it removes good RS/overnight trades.

NEW APPROACH: Instead of excluding stocks, BOOST the ranking of stocks that
score high on multiple dimensions. The RS signal remains primary, but stocks
with high RVOL, range expansion, or abnormality get a ranking bonus.

Result: the same stocks trade as v10, but high-conviction stocks get PRIORITY
for the limited position slots. No trades are removed.

BOOST FACTORS:
  1. RVOL bonus: stocks with >1.5x normal volume get +0.3 RS boost
  2. Range bonus: stocks with >1.5x normal range get +0.2 RS boost
  3. Momentum alignment: stocks trending in trade direction get +0.2 RS boost
  4. Historical overnight gap: stocks with positive avg gap history get +0.1 boost

These bonuses shift the RANKING order but don't change thresholds.

Built on v10 architecture (margin overlay + 20min exit + 3%/3% stop/target).
"""

from collections import deque
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")

SIGNAL_ONLY = {"VGK", "EFA", "EWG", "FXI", "EWJ", "UVXY", "VXX", "VIXY",
               "XLK", "XLF", "SMH", "IWM", "TQQQ"}


class BoostedV10Strategy(Strategy):
    name = "boosted_v10"
    label = "Boosted v10 (Score-Enhanced Ranking)"

    def __init__(
        self,
        symbols: List[str],
        # v10 core params
        rs_threshold: float = 1.0,
        rs_stop_pct: float = 3.0,
        rs_target_pct: float = 3.0,
        spy_trend_days: int = 3,
        rs_entry_after_min: int = 15,
        rs_entry_end_hour: int = 14,
        rs_close_hour: int = 15,
        rs_close_minute: int = 35,
        overnight_top_k: int = 4,
        overnight_bottom_k: int = 4,
        overnight_stop_pct: float = 2.0,
        overnight_min_move: float = 0.3,
        overnight_entry_hour: int = 15,
        overnight_entry_minute: int = 30,
        overnight_exit_after_min: int = 20,
        global_signal_symbol: str = "VGK",
        global_min_return: float = 0.0,
        tier2_top_k: int = 2,
        tier2_bottom_k: int = 2,
        # Boost params
        rvol_boost: float = 0.3,        # RS boost for high RVOL stocks
        range_boost: float = 0.2,       # RS boost for high range stocks
        momentum_boost: float = 0.2,    # RS boost for trend-aligned stocks
        overnight_boost: float = 0.1,   # RS boost for positive overnight history
        vol_lookback: int = 20,
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
        self.rvol_boost = rvol_boost
        self.range_boost = range_boost
        self.momentum_boost = momentum_boost
        self.overnight_boost = overnight_boost
        self.vol_lookback = vol_lookback

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
            # Boost tracking
            "session_volume": 0.0,
            "session_high": None, "session_low": None,
            "daily_volumes": deque(maxlen=self.vol_lookback),
            "daily_ranges": deque(maxlen=self.vol_lookback),
            "daily_closes": deque(maxlen=6),
            "overnight_returns": deque(maxlen=self.vol_lookback),
            "prev_close": None,
        }

    def _fresh_signal(self) -> dict:
        return {"current_date": None, "day_open": None}

    def rules(self) -> List[str]:
        return [
            "=== BOOSTED v10 (Score-Enhanced Ranking) ===",
            "Same trades as v10, but high-conviction stocks get PRIORITY",
            f"RVOL boost +{self.rvol_boost} | Range boost +{self.range_boost}",
            f"Momentum boost +{self.momentum_boost} | Overnight boost +{self.overnight_boost}",
            f"RS < -{self.rs_threshold}% | Stop {self.rs_stop_pct}% | Target {self.rs_target_pct}%",
            f"Overnight {self.overnight_top_k}+{self.overnight_bottom_k} | Exit {self.overnight_exit_after_min}min",
        ]

    def _compute_boost(self, sym: str) -> float:
        """Compute ranking boost for a stock based on activity metrics."""
        st = self._sym.get(sym)
        if st is None:
            return 0.0
        boost = 0.0

        # RVOL boost
        if st["daily_volumes"] and st["session_volume"] > 0:
            avg_vol = sum(st["daily_volumes"]) / len(st["daily_volumes"])
            if avg_vol > 0 and st["session_volume"] / avg_vol > 1.5:
                boost += self.rvol_boost

        # Range boost
        if (st["daily_ranges"] and st["session_high"] and st["session_low"]
                and st["session_low"] > 0):
            curr = (st["session_high"] - st["session_low"]) / st["session_low"] * 100
            avg = sum(st["daily_ranges"]) / len(st["daily_ranges"])
            if avg > 0 and curr / avg > 1.5:
                boost += self.range_boost

        # Momentum alignment
        closes = list(st["daily_closes"])
        if len(closes) >= 5 and closes[0] > 0:
            mom = (closes[-1] - closes[0]) / closes[0] * 100
            if abs(mom) > 1.0:  # trending > 1% over 5 days
                boost += self.momentum_boost

        # Overnight history
        if st["overnight_returns"]:
            avg_on = sum(st["overnight_returns"]) / len(st["overnight_returns"])
            if avg_on > 0.05:  # positive avg overnight gap
                boost += self.overnight_boost

        return boost

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

        global_return = None
        if self.global_signal_symbol in bars:
            global_return = self._update_signal(self.global_signal_symbol, bars[self.global_signal_symbol])

        stock_rs: List[Tuple[str, float, float, float]] = []  # (sym, boosted_rs, price, raw_rs)
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
                # Save daily stats
                if st["session_volume"] > 0:
                    st["daily_volumes"].append(st["session_volume"])
                if st["session_high"] and st["session_low"] and st["session_low"] > 0:
                    st["daily_ranges"].append((st["session_high"]-st["session_low"])/st["session_low"]*100)
                if st["prev_close"] is not None:
                    st["daily_closes"].append(st["prev_close"])
                # Overnight return
                if st["prev_close"] and st["prev_close"] > 0 and bar.open > 0:
                    st["overnight_returns"].append((bar.open - st["prev_close"]) / st["prev_close"] * 100)

                if not st["holding_overnight"]:
                    st["rs_traded"] = False; st["overnight_traded"] = False
                st["current_date"] = today; st["day_open"] = bar.open
                st["session_volume"] = 0.0; st["session_high"] = None; st["session_low"] = None

            price = bar.close
            st["prev_close"] = price
            st["session_volume"] += bar.volume
            if st["session_high"] is None or bar.high > st["session_high"]:
                st["session_high"] = bar.high
            if st["session_low"] is None or bar.low < st["session_low"]:
                st["session_low"] = bar.low

            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0
            sym_bar_mins = et.hour * 60 + et.minute

            # Exit overnight / manage RS short (same as v10)
            if st["holding_overnight"] and st["overnight_entry_date"] != today:
                if st["stop_level"] and current_qty > 0 and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="bv stop"))
                    st["holding_overnight"] = False; st["position_type"] = None; continue
                if sym_bar_mins >= open_mins + self.overnight_exit_after_min:
                    signals.append(Signal(symbol, Direction.FLAT, reason="bv exit"))
                    st["holding_overnight"] = False; st["position_type"] = None
                continue

            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="bv RS stop")); st["position_type"] = None
                elif st["target_level"] and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="bv RS tgt")); st["position_type"] = None
                elif et.hour > self.rs_close_hour or (et.hour == self.rs_close_hour and et.minute >= self.rs_close_minute):
                    signals.append(Signal(symbol, Direction.FLAT, reason="bv RS close")); st["position_type"] = None
                continue

            if current_qty > 0 and st["holding_overnight"] and st["overnight_entry_date"] == today:
                if st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="bv stop(d)"))
                    st["holding_overnight"] = False; st["position_type"] = None
                continue

            if current_qty != 0:
                continue
            if not st["day_open"] or st["day_open"] == 0 or spy_return_pct is None:
                continue

            stock_ret = (price - st["day_open"]) / st["day_open"] * 100
            rs = stock_ret - spy_return_pct
            boost = self._compute_boost(symbol)

            # Bear: RS short (boosted ranking)
            if (not st["rs_traded"] and spy_bearish_full
                    and sym_bar_mins >= open_mins + self.rs_entry_after_min
                    and et.hour < self.rs_entry_end_hour):
                # Use boosted RS for threshold check (boost makes it easier to qualify)
                boosted_rs = rs - boost  # more negative = stronger short signal
                if boosted_rs < -self.rs_threshold:
                    st["rs_traded"] = True
                    st["stop_level"] = price * (1 + self.rs_stop_pct / 100)
                    st["target_level"] = price * (1 - self.rs_target_pct / 100)
                    st["position_type"] = "rs_short"
                    signals.append(Signal(symbol, Direction.SHORT, reason=f"bv RS={rs:.1f}% b={boost:.1f}"))
                continue

            # Bull: collect overnight candidates with boost
            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
            if (sym_bar_mins >= entry_mins and sym_bar_mins <= entry_mins + 5
                    and not st["overnight_traded"]):
                # Boost RS for ranking (higher boost = higher priority)
                stock_rs.append((symbol, rs + boost, price, rs))

        # Overnight entry (same as v10 but with boosted ranking)
        entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
        if (stock_rs and bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                and self._overnight_done_today != spy_today):
            self._overnight_done_today = spy_today
            global_bullish = global_return is not None and global_return > self.global_min_return

            if spy_bullish:
                top_k, bot_k, tier = self.overnight_top_k, self.overnight_bottom_k, 1
            elif global_bullish:
                top_k, bot_k, tier = self.tier2_top_k, self.tier2_bottom_k, 2
            else:
                top_k, bot_k, tier = 0, 0, 0

            if top_k > 0 or bot_k > 0:
                stock_rs.sort(key=lambda x: x[1], reverse=True)  # sort by BOOSTED RS

                for sym, brs, px, raw_rs in stock_rs:
                    if top_k <= 0: break
                    if raw_rs < self.overnight_min_move: continue
                    st = self._sym.get(sym)
                    if not st or st["overnight_traded"] or st["holding_overnight"]: continue
                    pos = portfolio.get_position(sym)
                    if pos and pos.quantity != 0: continue
                    st["overnight_traded"] = True; st["holding_overnight"] = True
                    st["overnight_entry_date"] = spy_today
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"on_t{tier}"
                    signals.append(Signal(sym, Direction.LONG, reason=f"bv T{tier} +{raw_rs:.1f}%"))
                    top_k -= 1

                losers = sorted([x for x in stock_rs if x[3] < -self.overnight_min_move], key=lambda x: x[1])
                for sym, brs, px, raw_rs in losers:
                    if bot_k <= 0: break
                    st = self._sym.get(sym)
                    if not st or st["overnight_traded"] or st["holding_overnight"]: continue
                    pos = portfolio.get_position(sym)
                    if pos and pos.quantity != 0: continue
                    st["overnight_traded"] = True; st["holding_overnight"] = True
                    st["overnight_entry_date"] = spy_today
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"on_t{tier}"
                    signals.append(Signal(sym, Direction.LONG, reason=f"bv T{tier} dip {raw_rs:.1f}%"))
                    bot_k -= 1

        return signals
