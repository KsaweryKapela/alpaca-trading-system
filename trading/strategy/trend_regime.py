"""Trend-Following Regime Overlay Strategy.

FUNDAMENTALLY DIFFERENT APPROACH — based on 10-year evidence.

THE CORE INSIGHT:
  Beating buy-and-hold on raw returns is nearly impossible for retail algo.
  The real edge is RISK-ADJUSTED: achieve similar returns with half the
  drawdown. The math: avoiding a -50% crash means you don't need +100% to
  recover. A -20% max DD with +10%/yr beats -55% DD with +12%/yr in practice
  because you can actually stay invested.

STRATEGY:
  This is NOT an alpha-extraction strategy. It's a REGIME-ADAPTIVE POSITION
  MANAGEMENT system that decides HOW MUCH to be invested, not WHAT to buy.

  REGIME DETECTION: SPY 200-day SMA (the most robust trend filter in
  academic literature — Faber 2007, Moskowitz et al 2012)

  BULL REGIME (SPY > 200-day SMA):
    - Full exposure: overnight longs on high-beta tech (proven edge)
    - Leverage: 2-3× (moderate — captures upside without excess risk)
    - Use the best overnight selection logic (RS-based, VGK tier-2)

  BEAR REGIME (SPY < 200-day SMA):
    - REDUCE to minimal exposure (not zero — avoids whipsaw)
    - No overnight longs (protect capital)
    - Optional: small RS short allocation (proven intraday edge)
    - Cash earns risk-free rate (implicit)

  TRANSITION BUFFER:
    - Don't switch on the exact SMA cross (whipsaw-prone)
    - Require N consecutive days below SMA before going defensive
    - Or use a buffer zone (SPY must be > X% below SMA)

WHY THIS SHOULD WORK OVER 10 YEARS:
  - 2015 (flat): defensive, avoids churn → ~0%
  - 2016-2017 (bull): fully invested, captures upside → ~+30%
  - 2018 (correction): goes defensive in Q4, avoids -20% DD → ~-5%
  - 2019-2020 (recovery): back to full, captures V-recovery → ~+80%
  - 2021 (peak): fully invested, captures final push → ~+50%
  - 2022 (crash): goes defensive, avoids -35% → ~-10%
  - 2023-2024 (recovery): back to full → ~+100%
  - Net: similar return to B&H, max DD ~-20% vs ~-55%

REQUIRES: eod_flatten=False for overnight holds. Need enough daily closes
to compute 200-day SMA (warm-up period).
"""

from collections import deque
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")

SIGNAL_ONLY = {"VGK", "EFA", "EWG", "FXI", "EWJ", "UVXY", "VXX", "VIXY"}


