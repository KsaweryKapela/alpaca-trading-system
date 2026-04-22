"""Gapper Momentum: Catalyst-Driven Intraday Trading.

WORKS ACROSS ALL SECTORS — catalyst-driven, not beta-dependent.

THESIS: Stocks that gap significantly (>1-2%) have news/catalysts. These
catalysts create directional bias that persists for hours. The key is
CONFIRMATION: wait 30 min, verify the gap holds, then ride the trend.

STOCK SELECTION (each morning):
  1. Compute overnight gap for ALL stocks in the universe
  2. Filter: gap > min_gap_pct (significant news/catalyst)
  3. At 10:00 ET, classify each gapper:
     - GAP-UP CONFIRMED: price still above gap level → LONG
     - GAP-DOWN CONFIRMED: price still below gap level → SHORT
     - GAP FADED: gap reversed → SKIP (no edge)

WHY THIS IS DIFFERENT FROM EVERYTHING PRIOR:
  - Previous overnight strategies: fixed universe, beta-dependent edge
  - Previous RS shorts: SPY-relative, regime-dependent
  - This: catalyst-driven, sector-agnostic, works on ANY liquid stock
  - The selection IS the edge — trading only catalyst-driven names

TRADE MANAGEMENT:
  - Entry: at confirmation time (10:00 ET), in gap direction
  - Stop: at the gap level (if price returns to gap open → thesis invalid)
  - Target: 2x stop distance (2:1 R:R)
  - Exit: 15:25 ET at latest (intraday only)
  - Max positions: top N by gap magnitude (biggest catalysts first)

INTRADAY ONLY — flatten at 15:55.
"""

from collections import deque
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")

SKIP_SYMBOLS = {"VGK", "EFA", "EWG", "FXI", "EWJ", "UVXY", "VXX", "VIXY",
                "XLK", "XLF", "SMH", "SPY", "QQQ", "IWM", "TQQQ"}


