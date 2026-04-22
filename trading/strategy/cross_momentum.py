"""Cross-Sectional Momentum: Pure Stock Selection Strategy.

GENUINELY DIFFERENT: Selection IS the strategy. No regime filters, no RS
thresholds, no VWAP — just rank stocks by multi-day momentum and trade
the extremes.

THESIS: Stocks with the strongest 5-day momentum tend to continue overnight.
Stocks with the weakest 5-day momentum tend to continue falling. This is
the Jegadeesh-Titman momentum effect applied at short-term frequency.

HOW IT WORKS:
  1. At 15:30, compute 5-day return for ALL stocks in the universe
  2. Rank from highest to lowest
  3. LONG the top-K (strongest momentum) → overnight hold
  4. SHORT the bottom-K (weakest momentum) → overnight hold
  5. Exit at 9:30 + exit_min next morning

WHY THIS MIGHT WORK WITH 66 STOCKS:
  - With 17 stocks, the top/bottom 5 are not very extreme
  - With 66 stocks, the top/bottom 5 are TRUE outliers — much stronger signal
  - More stocks = better cross-sectional spread = more alpha from selection

NO REGIME FILTER: Always trades. The momentum ranking itself adapts:
  - In bull markets, even the "bottom 5" might be slightly positive
  - In bear markets, even the "top 5" might be slightly negative
  - The SPREAD between top and bottom is what matters

MARGIN OVERLAY: Shorts at entry fund additional longs.
REQUIRES: eod_flatten=False.
"""

from collections import deque
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")

SKIP = {"VGK", "EFA", "EWG", "FXI", "EWJ", "UVXY", "VXX", "VIXY",
        "XLK", "XLF", "SMH", "SPY", "QQQ", "IWM", "TQQQ"}