class TrendRegimeStrategy(Strategy):
    name = "trend_regime"
    label = "Trend-Following Regime Overlay"

    def __init__(
        self,
        symbols: List[str],
        # Regime detection
        sma_period: int = 200,           # SPY SMA period (trading days)
        buffer_pct: float = 0.0,         # require SPY this % below SMA to go bear
        confirm_days: int = 3,           # require N consecutive days below SMA
        # Bull sleeve: overnight longs
        bull_top_k: int = 4,
        bull_bottom_k: int = 4,
        overnight_stop_pct: float = 2.0,
        overnight_min_move: float = 0.3,
        overnight_entry_hour: int = 15,
        overnight_entry_minute: int = 30,
        overnight_exit_after_min: int = 20,
        # Bear sleeve: minimal exposure (optional RS shorts)
        bear_rs_enabled: bool = True,
        rs_threshold: float = 1.0,
        rs_stop_pct: float = 3.0,
        rs_target_pct: float = 3.0,
        rs_entry_after_min: int = 15,
        rs_entry_end_hour: int = 14,
        rs_close_hour: int = 15,
        rs_close_minute: int = 35,
        # Global signal for tier-2 nights
        global_signal_symbol: str = "VGK",
        global_min_return: float = 0.0,
        tier2_top_k: int = 2,
        tier2_bottom_k: int = 2,
    ) -> None:
        super().__init__(symbols)
        self.sma_period = sma_period
        self.buffer_pct = buffer_pct
        self.confirm_days = confirm_days
        self.bull_top_k = bull_top_k
        self.bull_bottom_k = bull_bottom_k
        self.overnight_stop_pct = overnight_stop_pct
        self.overnight_min_move = overnight_min_move
        self.overnight_entry_hour = overnight_entry_hour
        self.overnight_entry_minute = overnight_entry_minute
        self.overnight_exit_after_min = overnight_exit_after_min
        self.bear_rs_enabled = bear_rs_enabled
        self.rs_threshold = rs_threshold
        self.rs_stop_pct = rs_stop_pct
        self.rs_target_pct = rs_target_pct
        self.rs_entry_after_min = rs_entry_after_min
        self.rs_entry_end_hour = rs_entry_end_hour
        self.rs_close_hour = rs_close_hour
        self.rs_close_minute = rs_close_minute
        self.global_signal_symbol = global_signal_symbol
        self.global_min_return = global_min_return
        self.tier2_top_k = tier2_top_k
        self.tier2_bottom_k = tier2_bottom_k

        self._spy: dict = {}
        self._sym: Dict[str, dict] = {}
        self._signal_states: Dict[str, dict] = {}
        self._overnight_done_today = None
        self._regime: str = "unknown"  # "bull", "bear", "unknown"
        self._days_below_sma: int = 0

    def on_start(self) -> None:
        self._spy = {
            "current_date": None, "day_open": None,
            "vwap_num": 0.0, "vwap_den": 0.0, "vwap": None,
            "prev_close": None,
            "daily_closes": deque(maxlen=self.sma_period + 10),
            "sma": None,
        }
        self._sym = {}
        self._signal_states = {}
        self._overnight_done_today = None
        self._regime = "unknown"
        self._days_below_sma = 0

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
        r = [
            f"=== REGIME: SPY {self.sma_period}-day SMA ===",
            f"Bull: SPY > SMA (confirm {self.confirm_days} days)",
            f"Bear: SPY < SMA → protect capital",
            f"=== BULL SLEEVE (Overnight Longs) ===",
            f"{self.bull_top_k}+{self.bull_bottom_k} overnight, exit {self.overnight_exit_after_min}min",
            f"Tier-2: {self.global_signal_symbol} signal",
        ]
        if self.bear_rs_enabled:
            r.append(f"=== BEAR SLEEVE (RS Shorts, reduced) ===")
            r.append(f"RS < -{self.rs_threshold}% | Stop {self.rs_stop_pct}% | Target {self.rs_target_pct}%")
        else:
            r.append("=== BEAR SLEEVE: CASH (no trades) ===")
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

            # Compute SMA
            closes = list(spy["daily_closes"])
            if len(closes) >= self.sma_period:
                spy["sma"] = sum(closes[-self.sma_period:]) / self.sma_period

                # Update regime with confirmation
                last_close = closes[-1]
                threshold = spy["sma"] * (1 - self.buffer_pct / 100)

                if last_close < threshold:
                    self._days_below_sma += 1
                else:
                    self._days_below_sma = 0

                if self._days_below_sma >= self.confirm_days:
                    if self._regime == "bull":
                        # Transition: exit all overnight longs
                        for sym, st in self._sym.items():
                            if st["holding_overnight"]:
                                pos = portfolio.get_position(sym)
                                if pos and pos.quantity > 0:
                                    signals.append(Signal(sym, Direction.FLAT, reason="tr regime→bear"))
                                    st["holding_overnight"] = False
                                    st["position_type"] = None
                    self._regime = "bear"
                elif last_close > spy["sma"]:
                    self._regime = "bull"

        # VWAP (used for intraday bull/bear within regime)
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
        spy_bearish_vwap = spy["vwap"] is not None and spy_price < spy["vwap"]

        bar_mins = et_spy.hour * 60 + et_spy.minute
        open_mins = 9 * 60 + 30

        # Global signal
        global_return = None
        if self.global_signal_symbol in bars:
            global_return = self._update_signal(self.global_signal_symbol, bars[self.global_signal_symbol])

        # ── If regime unknown (warming up), do nothing ───────────────────
        if self._regime == "unknown":
            # Still track prev_close for symbols
            for symbol in self.symbols:
                if symbol in SIGNAL_ONLY or symbol == "SPY":
                    continue
                bar = bars.get(symbol)
                if bar and symbol not in self._sym:
                    self._sym[symbol] = self._fresh_sym()
                if bar:
                    st = self._sym[symbol]
                    if st["current_date"] != spy_today:
                        st["current_date"] = spy_today
                        st["day_open"] = bar.open
            return signals

        # Per-symbol processing
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
                    signals.append(Signal(symbol, Direction.FLAT, reason="tr stop"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                    continue
                if sym_bar_mins >= open_mins + self.overnight_exit_after_min:
                    signals.append(Signal(symbol, Direction.FLAT, reason="tr exit"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            # ── Manage RS short ──────────────────────────────────────────
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="tr RS stop"))
                    st["position_type"] = None
                elif st["target_level"] and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="tr RS target"))
                    st["position_type"] = None
                elif (et.hour > self.rs_close_hour or
                      (et.hour == self.rs_close_hour and et.minute >= self.rs_close_minute)):
                    signals.append(Signal(symbol, Direction.FLAT, reason="tr RS close"))
                    st["position_type"] = None
                continue

            # Same-day overnight stop
            if current_qty > 0 and st["holding_overnight"] and st["overnight_entry_date"] == today:
                if st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="tr stop (day)"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            if current_qty != 0:
                continue
            if not st["day_open"] or st["day_open"] == 0:
                continue

            stock_ret = (price - st["day_open"]) / st["day_open"] * 100
            rs = stock_ret - spy_return_pct if spy_return_pct is not None else 0

            # ── BEAR REGIME: RS shorts only (if enabled) ─────────────────
            if self._regime == "bear" and self.bear_rs_enabled:
                if (not st["rs_traded"] and spy_bearish_vwap
                        and sym_bar_mins >= open_mins + self.rs_entry_after_min
                        and et.hour < self.rs_entry_end_hour):
                    if rs < -self.rs_threshold:
                        st["rs_traded"] = True
                        st["stop_level"] = price * (1 + self.rs_stop_pct / 100)
                        st["target_level"] = price * (1 - self.rs_target_pct / 100) if self.rs_target_pct > 0 else None
                        st["position_type"] = "rs_short"
                        signals.append(Signal(symbol, Direction.SHORT, reason=f"tr RS={rs:.1f}%"))
                continue  # no overnight longs in bear

            # ── BULL REGIME: collect overnight candidates ─────────────────
            if self._regime == "bull":
                entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
                if (sym_bar_mins >= entry_mins and sym_bar_mins <= entry_mins + 5
                        and not st["overnight_traded"] and spy_return_pct is not None):
                    stock_rs.append((symbol, rs, price))

        # ── BULL REGIME: overnight entry ─────────────────────────────────
        if self._regime == "bull" and stock_rs:
            et = spy_bar.timestamp.astimezone(ET)
            today = et.date()
            bar_mins = et.hour * 60 + et.minute
            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute

            if (bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                    and self._overnight_done_today != today):

                self._overnight_done_today = today
                global_bullish = global_return is not None and global_return > self.global_min_return

                if spy_bullish_vwap:
                    top_k, bot_k, tier = self.bull_top_k, self.bull_bottom_k, 1
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
                        signals.append(Signal(sym, Direction.LONG, reason=f"tr T{tier} +{rs:.1f}%"))
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
                        signals.append(Signal(sym, Direction.LONG, reason=f"tr T{tier} dip {rs:.1f}%"))
                        bot_k -= 1

        return signals
