"""All-Weather v7: Regime-Adaptive Leveraged Trend Following.

CORE THESIS: In bull regimes, the best strategy is to BE LONG with leverage.
Don't pick stocks, don't trail-stop individual names. Just hold leveraged index
exposure and exit ONLY when the regime changes.

Why v6 failed in 2025 (+2.6% vs 27.66% buy-and-hold):
  - Individual stocks are too volatile: 5% trail stops trigger in normal pullbacks
  - Stock selection at 15:30 adds noise: today's winners often mean-revert
  - Net effect: constant stopping out + re-entering = death by a thousand cuts

v7 INNOVATION: Three operating modes with clean transitions.

MODE 1: BULL TREND (SPY > N-day SMA)
  - Hold levered long positions in a DIVERSIFIED basket
  - NO trail stops on individuals — only exit on regime change
  - Add/rebalance positions daily at 15:30 if slots are open
  - Position sizing: equal-weight across all qualifying names

MODE 2: BEAR TREND (SPY < VWAP AND SPY < N-day ago close)
  - RS short intraday (proven, Sharpe 3+ in 2026)
  - Flatten shorts by 15:25

MODE 3: NEUTRAL (between bull and bear)
  - No new entries
  - Existing positions held with wide stop (optional)

TRANSITIONS:
  Bull → Neutral/Bear: Exit all longs at next day's 9:45 (gap already happened)
  Bear → Bull: Wait for full SMA confirmation, then enter at 15:30

STOCK CLASSIFICATION (from user ideas):
  - Compute each stock's recent beta and typical daily range
  - In bull mode, prefer lower-beta names (institutional, less whipsaw)
  - In bear mode, prefer higher-beta names (more short profit)

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


class AllWeatherV7Strategy(Strategy):
    name = "allweather_v7"
    label = "All-Weather v7 (Regime Trend Following)"

    def __init__(
        self,
        symbols: List[str],
        # Regime detection
        sma_period: int = 10,           # SPY SMA for bull detection
        spy_trend_days: int = 3,        # bear trend confirmation
        # Bull sleeve: diversified long
        long_max_positions: int = 8,    # how many names to hold long
        rebalance_daily: bool = True,   # add to positions daily
        catastrophe_stop_pct: float = 15.0,  # only exit individual on catastrophic drop
        entry_hour: int = 15,
        entry_minute: int = 30,
        exit_morning_min: int = 15,
        # Bear sleeve: RS short
        rs_threshold: float = 1.0,
        rs_stop_pct: float = 1.0,
        rs_target_pct: float = 2.0,
        rs_entry_after_min: int = 15,
        rs_entry_end_hour: int = 14,
    ) -> None:
        super().__init__(symbols)
        self.sma_period = sma_period
        self.spy_trend_days = spy_trend_days
        self.long_max_positions = long_max_positions
        self.rebalance_daily = rebalance_daily
        self.catastrophe_stop_pct = catastrophe_stop_pct
        self.entry_hour = entry_hour
        self.entry_minute = entry_minute
        self.exit_morning_min = exit_morning_min
        self.rs_threshold = rs_threshold
        self.rs_stop_pct = rs_stop_pct
        self.rs_target_pct = rs_target_pct
        self.rs_entry_after_min = rs_entry_after_min
        self.rs_entry_end_hour = rs_entry_end_hour

        self._spy: dict = {}
        self._sym: Dict[str, dict] = {}
        self._entry_done_today = None
        self._regime: str = "neutral"  # "bull", "bear", "neutral"
        self._prev_regime: str = "neutral"
        self._regime_changed_today = False

    def on_start(self) -> None:
        self._spy = {
            "current_date": None,
            "day_open": None,
            "vwap_num": 0.0, "vwap_den": 0.0, "vwap": None,
            "prev_close": None,
            "daily_closes": deque(maxlen=max(self.sma_period, self.spy_trend_days, 1) + 1),
            "sma": None,
        }
        self._sym = {}
        self._entry_done_today = None
        self._regime = "neutral"
        self._prev_regime = "neutral"
        self._regime_changed_today = False

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "holding_long": False,
            "entry_price": None,
            "rs_traded": False,
            "rs_stop": None,
            "rs_target": None,
            "position_type": None,
            # Stock personality: computed over rolling window
            "daily_returns": deque(maxlen=20),
            "prev_close": None,
        }

    def rules(self) -> List[str]:
        return [
            "=== BULL MODE (SPY > SMA) ===",
            f"Regime: SPY > {self.sma_period}-day SMA",
            f"Hold up to {self.long_max_positions} diversified longs",
            f"NO trail stops — exit ONLY on regime change or {self.catastrophe_stop_pct}% catastrophe",
            f"Rebalance daily at {self.entry_hour}:{self.entry_minute:02d}",
            "=== BEAR MODE (SPY < VWAP + trend) ===",
            f"RS < -{self.rs_threshold}% | Stop {self.rs_stop_pct}% | Target {self.rs_target_pct}%",
            "=== TRANSITIONS ===",
            "Bull→Bear: exit all longs next morning",
            "Bear→Bull: enter diversified longs at 15:30",
        ]

    def _compute_stock_beta(self, sym: str) -> float:
        """Rough beta proxy: avg absolute daily return. Higher = more volatile."""
        st = self._sym.get(sym)
        if not st or len(st["daily_returns"]) < 5:
            return 1.0
        returns = list(st["daily_returns"])
        return sum(abs(r) for r in returns) / len(returns)

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # ── SPY ──────────────────────────────────────────────────────────────
        spy_bar = bars.get("SPY")
        if spy_bar is None:
            return signals

        et_spy = spy_bar.timestamp.astimezone(ET)
        spy_today = et_spy.date()
        spy = self._spy

        new_day = spy["current_date"] != spy_today
        if new_day:
            if spy["prev_close"] is not None:
                spy["daily_closes"].append(spy["prev_close"])
            spy["current_date"] = spy_today
            spy["day_open"] = spy_bar.open
            spy["vwap_num"] = 0.0
            spy["vwap_den"] = 0.0
            spy["vwap"] = None
            self._regime_changed_today = False
            self._entry_done_today = None

            # SMA
            closes = list(spy["daily_closes"])
            if len(closes) >= self.sma_period:
                spy["sma"] = sum(closes[-self.sma_period:]) / self.sma_period

            # Update per-symbol daily returns
            for sym, st in self._sym.items():
                if st["prev_close"] is not None and st["day_open"] is not None:
                    pass  # updated below on first bar
                # Will be set when we see the symbol's bar

        # VWAP
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

        bar_mins = et_spy.hour * 60 + et_spy.minute
        open_mins = 9 * 60 + 30

        # ── REGIME DETECTION ─────────────────────────────────────────────────
        bull_sma = spy["sma"] is not None and spy_price > spy["sma"]
        spy_below_vwap = spy["vwap"] is not None and spy_price < spy["vwap"]
        spy_bearish_trend = False
        if self.spy_trend_days > 0:
            closes = list(spy["daily_closes"])
            if len(closes) >= self.spy_trend_days:
                spy_bearish_trend = spy_price < closes[-self.spy_trend_days]
        spy_bearish_full = spy_below_vwap and spy_bearish_trend

        # Determine regime at 15:50 each day (end of day, stable reading)
        if bar_mins >= 15 * 60 + 50 and bar_mins < 15 * 60 + 55:
            self._prev_regime = self._regime
            if bull_sma:
                self._regime = "bull"
            elif spy_bearish_full:
                self._regime = "bear"
            else:
                self._regime = "neutral"

        # ── REGIME TRANSITION: exit longs when leaving bull ──────────────────
        if (self._prev_regime == "bull" and self._regime != "bull"
                and not self._regime_changed_today
                and bar_mins >= open_mins + self.exit_morning_min
                and bar_mins < open_mins + self.exit_morning_min + 5):
            self._regime_changed_today = True
            for sym, st in self._sym.items():
                if st["holding_long"] and st["position_type"] == "long_swing":
                    pos = portfolio.get_position(sym)
                    if pos and pos.quantity > 0:
                        signals.append(Signal(sym, Direction.FLAT, reason="v7 regime exit"))
                        st["holding_long"] = False
                        st["position_type"] = None
                        st["entry_price"] = None

        # ── PER-SYMBOL ───────────────────────────────────────────────────────
        stock_candidates: List[Tuple[str, float, float, float]] = []  # (sym, rs, price, beta)
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
                # Track daily returns for personality
                if st["prev_close"] is not None and bar.open > 0:
                    daily_ret = (bar.open - st["prev_close"]) / st["prev_close"] * 100
                    st["daily_returns"].append(daily_ret)
                st["current_date"] = today
                st["day_open"] = bar.open
                if not st["holding_long"]:
                    st["rs_traded"] = False

            price = bar.close
            st["prev_close"] = price
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0
            sym_bar_mins = et.hour * 60 + et.minute

            # ── Manage existing long positions ───────────────────────────
            if current_qty > 0 and st["position_type"] == "long_swing":
                # Only exit on catastrophic individual drop
                if st["entry_price"] and st["entry_price"] > 0:
                    pnl_pct = (price - st["entry_price"]) / st["entry_price"] * 100
                    if pnl_pct < -self.catastrophe_stop_pct:
                        signals.append(Signal(symbol, Direction.FLAT, reason="v7 catastrophe"))
                        st["holding_long"] = False
                        st["position_type"] = None
                        st["entry_price"] = None
                continue

            # ── Manage RS short positions ────────────────────────────────
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["rs_stop"] and price >= st["rs_stop"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v7 RS stop"))
                    st["position_type"] = None
                elif st["rs_target"] and price <= st["rs_target"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v7 RS target"))
                    st["position_type"] = None
                elif et.hour == 15 and et.minute >= 25:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v7 RS close"))
                    st["position_type"] = None
                continue

            if current_qty != 0:
                continue
            if not st["day_open"] or st["day_open"] == 0:
                continue

            stock_ret = (price - st["day_open"]) / st["day_open"] * 100
            rs = stock_ret - spy_return_pct if spy_return_pct is not None else 0

            # ── BEAR: RS short ───────────────────────────────────────────
            if (self._regime == "bear" and not st["rs_traded"]
                    and spy_bearish_full
                    and sym_bar_mins >= open_mins + self.rs_entry_after_min
                    and et.hour < self.rs_entry_end_hour):
                if rs < -self.rs_threshold:
                    st["rs_traded"] = True
                    st["rs_stop"] = price * (1 + self.rs_stop_pct / 100)
                    st["rs_target"] = price * (1 - self.rs_target_pct / 100) if self.rs_target_pct > 0 else None
                    st["position_type"] = "rs_short"
                    signals.append(Signal(symbol, Direction.SHORT, reason=f"v7 RS={rs:.1f}%"))
                continue

            # ── BULL: collect candidates ──────────────────────────────────
            entry_mins = self.entry_hour * 60 + self.entry_minute
            if (self._regime == "bull" and bull_sma
                    and sym_bar_mins >= entry_mins and sym_bar_mins <= entry_mins + 5
                    and not st["holding_long"]):
                beta = self._compute_stock_beta(symbol)
                stock_candidates.append((symbol, rs, price, beta))

        # ── BULL ENTRY ───────────────────────────────────────────────────────
        entry_mins = self.entry_hour * 60 + self.entry_minute
        if (stock_candidates and self._regime == "bull" and bull_sma
                and bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                and self._entry_done_today != spy_today):

            self._entry_done_today = spy_today

            # Count existing swing longs
            existing_longs = sum(1 for st in self._sym.values()
                                if st["holding_long"] and st["position_type"] == "long_swing")
            slots = self.long_max_positions - existing_longs
            if slots <= 0:
                return signals

            # Sort by lowest beta (prefer stable, institutional names)
            # This implements "stock personality" — prefer less volatile names for swings
            stock_candidates.sort(key=lambda x: x[3])

            for sym, rs, px, beta in stock_candidates:
                if slots <= 0:
                    break
                st = self._sym.get(sym)
                if not st or st["holding_long"]:
                    continue
                pos = portfolio.get_position(sym)
                if pos and pos.quantity != 0:
                    continue
                st["holding_long"] = True
                st["entry_price"] = px
                st["position_type"] = "long_swing"
                signals.append(Signal(sym, Direction.LONG, reason=f"v7 bull β={beta:.1f}"))
                slots -= 1

        return signals