class GapperMomentumStrategy(Strategy):
    name = "gapper_momentum"
    label = "Gapper Momentum (Catalyst-Driven)"

    def __init__(
        self,
        symbols: List[str],
        # Gap scanning
        min_gap_pct: float = 1.5,          # minimum gap to qualify
        max_gap_pct: float = 15.0,         # skip extreme gaps (binary events)
        confirm_after_min: int = 30,       # confirm gap at 10:00 ET
        # Position management
        max_positions: int = 6,            # max concurrent gapper trades
        stop_at_gap: bool = True,          # stop at the gap open level
        stop_buffer_pct: float = 0.2,      # buffer beyond gap level for stop
        target_mult: float = 2.0,          # R:R multiplier
        max_stop_pct: float = 3.0,         # cap stop distance
        # Exit
        exit_hour: int = 15,
        exit_minute: int = 25,
        entry_end_hour: int = 12,          # no new entries after noon
        # Direction filter
        direction: str = "both",           # "both", "long_only", "short_only"
        # Market regime filter (optional)
        use_spy_filter: bool = False,      # require SPY alignment
    ) -> None:
        super().__init__(symbols)
        self.min_gap_pct = min_gap_pct
        self.max_gap_pct = max_gap_pct
        self.confirm_after_min = confirm_after_min
        self.max_positions = max_positions
        self.stop_at_gap = stop_at_gap
        self.stop_buffer_pct = stop_buffer_pct
        self.target_mult = target_mult
        self.max_stop_pct = max_stop_pct
        self.exit_hour = exit_hour
        self.exit_minute = exit_minute
        self.entry_end_hour = entry_end_hour
        self.direction = direction
        self.use_spy_filter = use_spy_filter

        self._spy: dict = {}
        self._sym: Dict[str, dict] = {}
        self._positions_today: int = 0
        self._selection_done_today = None

    def on_start(self) -> None:
        self._spy = {
            "current_date": None, "day_open": None,
            "vwap_num": 0.0, "vwap_den": 0.0, "vwap": None,
        }
        self._sym = {}
        self._positions_today = 0
        self._selection_done_today = None

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "prev_close": None,
            "gap_pct": None,
            "gap_confirmed": None,    # True=confirmed, False=faded, None=unchecked
            "traded_today": False,
            "position_type": None,
            "stop_level": None,
            "target_level": None,
        }

    def rules(self) -> List[str]:
        return [
            "=== GAPPER SCAN (every morning) ===",
            f"Gap threshold: {self.min_gap_pct}% - {self.max_gap_pct}%",
            f"Confirm at 9:30+{self.confirm_after_min}min",
            f"Max positions: {self.max_positions}",
            "=== ENTRY ===",
            "Gap-up confirmed (above open) → LONG",
            "Gap-down confirmed (below open) → SHORT",
            "Gap faded → SKIP",
            f"Target: {self.target_mult}x stop | Max stop: {self.max_stop_pct}%",
            f"Direction: {self.direction}",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        spy_bar = bars.get("SPY")
        if spy_bar is None:
            return signals

        et_spy = spy_bar.timestamp.astimezone(ET)
        spy_today = et_spy.date()
        spy = self._spy

        if spy["current_date"] != spy_today:
            spy["current_date"] = spy_today
            spy["day_open"] = spy_bar.open
            spy["vwap_num"] = 0.0
            spy["vwap_den"] = 0.0
            spy["vwap"] = None
            self._positions_today = 0
            self._selection_done_today = None

        typical = (spy_bar.high + spy_bar.low + spy_bar.close) / 3
        spy["vwap_num"] += typical * spy_bar.volume
        spy["vwap_den"] += spy_bar.volume
        if spy["vwap_den"] > 0:
            spy["vwap"] = spy["vwap_num"] / spy["vwap_den"]

        spy_price = spy_bar.close
        spy_bullish = spy["vwap"] is not None and spy_price > spy["vwap"]
        spy_bearish = spy["vwap"] is not None and spy_price < spy["vwap"]

        bar_mins = et_spy.hour * 60 + et_spy.minute
        open_mins = 9 * 60 + 30
        exit_mins = self.exit_hour * 60 + self.exit_minute

        # Collect gapper candidates at confirmation time
        gapper_candidates: List[Tuple[str, float, float, float]] = []
        # (symbol, gap_pct, current_price, gap_open_price)

        for symbol in self.symbols:
            if symbol in SKIP_SYMBOLS:
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
                # Save prev_close and compute gap
                if st["prev_close"] is None:
                    st["prev_close"] = bar.open  # bootstrap
                st["current_date"] = today
                st["day_open"] = bar.open
                st["gap_confirmed"] = None
                st["traded_today"] = False
                st["position_type"] = None

                if st["prev_close"] and st["prev_close"] > 0:
                    st["gap_pct"] = (bar.open - st["prev_close"]) / st["prev_close"] * 100
                else:
                    st["gap_pct"] = None

            price = bar.close
            sym_bar_mins = et.hour * 60 + et.minute
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # ── MANAGE EXISTING POSITIONS ────────────────────────────────
            if current_qty != 0 and st["position_type"] is not None:
                # Stop
                if current_qty > 0 and st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="gm stop"))
                    st["position_type"] = None; continue
                if current_qty < 0 and st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="gm stop"))
                    st["position_type"] = None; continue
                # Target
                if current_qty > 0 and st["target_level"] and price >= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="gm target"))
                    st["position_type"] = None; continue
                if current_qty < 0 and st["target_level"] and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="gm target"))
                    st["position_type"] = None; continue
                # Time exit
                if sym_bar_mins >= exit_mins:
                    signals.append(Signal(symbol, Direction.FLAT, reason="gm time"))
                    st["position_type"] = None
                continue

            if current_qty != 0:
                continue

            # Update prev_close near EOD
            if sym_bar_mins >= 15 * 60 + 50:
                st["prev_close"] = price

            # ── GAP CLASSIFICATION at confirm time ───────────────────────
            if (st["gap_pct"] is not None
                    and abs(st["gap_pct"]) >= self.min_gap_pct
                    and abs(st["gap_pct"]) <= self.max_gap_pct
                    and st["gap_confirmed"] is None
                    and sym_bar_mins >= open_mins + self.confirm_after_min
                    and sym_bar_mins < open_mins + self.confirm_after_min + 5):

                gap_up = st["gap_pct"] > 0
                if gap_up:
                    # Confirmed if price is still above the open (gap held)
                    st["gap_confirmed"] = price > st["day_open"]
                else:
                    # Confirmed if price is still below the open (gap held)
                    st["gap_confirmed"] = price < st["day_open"]

                if st["gap_confirmed"]:
                    gapper_candidates.append((symbol, st["gap_pct"], price, st["day_open"]))

        # ── SELECT TOP GAPPERS AND ENTER ─────────────────────────────────
        if (gapper_candidates
                and self._selection_done_today != spy_today
                and bar_mins >= open_mins + self.confirm_after_min
                and bar_mins < open_mins + self.confirm_after_min + 5):

            self._selection_done_today = spy_today

            # Sort by absolute gap magnitude (biggest catalyst first)
            gapper_candidates.sort(key=lambda x: abs(x[1]), reverse=True)

            for sym, gap, px, gap_open in gapper_candidates:
                if self._positions_today >= self.max_positions:
                    break

                st = self._sym.get(sym)
                if not st or st["traded_today"]:
                    continue
                pos = portfolio.get_position(sym)
                if pos and pos.quantity != 0:
                    continue

                gap_up = gap > 0

                # Direction filter
                if gap_up and self.direction == "short_only":
                    continue
                if not gap_up and self.direction == "long_only":
                    continue

                # SPY alignment filter
                if self.use_spy_filter:
                    if gap_up and not spy_bullish:
                        continue
                    if not gap_up and not spy_bearish:
                        continue

                # Compute stop and target
                if self.stop_at_gap:
                    if gap_up:
                        stop = gap_open * (1 - self.stop_buffer_pct / 100)
                        stop_dist = px - stop
                    else:
                        stop = gap_open * (1 + self.stop_buffer_pct / 100)
                        stop_dist = stop - px
                else:
                    stop_dist = px * self.max_stop_pct / 100
                    if gap_up:
                        stop = px - stop_dist
                    else:
                        stop = px + stop_dist

                # Cap stop distance
                if stop_dist <= 0:
                    continue
                stop_pct = stop_dist / px * 100
                if stop_pct > self.max_stop_pct:
                    stop_dist = px * self.max_stop_pct / 100
                    if gap_up:
                        stop = px - stop_dist
                    else:
                        stop = px + stop_dist

                # Target
                if gap_up:
                    target = px + stop_dist * self.target_mult
                    direction = Direction.LONG
                else:
                    target = px - stop_dist * self.target_mult
                    direction = Direction.SHORT

                st["traded_today"] = True
                st["position_type"] = "gapper"
                st["stop_level"] = stop
                st["target_level"] = target
                self._positions_today += 1
                signals.append(Signal(sym, direction,
                                      reason=f"gm gap={gap:+.1f}%"))

        return signals
