"""Gap-Context Intraday Strategy.

NEW STRATEGY FAMILY — uses overnight gap behavior to predict intraday direction.

THESIS: The overnight gap is information. What happens IN THE FIRST 30 MINUTES
after the gap determines the rest of the day:

  GAP-UP + HOLD (price stays above prior close after 30 min):
    → Institutional accumulation confirmed. Go LONG for continuation.
    → The gap is "real" — buyers are defending it.

  GAP-UP + FAIL (price falls back below prior close within 30 min):
    → Gap trapped longs. Go SHORT for reversal/fade.
    → The gap was retail/news-driven, institutions are selling into it.

  GAP-DOWN + RECOVER (price recovers above prior close within 30 min):
    → Overnight fear was overdone. Go LONG for recovery.
    → Sellers exhausted, buyers stepping in.

  GAP-DOWN + CONTINUE (price stays below prior close):
    → Genuine weakness. Go SHORT for continuation.

WHY THIS IS DIFFERENT:
  - Previous strategies used intraday MOMENTUM (failed: stocks mean-revert)
  - Previous strategies used RS vs SPY (works for shorts, not longs)
  - This uses GAP QUALITY (how the gap behaves) as the primary signal
  - The first-30-min pattern determines WHETHER the gap is real
  - This is structural market microstructure, not price pattern matching

ENTRY RULES:
  - Check at 10:00 ET (30 min after open) — gap behavior is settled
  - Must have gapped > min_gap_pct from prior close
  - SPY regime filter: only trade gap direction aligned with SPY regime
  - Stop: below/above the gap reference level (prior close)
  - Target: 2× stop distance (2:1 R:R)
  - Exit by 15:25 ET (intraday)

INTRADAY ONLY: flatten at 15:55.
"""

