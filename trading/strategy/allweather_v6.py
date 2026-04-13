"""All-Weather v6: Multi-Day Trend Rider.

KEY INNOVATION: In bull regimes, HOLD long positions for multiple days instead
of exiting 15 minutes after open. This captures the full directional trend
(not just overnight gaps), which is where most of the bull-market return lives.

Why previous strategies capped at ~10% in 2025:
  - Overnight strategies exit at 9:45, missing regular-session continuation
  - In a +27.66% year, regular-session returns are ~60% of total
  - By holding multi-day, we capture close-to-close returns, not just overnight

Architecture:
  BULL MODE (SPY > N-day SMA):
    - At 15:30, buy top-K momentum winners + bottom-K dip buys
    - HOLD positions across days until:
      a) SPY closes below N-day SMA → exit ALL longs next morning
      b) Individual trailing stop hit (trail_pct% from peak)
      c) Position held > max_hold_days
    - Rebalance daily: add new positions if slots freed up

  BEAR MODE (SPY < VWAP AND SPY < N-day ago close):
    - RS short intraday (proven, unchanged from 069 base)
    - All shorts flatten by 15:25

  TRANSITION:
    - When SPY crosses below SMA: exit all longs next morning (9:45)
    - When SPY crosses above SMA: begin building long book at 15:30
    - No overlap: shorts only fire when SPY < VWAP + 3d trend

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


class AllWeatherV6Strategy(Strategy):
    name = "allweather_v6"
    label = "All-Weather v6 (Multi-Day Trend Rider)"

    def __init__(
        self,
        symbols: List[str],
        # Bull regime detection
        sma_period: int = 5,            # SPY SMA period (trading days)
        # Multi-day long positions
        long_top_k: int = 3,            # top winners to buy
        long_bottom_k: int = 3,         # bottom dip-buys
        trail_stop_pct: float = 3.0,    # trailing stop from peak
        max_hold_days: int = 15,        # force exit after N days
        min_rs_entry: float = 0.3,      # min RS move to qualify for entry
        entry_hour: int = 15,
        entry_minute: int = 30,
        exit_morning_min: int = 15,     # exit longs this many min after open on regime change
        # Bear sleeve (RS short)
        rs_threshold: float = 1.0,
        rs_stop_pct: float = 1.0,
        rs_target_pct: float = 2.0,
        spy_trend_days: int = 3,
        rs_entry_after_min: int = 15,
        rs_entry_end_hour: int = 14,
    ) -> None:
        super().__init__(symbols)
        self.sma_period = sma_period
        self.long_top_k = long_top_k
        self.long_bottom_k = long_bottom_k
        self.trail_stop_pct = trail_stop_pct
        self.max_hold_days = max_hold_days
        self.min_rs_entry = min_rs_entry
        self.entry_hour = entry_hour
        self.entry_minute = entry_minute
        self.exit_morning_min = exit_morning_min
        self.rs_threshold = rs_threshold
        self.rs_stop_pct = rs_stop_pct
        self.rs_target_pct = rs_target_pct
        self.spy_trend_days = spy_trend_days
        self.rs_entry_after_min = rs_entry_after_min
        self.rs_entry_end_hour = rs_entry_end_hour

        # State
        self._spy: dict = {}
        self._sym: Dict[str, dict] = {}
        self._entry_done_today = None
        self._prev_bull = False  # was bull regime yesterday?

    def on_start(self) -> None:
        self._spy = {
            "current_date": None,
            "day_open": None,
            "vwap_num": 0.0,
            "vwap_den": 0.0,
            "vwap": None,
            "prev_close": None,
            "daily_closes": deque(maxlen=max(self.sma_period, self.spy_trend_days, 1) + 1),
            "sma": None,
        }
        self._sym = {}
        self._entry_done_today = None
        self._prev_bull = False

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            # Long multi-day state
            "holding_long": False,
            "long_entry_date": None,
            "long_hold_days": 0,
            "peak_price": None,
            "trail_stop": None,
            # RS short state
            "rs_traded": False,
            "rs_stop": None,
            "rs_target": None,
            "position_type": None,  # "long_swing", "rs_short"
        }

    def rules(self) -> List[str]:
        return [
            "=== BULL SLEEVE (Multi-Day Trend Rider) ===",
            f"Regime: SPY > {self.sma_period}-day SMA",
            f"Entry: top {self.long_top_k} winners + bottom {self.long_bottom_k} dip buys at {self.entry_hour}:{self.entry_minute:02d}",
            f"Hold multi-day, trail stop {self.trail_stop_pct}%, max {self.max_hold_days} days",
            f"Exit ALL when SPY < SMA (regime switch)",
            "=== BEAR SLEEVE (RS Short, Intraday) ===",
            f"RS < -{self.rs_threshold}% on bearish sessions (VWAP + {self.spy_trend_days}d trend)",
            f"Stop {self.rs_stop_pct}% | Target {self.rs_target_pct}% | Flatten by 15:25",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # ── SPY state ────────────────────────────────────────────────────────
        spy_bar = bars.get("SPY")
        if spy_bar is None:
            return signals

        et_spy = spy_bar.timestamp.astimezone(ET)
        spy_today = et_spy.date()
        spy = self._spy

        if spy["current_date"] != spy_today:
            # New day: update daily closes, compute SMA
            if spy["prev_close"] is not None:
                spy["daily_closes"].append(spy["prev_close"])
            spy["current_date"] = spy_today
            spy["day_open"] = spy_bar.open
            spy["vwap_num"] = 0.0
            spy["vwap_den"] = 0.0
            spy["vwap"] = None

            # Compute SMA from daily closes
            closes = list(spy["daily_closes"])
            if len(closes) >= self.sma_period:
                spy["sma"] = sum(closes[-self.sma_period:]) / self.sma_period
            else:
                spy["sma"] = None

            # Increment hold days for all swing positions
            for sym, st in self._sym.items():
                if st["holding_long"]:
                    st["long_hold_days"] += 1

        # Update VWAP
        typical = (spy_bar.high + spy_bar.low + spy_bar.close) / 3
        spy["vwap_num"] += typical * spy_bar.volume
        spy["vwap_den"] += spy_bar.volume
        if spy["vwap_den"] > 0:
            spy["vwap"] = spy["vwap_num"] / spy["vwap_den"]

        spy_price = spy_bar.close
        spy["prev_close"] = spy_price

        # Regime signals
        bull_sma = spy["sma"] is not None and spy_price > spy["sma"]
        spy_return_pct = None
        if spy["day_open"] and spy["day_open"] > 0:
            spy_return_pct = (spy_price - spy["day_open"]) / spy["day_open"] * 100

        spy_below_vwap = spy["vwap"] is not None and spy_price < spy["vwap"]
        spy_bearish_trend = False
        if self.spy_trend_days > 0 and spy_price is not None:
            closes = list(spy["daily_closes"])
            if len(closes) >= self.spy_trend_days:
                spy_bearish_trend = spy_price < closes[-self.spy_trend_days]
        spy_bearish_full = spy_below_vwap and spy_bearish_trend

        bar_mins = et_spy.hour * 60 + et_spy.minute
        open_mins = 9 * 60 + 30

        # ── Regime switch: exit all longs if bull → bear ─────────────────────
        if self._prev_bull and not bull_sma:
            # SMA crossed below — exit all longs in the morning
            if bar_mins >= open_mins + self.exit_morning_min and bar_mins < open_mins + self.exit_morning_min + 5:
                for sym, st in self._sym.items():
                    if st["holding_long"] and st["position_type"] == "long_swing":
                        pos = portfolio.get_position(sym)
                        if pos and pos.quantity > 0:
                            signals.append(Signal(sym, Direction.FLAT, reason="v6 regime→bear"))
                            st["holding_long"] = False
                            st["position_type"] = None
                            st["peak_price"] = None
                            st["trail_stop"] = None

        # Update prev_bull at end of day (15:55)
        if bar_mins >= 15 * 60 + 55:
            self._prev_bull = bull_sma

        # ── Per-symbol processing ────────────────────────────────────────────
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
                st["current_date"] = today
                st["day_open"] = bar.open
                if not st["holding_long"]:
                    st["rs_traded"] = False

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0
            sym_bar_mins = et.hour * 60 + et.minute

            # ── Manage existing long swing positions ─────────────────────
            if current_qty > 0 and st["position_type"] == "long_swing":
                # Update trailing stop
                if st["peak_price"] is None or price > st["peak_price"]:
                    st["peak_price"] = price
                    st["trail_stop"] = price * (1 - self.trail_stop_pct / 100)

                # Check trailing stop
                if st["trail_stop"] and price <= st["trail_stop"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason=f"v6 trail stop"))
                    st["holding_long"] = False
                    st["position_type"] = None
                    st["peak_price"] = None
                    st["trail_stop"] = None
                    continue

                # Check max hold period
                if st["long_hold_days"] >= self.max_hold_days:
                    signals.append(Signal(symbol, Direction.FLAT, reason=f"v6 max hold"))
                    st["holding_long"] = False
                    st["position_type"] = None
                    st["peak_price"] = None
                    st["trail_stop"] = None
                    continue

                continue  # holding, no new signals

            # ── Manage RS short positions ────────────────────────────────
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["rs_stop"] and price >= st["rs_stop"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v6 RS stop"))
                    st["position_type"] = None
                elif st["rs_target"] and price <= st["rs_target"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v6 RS target"))
                    st["position_type"] = None
                elif et.hour == 15 and et.minute >= 25:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v6 RS close"))
                    st["position_type"] = None
                continue

            if current_qty != 0:
                continue
            if not st["day_open"] or st["day_open"] == 0:
                continue

            stock_ret = (price - st["day_open"]) / st["day_open"] * 100
            rs = stock_ret - spy_return_pct if spy_return_pct is not None else 0

            # ── BEAR SLEEVE: RS short entry ──────────────────────────────
            if (not st["rs_traded"] and spy_bearish_full
                    and not bull_sma  # never short in bull regime
                    and sym_bar_mins >= open_mins + self.rs_entry_after_min
                    and et.hour < self.rs_entry_end_hour):
                if rs < -self.rs_threshold:
                    st["rs_traded"] = True
                    st["rs_stop"] = price * (1 + self.rs_stop_pct / 100)
                    st["rs_target"] = price * (1 - self.rs_target_pct / 100) if self.rs_target_pct > 0 else None
                    st["position_type"] = "rs_short"
                    signals.append(Signal(symbol, Direction.SHORT, reason=f"v6 RS={rs:.1f}%"))
                continue

            # ── BULL SLEEVE: collect candidates for multi-day entry ───────
            entry_mins = self.entry_hour * 60 + self.entry_minute
            if (bull_sma and sym_bar_mins >= entry_mins and sym_bar_mins <= entry_mins + 5
                    and not st["holding_long"] and spy_return_pct is not None):
                stock_rs.append((symbol, rs, price))

        # ── BULL ENTRY: top-K winners + bottom-K dip buys ────────────────────
        sample = spy_bar
        et = sample.timestamp.astimezone(ET)
        today = et.date()
        bar_mins = et.hour * 60 + et.minute
        entry_mins = self.entry_hour * 60 + self.entry_minute

        if (stock_rs and bull_sma
                and bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                and self._entry_done_today != today):

            self._entry_done_today = today
            stock_rs.sort(key=lambda x: x[1], reverse=True)

            # Top-K winners (positive momentum)
            top_k = self.long_top_k
            for sym, rs, px in stock_rs:
                if top_k <= 0:
                    break
                if rs < self.min_rs_entry:
                    continue
                st = self._sym.get(sym)
                if not st or st["holding_long"]:
                    continue
                pos = portfolio.get_position(sym)
                if pos and pos.quantity != 0:
                    continue
                st["holding_long"] = True
                st["long_entry_date"] = today
                st["long_hold_days"] = 0
                st["peak_price"] = px
                st["trail_stop"] = px * (1 - self.trail_stop_pct / 100)
                st["position_type"] = "long_swing"
                signals.append(Signal(sym, Direction.LONG, reason=f"v6 swing +{rs:.1f}%"))
                top_k -= 1

            # Bottom-K dip buys (reversal)
            losers = sorted([x for x in stock_rs if x[1] < -self.min_rs_entry], key=lambda x: x[1])
            bot_k = self.long_bottom_k
            for sym, rs, px in losers:
                if bot_k <= 0:
                    break
                st = self._sym.get(sym)
                if not st or st["holding_long"]:
                    continue
                pos = portfolio.get_position(sym)
                if pos and pos.quantity != 0:
                    continue
                st["holding_long"] = True
                st["long_entry_date"] = today
                st["long_hold_days"] = 0
                st["peak_price"] = px
                st["trail_stop"] = px * (1 - self.trail_stop_pct / 100)
                st["position_type"] = "long_swing"
                signals.append(Signal(sym, Direction.LONG, reason=f"v6 dip {rs:.1f}%"))
                bot_k -= 1

        return signals