class CrossMomentumStrategy(Strategy):
    name = "cross_momentum"
    label = "Cross-Sectional Momentum (Pure Selection)"

    def __init__(
        self,
        symbols: List[str],
        # Momentum params
        momentum_days: int = 5,
        # Position params
        long_k: int = 5,               # long top K by momentum
        short_k: int = 5,              # short bottom K by momentum
        overnight_stop_pct: float = 3.0,
        entry_hour: int = 15,
        entry_minute: int = 30,
        exit_after_min: int = 20,
        # Optional: also use intraday RS as tiebreaker
        use_intraday_rs: bool = True,
        rs_weight: float = 0.3,        # weight of intraday RS in ranking
    ) -> None:
        super().__init__(symbols)
        self.momentum_days = momentum_days
        self.long_k = long_k
        self.short_k = short_k
        self.overnight_stop_pct = overnight_stop_pct
        self.entry_hour = entry_hour
        self.entry_minute = entry_minute
        self.exit_after_min = exit_after_min
        self.use_intraday_rs = use_intraday_rs
        self.rs_weight = rs_weight

        self._spy_open: float = 0.0
        self._spy_return: float = 0.0
        self._sym: Dict[str, dict] = {}
        self._current_date = None
        self._entry_done_today = None

    def on_start(self) -> None:
        self._sym = {}
        self._current_date = None
        self._entry_done_today = None

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "prev_close": None,
            "daily_closes": deque(maxlen=self.momentum_days + 2),
            "holding": False,
            "entry_date": None,
            "stop_level": None,
            "position_type": None,  # "long" or "short"
        }

    def rules(self) -> List[str]:
        return [
            "=== PURE CROSS-SECTIONAL MOMENTUM ===",
            f"Rank all stocks by {self.momentum_days}-day return",
            f"LONG top {self.long_k} | SHORT bottom {self.short_k}",
            f"Hold overnight, exit {self.exit_after_min}min after open",
            f"Stop: {self.overnight_stop_pct}%",
            f"Intraday RS tiebreaker: {'ON' if self.use_intraday_rs else 'OFF'} (weight {self.rs_weight})",
            "No regime filter — always trades",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        spy_bar = bars.get("SPY")
        if spy_bar is None:
            return signals

        et_spy = spy_bar.timestamp.astimezone(ET)
        spy_today = et_spy.date()
        bar_mins = et_spy.hour * 60 + et_spy.minute
        open_mins = 9 * 60 + 30

        if self._current_date != spy_today:
            self._current_date = spy_today
            self._spy_open = spy_bar.open
            self._entry_done_today = None

        if self._spy_open and self._spy_open > 0:
            self._spy_return = (spy_bar.close - self._spy_open) / self._spy_open * 100

        # Collect data for all stocks
        candidates: List[Tuple[str, float, float, float]] = []
        # (symbol, momentum_score, price, intraday_rs)

        for symbol in self.symbols:
            if symbol in SKIP:
                continue

            bar = bars.get(symbol)
            if bar is None:
                continue

            et = bar.timestamp.astimezone(ET)
            today = et.date()

            if symbol not in self._sym:
                self._sym[symbol] = self._fresh_sym()
            st = self._sym[symbol]

            if st["current_date"] != today:
                if st["prev_close"] is not None:
                    st["daily_closes"].append(st["prev_close"])
                st["current_date"] = today
                st["day_open"] = bar.open
                if not st["holding"]:
                    pass  # reset nothing — positions carry over

            price = bar.close
            st["prev_close"] = price
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0
            sym_bar_mins = et.hour * 60 + et.minute

            # ── EXIT overnight positions ─────────────────────────────────
            if st["holding"] and st["entry_date"] != today:
                # Stop
                if st["stop_level"]:
                    if current_qty > 0 and price <= st["stop_level"]:
                        signals.append(Signal(symbol, Direction.FLAT, reason="cm stop"))
                        st["holding"] = False; st["position_type"] = None; continue
                    if current_qty < 0 and price >= st["stop_level"]:
                        signals.append(Signal(symbol, Direction.FLAT, reason="cm stop"))
                        st["holding"] = False; st["position_type"] = None; continue

                # Time exit
                if sym_bar_mins >= open_mins + self.exit_after_min:
                    signals.append(Signal(symbol, Direction.FLAT, reason="cm exit"))
                    st["holding"] = False; st["position_type"] = None
                continue

            # Same-day stop
            if st["holding"] and st["entry_date"] == today:
                if st["stop_level"]:
                    if current_qty > 0 and price <= st["stop_level"]:
                        signals.append(Signal(symbol, Direction.FLAT, reason="cm stop(d)"))
                        st["holding"] = False; st["position_type"] = None
                    elif current_qty < 0 and price >= st["stop_level"]:
                        signals.append(Signal(symbol, Direction.FLAT, reason="cm stop(d)"))
                        st["holding"] = False; st["position_type"] = None
                continue

            if current_qty != 0:
                continue

            # ── COLLECT CANDIDATES at entry time ─────────────────────────
            entry_mins = self.entry_hour * 60 + self.entry_minute
            if (sym_bar_mins >= entry_mins and sym_bar_mins <= entry_mins + 5
                    and st["day_open"] and st["day_open"] > 0):

                closes = list(st["daily_closes"])
                if len(closes) >= self.momentum_days:
                    # N-day momentum
                    mom = (closes[-1] - closes[-self.momentum_days]) / closes[-self.momentum_days] * 100

                    # Intraday RS
                    intraday_ret = (price - st["day_open"]) / st["day_open"] * 100
                    rs = intraday_ret - self._spy_return

                    # Composite score
                    if self.use_intraday_rs:
                        score = mom + rs * self.rs_weight
                    else:
                        score = mom

                    candidates.append((symbol, score, price, rs))

        # ── ENTRY: rank and trade ────────────────────────────────────────
        entry_mins = self.entry_hour * 60 + self.entry_minute
        if (candidates and bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                and self._entry_done_today != spy_today):

            self._entry_done_today = spy_today

            # Sort by score (highest momentum first)
            candidates.sort(key=lambda x: x[1], reverse=True)

            # LONG top K
            long_count = 0
            for sym, score, px, rs in candidates:
                if long_count >= self.long_k:
                    break
                st = self._sym.get(sym)
                if not st or st["holding"]:
                    continue
                pos = portfolio.get_position(sym)
                if pos and pos.quantity != 0:
                    continue
                st["holding"] = True
                st["entry_date"] = spy_today
                st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                st["position_type"] = "long"
                signals.append(Signal(sym, Direction.LONG, reason=f"cm L mom={score:+.1f}%"))
                long_count += 1

            # SHORT bottom K
            short_count = 0
            for sym, score, px, rs in reversed(candidates):
                if short_count >= self.short_k:
                    break
                st = self._sym.get(sym)
                if not st or st["holding"]:
                    continue
                pos = portfolio.get_position(sym)
                if pos and pos.quantity != 0:
                    continue
                st["holding"] = True
                st["entry_date"] = spy_today
                st["stop_level"] = px * (1 + self.overnight_stop_pct / 100)
                st["position_type"] = "short"
                signals.append(Signal(sym, Direction.SHORT, reason=f"cm S mom={score:+.1f}%"))
                short_count += 1

        return signals