from collections import deque
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class GapContextStrategy(Strategy):
    name = "gap_context"
    label = "Gap-Context Intraday (Gap Quality Signal)"

    def __init__(
        self,
        symbols: List[str],
        # Gap parameters
        min_gap_pct: float = 0.3,         # minimum gap size to qualify
        check_after_min: int = 30,        # check gap behavior after this many min
        # Entry/exit
        entry_end_hour: int = 13,         # latest entry
        stop_buffer_pct: float = 0.15,    # stop buffer beyond reference level
        target_mult: float = 2.0,         # target as multiple of stop distance
        max_stop_pct: float = 1.5,        # maximum stop distance
        exit_hour: int = 15,
        exit_minute: int = 25,
        # Mode
        mode: str = "all",                # "all", "hold_only", "fail_only"
        # SPY regime
        require_spy_alignment: bool = True,  # gap direction must align with SPY
    ) -> None:
        super().__init__(symbols)
        self.min_gap_pct = min_gap_pct
        self.check_after_min = check_after_min
        self.entry_end_hour = entry_end_hour
        self.stop_buffer_pct = stop_buffer_pct
        self.target_mult = target_mult
        self.max_stop_pct = max_stop_pct
        self.exit_hour = exit_hour
        self.exit_minute = exit_minute
        self.mode = mode
        self.require_spy_alignment = require_spy_alignment

        self._spy: dict = {}
        self._sym: Dict[str, dict] = {}

    def on_start(self) -> None:
        self._spy = {
            "current_date": None, "day_open": None,
            "vwap_num": 0.0, "vwap_den": 0.0, "vwap": None,
            "prev_close": None,
        }
        self._sym = {}

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "prev_close": None,       # yesterday's close (computed from today's open area)
            "gap_pct": None,           # (open - prev_close) / prev_close
            "gap_classified": False,   # have we classified the gap today?
            "gap_type": None,          # "hold", "fail", "recover", "continue", None
            "traded_today": False,
            "position_type": None,
            "stop_level": None,
            "target_level": None,
        }

    def rules(self) -> List[str]:
        r = [
            f"Min gap: {self.min_gap_pct}%",
            f"Check gap behavior at 9:30+{self.check_after_min}min",
            "GAP-UP + HOLD (above prior close) → LONG",
            "GAP-UP + FAIL (below prior close) → SHORT",
            "GAP-DOWN + RECOVER (above prior close) → LONG",
            "GAP-DOWN + CONTINUE (below prior close) → SHORT",
            f"Stop: prior close ± {self.stop_buffer_pct}% | Target: {self.target_mult}× stop",
            f"Mode: {self.mode}",
        ]
        if self.require_spy_alignment:
            r.append("Require SPY VWAP alignment")
        return r

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        spy_bar = bars.get("SPY")
        if spy_bar is None:
            return signals

        et_spy = spy_bar.timestamp.astimezone(ET)
        spy_today = et_spy.date()
        spy = self._spy

        if spy["current_date"] != spy_today:
            if spy["prev_close"] is None:
                spy["prev_close"] = spy_bar.open  # bootstrap
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
        spy_bullish = spy["vwap"] is not None and spy_price > spy["vwap"]
        spy_bearish = spy["vwap"] is not None and spy_price < spy["vwap"]

        bar_mins = et_spy.hour * 60 + et_spy.minute
        open_mins = 9 * 60 + 30
        exit_mins = self.exit_hour * 60 + self.exit_minute

        # Update SPY prev_close at end of day
        if bar_mins >= 15 * 60 + 50:
            spy["prev_close"] = spy_price

        tradable = [s for s in self.symbols if s != "SPY"]

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
                # Carry forward prev_close
                if st["prev_close"] is None:
                    st["prev_close"] = bar.open  # bootstrap
                st["current_date"] = today
                st["day_open"] = bar.open
                st["gap_classified"] = False
                st["gap_type"] = None
                st["traded_today"] = False
                st["position_type"] = None

                # Compute gap
                if st["prev_close"] and st["prev_close"] > 0:
                    st["gap_pct"] = (bar.open - st["prev_close"]) / st["prev_close"] * 100
                else:
                    st["gap_pct"] = None

            price = bar.close
            sym_bar_mins = et.hour * 60 + et.minute
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # ── Manage existing position ─────────────────────────────────
            if current_qty != 0 and st["position_type"] is not None:
                # Stop
                if current_qty > 0 and st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="gc stop"))
                    st["position_type"] = None
                    continue
                if current_qty < 0 and st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="gc stop"))
                    st["position_type"] = None
                    continue
                # Target
                if current_qty > 0 and st["target_level"] and price >= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="gc target"))
                    st["position_type"] = None
                    continue
                if current_qty < 0 and st["target_level"] and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="gc target"))
                    st["position_type"] = None
                    continue
                # Time exit
                if sym_bar_mins >= exit_mins:
                    signals.append(Signal(symbol, Direction.FLAT, reason="gc time"))
                    st["position_type"] = None
                continue

            if current_qty != 0:
                continue

            # ── Classify gap at check time ───────────────────────────────
            if (not st["gap_classified"]
                    and sym_bar_mins >= open_mins + self.check_after_min
                    and st["gap_pct"] is not None
                    and st["prev_close"] is not None
                    and abs(st["gap_pct"]) >= self.min_gap_pct):

                st["gap_classified"] = True
                gap_up = st["gap_pct"] > 0
                above_prev_close = price > st["prev_close"]

                if gap_up and above_prev_close:
                    st["gap_type"] = "hold"       # gap-up held → bullish
                elif gap_up and not above_prev_close:
                    st["gap_type"] = "fail"       # gap-up failed → bearish
                elif not gap_up and above_prev_close:
                    st["gap_type"] = "recover"    # gap-down recovered → bullish
                elif not gap_up and not above_prev_close:
                    st["gap_type"] = "continue"   # gap-down continuing → bearish

            # ── Entry based on gap classification ────────────────────────
            if (st["gap_classified"] and st["gap_type"] is not None
                    and not st["traded_today"]
                    and sym_bar_mins >= open_mins + self.check_after_min
                    and et.hour < self.entry_end_hour):

                ref = st["prev_close"]
                gap_type = st["gap_type"]
                direction = None

                if gap_type == "hold" and self.mode in ("all", "hold_only"):
                    # Gap-up confirmed → long
                    if not self.require_spy_alignment or spy_bullish:
                        direction = Direction.LONG
                        stop = ref * (1 - self.stop_buffer_pct / 100)
                        stop_dist = price - stop

                elif gap_type == "fail" and self.mode in ("all", "fail_only"):
                    # Gap-up failed → short
                    if not self.require_spy_alignment or spy_bearish:
                        direction = Direction.SHORT
                        stop = ref * (1 + self.stop_buffer_pct / 100)
                        stop_dist = stop - price

                elif gap_type == "recover" and self.mode in ("all", "hold_only"):
                    # Gap-down recovered → long
                    if not self.require_spy_alignment or spy_bullish:
                        direction = Direction.LONG
                        stop = ref * (1 - self.stop_buffer_pct / 100)
                        stop_dist = price - stop

                elif gap_type == "continue" and self.mode in ("all", "fail_only"):
                    # Gap-down continuing → short
                    if not self.require_spy_alignment or spy_bearish:
                        direction = Direction.SHORT
                        stop = ref * (1 + self.stop_buffer_pct / 100)
                        stop_dist = stop - price

                if direction is not None and stop_dist > 0:
                    # Check max stop
                    stop_pct = stop_dist / price * 100
                    if stop_pct > self.max_stop_pct:
                        # Tighten stop to max
                        if direction == Direction.LONG:
                            stop = price * (1 - self.max_stop_pct / 100)
                            stop_dist = price - stop
                        else:
                            stop = price * (1 + self.max_stop_pct / 100)
                            stop_dist = stop - price

                    # Compute target
                    if direction == Direction.LONG:
                        target = price + stop_dist * self.target_mult
                    else:
                        target = price - stop_dist * self.target_mult

                    st["traded_today"] = True
                    st["position_type"] = gap_type
                    st["stop_level"] = stop
                    st["target_level"] = target
                    signals.append(Signal(symbol, direction,
                                          reason=f"gc {gap_type} gap={st['gap_pct']:+.1f}%"))

            # Update prev_close at end of day
            if sym_bar_mins >= 15 * 60 + 50:
                st["prev_close"] = price

        return signals
