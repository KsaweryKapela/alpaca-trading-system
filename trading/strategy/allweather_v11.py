"""All-Weather v11: Enhanced Signal Quality.

Builds on v10 (margin overlay + 20-min exit) with three new signal features:

1. OVERNIGHT GAP QUALITY FILTER
   Research: small gaps (<1%) tend to continue; large gaps (>2%) tend to fade.
   At entry time (15:30), compute each stock's gap from prior close to today's open.
   - If stock gapped up >gap_fade_pct today AND is still near the gap level → skip (exhausted move)
   - If stock had a small positive gap AND continued → prefer (momentum confirmation)
   - Dip buys: prefer stocks that gapped DOWN then recovered intraday (mean-reversion setup)

2. DAILY EMA REGIME (higher-timeframe trend)
   Compute a rolling N-day EMA of SPY closing prices.
   - Bull regime: SPY > daily EMA → allow overnight longs
   - Bear regime: SPY < daily EMA → RS shorts only
   Replaces intraday VWAP as the regime filter (more stable, fewer whipsaws).
   Can be used IN ADDITION TO or INSTEAD OF the VWAP filter.

3. MARKET BREADTH FILTER
   At 15:30, count how many stocks in the universe are up vs down for the day.
   - Breadth ratio = up_count / total
   - Only enter overnight longs when breadth > threshold (e.g., 50%)
   - Filters out "narrow" rallies driven by 1-2 stocks

4. STOCK PERSONALITY: OVERNIGHT BETA
   Track each stock's average overnight gap size (close → next open).
   Prefer stocks with historically larger positive overnight gaps.

All features are optional flags — can be enabled/disabled individually.

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

# Sector mapping for sector-relative RS (future use)
SECTOR_MAP = {
    "NVDA": "XLK", "AAPL": "XLK", "MSFT": "XLK", "AMZN": "XLK",
    "META": "XLK", "GOOGL": "XLK", "AMD": "XLK", "NFLX": "XLK",
    "COIN": "XLK", "SHOP": "XLK", "PLTR": "XLK",
    "JPM": "XLF", "BA": "XLI",
    "TSLA": "XLY", "RIVN": "XLY",
}


class AllWeatherV11Strategy(Strategy):
    name = "allweather_v11"
    label = "All-Weather v11 (Enhanced Signals)"

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
        # Overnight longs
        overnight_top_k: int = 4,
        overnight_bottom_k: int = 4,
        overnight_stop_pct: float = 2.0,
        overnight_min_move: float = 0.3,
        overnight_entry_hour: int = 15,
        overnight_entry_minute: int = 30,
        overnight_exit_after_min: int = 20,  # v10 best = 20
        # Global signal
        global_signal_symbol: str = "VGK",
        global_min_return: float = 0.0,
        tier2_top_k: int = 2,
        tier2_bottom_k: int = 2,
        # === NEW: Gap quality filter ===
        gap_filter: bool = True,
        gap_fade_pct: float = 2.0,        # skip stocks that gapped up > this %
        gap_small_bonus: bool = True,      # prefer small-gap stocks for momentum
        # === NEW: Daily EMA regime ===
        use_daily_ema: bool = False,       # use daily EMA instead of VWAP for regime
        daily_ema_period: int = 20,        # EMA period in trading days
        # === NEW: Breadth filter ===
        breadth_filter: bool = True,
        breadth_min_pct: float = 45.0,     # min % of stocks up to allow longs
        # === NEW: Overnight personality ===
        use_overnight_beta: bool = True,   # prefer stocks with bigger avg overnight gaps
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
        self.gap_filter = gap_filter
        self.gap_fade_pct = gap_fade_pct
        self.gap_small_bonus = gap_small_bonus
        self.use_daily_ema = use_daily_ema
        self.daily_ema_period = daily_ema_period
        self.breadth_filter = breadth_filter
        self.breadth_min_pct = breadth_min_pct
        self.use_overnight_beta = use_overnight_beta

        self._spy: dict = {}
        self._sym: Dict[str, dict] = {}
        self._signal_states: Dict[str, dict] = {}
        self._overnight_done_today = None

    def on_start(self) -> None:
        self._spy = {
            "current_date": None, "day_open": None,
            "vwap_num": 0.0, "vwap_den": 0.0, "vwap": None,
            "prev_close": None,
            "daily_closes": deque(maxlen=max(self.spy_trend_days, self.daily_ema_period, 1) + 1),
            "daily_ema": None,
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
            # Gap tracking
            "prev_close": None,
            "today_gap_pct": None,  # open/prev_close - 1
            # Overnight personality
            "overnight_gaps": deque(maxlen=20),  # historical overnight gap sizes
            "avg_overnight_gap": 0.0,
        }

    def _fresh_signal(self) -> dict:
        return {"current_date": None, "day_open": None}

    def rules(self) -> List[str]:
        r = [
            "=== BEAR SLEEVE (RS Short — delayed close) ===",
            f"RS < -{self.rs_threshold}% | Close at {self.rs_close_hour}:{self.rs_close_minute:02d}",
            "=== BULL SLEEVE (Overnight — enhanced signals) ===",
            f"T1: {self.overnight_top_k}+{self.overnight_bottom_k} | T2: {self.tier2_top_k}+{self.tier2_bottom_k}",
            f"Exit {self.overnight_exit_after_min}min after open",
        ]
        if self.gap_filter:
            r.append(f"Gap filter: skip stocks gapped >{self.gap_fade_pct}% (exhausted)")
        if self.use_daily_ema:
            r.append(f"Regime: daily {self.daily_ema_period}-EMA (replaces VWAP)")
        if self.breadth_filter:
            r.append(f"Breadth: require >{self.breadth_min_pct}% stocks up")
        if self.use_overnight_beta:
            r.append("Stock personality: prefer high overnight-gap stocks")
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

    def _compute_ema(self, closes: list, period: int) -> Optional[float]:
        """Compute EMA from a list of daily closes."""
        if len(closes) < period:
            return None
        mult = 2.0 / (period + 1)
        ema = closes[0]
        for c in closes[1:]:
            ema = c * mult + ema * (1 - mult)
        return ema

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

            # Compute daily EMA
            if self.use_daily_ema:
                closes = list(spy["daily_closes"])
                if len(closes) >= self.daily_ema_period:
                    spy["daily_ema"] = self._compute_ema(closes, self.daily_ema_period)

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

        # Regime detection
        if self.use_daily_ema and spy["daily_ema"] is not None:
            spy_bullish = spy_price > spy["daily_ema"]
        else:
            spy_bullish = spy["vwap"] is not None and spy_price > spy["vwap"]

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

        # ── BREADTH: count stocks up vs down ─────────────────────────────
        stocks_up = 0
        stocks_total = 0
        tradable = [s for s in self.symbols if s not in SIGNAL_ONLY and s != "SPY"]

        # Per-symbol processing
        stock_rs: List[Tuple[str, float, float, float, float]] = []
        # (sym, rs, price, gap_score, overnight_beta)

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
                # Track overnight gap for personality
                if st["prev_close"] is not None and bar.open > 0:
                    gap_pct = (bar.open - st["prev_close"]) / st["prev_close"] * 100
                    st["overnight_gaps"].append(gap_pct)
                    if st["overnight_gaps"]:
                        st["avg_overnight_gap"] = sum(st["overnight_gaps"]) / len(st["overnight_gaps"])
                    st["today_gap_pct"] = gap_pct
                else:
                    st["today_gap_pct"] = None

                if not st["holding_overnight"]:
                    st["rs_traded"] = False
                    st["overnight_traded"] = False
                st["current_date"] = today
                st["day_open"] = bar.open

            price = bar.close
            st["prev_close"] = price

            # Breadth: is this stock up today?
            if st["day_open"] and st["day_open"] > 0:
                stocks_total += 1
                if price > st["day_open"]:
                    stocks_up += 1

            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0
            sym_bar_mins = et.hour * 60 + et.minute

            # ── Exit overnight longs ─────────────────────────────────────
            if st["holding_overnight"] and st["overnight_entry_date"] != today:
                if st["stop_level"] is not None and current_qty > 0 and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v11 stop"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                    continue
                if sym_bar_mins >= open_mins + self.overnight_exit_after_min:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v11 exit"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            # ── Manage RS short (delayed close) ──────────────────────────
            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v11 RS stop"))
                    st["position_type"] = None
                elif st["target_level"] and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v11 RS target"))
                    st["position_type"] = None
                elif (et.hour > self.rs_close_hour or
                      (et.hour == self.rs_close_hour and et.minute >= self.rs_close_minute)):
                    signals.append(Signal(symbol, Direction.FLAT, reason="v11 RS close"))
                    st["position_type"] = None
                continue

            # Same-day overnight stop
            if current_qty > 0 and st["holding_overnight"] and st["overnight_entry_date"] == today:
                if st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="v11 stop (day)"))
                    st["holding_overnight"] = False
                    st["position_type"] = None
                continue

            if current_qty != 0:
                continue
            if not st["day_open"] or st["day_open"] == 0:
                continue

            stock_ret = (price - st["day_open"]) / st["day_open"] * 100
            rs = stock_ret - spy_return_pct if spy_return_pct is not None else 0

            # ── Bear: RS short entry ─────────────────────────────────────
            if (not st["rs_traded"] and spy_bearish_full
                    and sym_bar_mins >= open_mins + self.rs_entry_after_min
                    and et.hour < self.rs_entry_end_hour):
                if rs < -self.rs_threshold:
                    st["rs_traded"] = True
                    st["stop_level"] = price * (1 + self.rs_stop_pct / 100)
                    st["target_level"] = price * (1 - self.rs_target_pct / 100) if self.rs_target_pct > 0 else None
                    st["position_type"] = "rs_short"
                    signals.append(Signal(symbol, Direction.SHORT, reason=f"v11 RS={rs:.1f}%"))
                continue

            # ── Bull: collect overnight candidates ───────────────────────
            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
            if (sym_bar_mins >= entry_mins and sym_bar_mins <= entry_mins + 5
                    and not st["overnight_traded"] and spy_return_pct is not None):

                # Gap quality score
                gap_score = 0.0
                if self.gap_filter and st["today_gap_pct"] is not None:
                    gap = st["today_gap_pct"]
                    if abs(gap) > self.gap_fade_pct:
                        gap_score = -1.0  # penalize large gaps (exhausted)
                    elif self.gap_small_bonus and 0 < gap < 1.0:
                        gap_score = 0.5   # small positive gap = momentum
                    elif gap < 0:
                        gap_score = 0.3   # gapped down then recovered = dip setup
                else:
                    gap_score = 0.0

                # Overnight beta (average historical gap)
                o_beta = st["avg_overnight_gap"] if self.use_overnight_beta else 0.0

                stock_rs.append((symbol, rs, price, gap_score, o_beta))

        # ── OVERNIGHT ENTRY ──────────────────────────────────────────────────
        sample = spy_bar
        et = sample.timestamp.astimezone(ET)
        today = et.date()
        bar_mins = et.hour * 60 + et.minute
        entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute

        if (stock_rs and bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                and self._overnight_done_today != today):

            self._overnight_done_today = today

            # Breadth check
            breadth_pct = (stocks_up / stocks_total * 100) if stocks_total > 0 else 50.0
            breadth_ok = not self.breadth_filter or breadth_pct >= self.breadth_min_pct

            global_bullish = global_return is not None and global_return > self.global_min_return

            if spy_bullish and breadth_ok:
                top_k = self.overnight_top_k
                bot_k = self.overnight_bottom_k
                tier = 1
            elif global_bullish and breadth_ok:
                top_k = self.tier2_top_k
                bot_k = self.tier2_bottom_k
                tier = 2
            else:
                top_k, bot_k, tier = 0, 0, 0

            if top_k > 0 or bot_k > 0:
                # Filter out exhausted-gap stocks
                if self.gap_filter:
                    stock_rs = [x for x in stock_rs if x[3] >= 0]  # remove gap_score < 0

                # Sort by composite score: RS + gap_score + overnight_beta
                # Winners: high RS, good gap, high overnight beta
                stock_rs.sort(key=lambda x: x[1] + x[3] * 0.5 + x[4] * 0.1, reverse=True)

                # Winners
                for sym, rs, px, gs, ob in stock_rs:
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
                    signals.append(Signal(sym, Direction.LONG, reason=f"v11 T{tier} +{rs:.1f}%"))
                    top_k -= 1

                # Dip buys (prefer stocks with negative gap but intraday recovery)
                losers = sorted(
                    [x for x in stock_rs if x[1] < -self.overnight_min_move],
                    key=lambda x: x[1] - x[3] * 0.5  # most negative RS, bonus for gap-down recovery
                )
                for sym, rs, px, gs, ob in losers:
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
                    signals.append(Signal(sym, Direction.LONG, reason=f"v11 T{tier} dip {rs:.1f}%"))
                    bot_k -= 1

        return signals
