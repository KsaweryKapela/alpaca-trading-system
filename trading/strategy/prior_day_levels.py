"""Prior-Day Level Trading Strategy.

THESIS: Key price levels from the previous session (high, low, close) act as
support and resistance. Breakouts above prior-day high with volume confirm
strength; rejections from prior-day high confirm weakness.

This is structurally different from all prior strategies because it uses
PRICE LEVELS as the signal, not momentum/RS/VWAP/RSI.

MODES:
  A) BREAKOUT: Stock breaks above prior-day high → long continuation
     - Confirmed by SPY above VWAP (bull regime)
     - Entry: first bar above PDH after 10:00 ET (avoid opening spike fakes)
     - Stop: below prior-day close
     - Target: 1.5× the distance from PDH to PDC (risk/reward)

  B) REJECTION SHORT: Stock tests prior-day high and fails → short
     - Confirmed by SPY below VWAP (bear regime)
     - Entry: price touches PDH then drops back below → short on rejection
     - Stop: above PDH + buffer
     - Target: prior-day close

  C) PRIOR-DAY LOW BOUNCE: Stock tests prior-day low and bounces → long
     - Confirmed by SPY above VWAP
     - Entry: price touches PDL then recovers
     - Stop: below PDL - buffer
     - Target: prior-day close

LEVELS:
  PDH = prior day high
  PDL = prior day low
  PDC = prior day close

FILTERS:
  - Only trade after 10:00 ET (avoid opening-range noise)
  - Maximum entry time: 14:00 ET (no late entries)
  - Require stock to first approach the level (within 0.1%) before triggering
  - SPY regime filter: breakouts in bull, rejections in bear

INTRADAY ONLY: flatten at 15:55 via engine.
"""

from collections import deque
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class PriorDayLevelsStrategy(Strategy):
    name = "prior_day_levels"
    label = "Prior-Day Levels (S/R Breakout/Rejection)"

    def __init__(
        self,
        symbols: List[str],
        # Entry params
        entry_after_min: int = 30,       # min after open (10:00 default)
        entry_end_hour: int = 14,
        approach_pct: float = 0.1,       # stock must come within 0.1% of level
        # Breakout
        breakout_confirm_pct: float = 0.05,  # close 0.05% above PDH = confirmed
        breakout_stop_below_pdc: bool = True,  # stop at PDC (prior day close)
        breakout_rr: float = 1.5,        # risk:reward ratio
        # Rejection
        rejection_fail_pct: float = 0.15,  # fall 0.15% below PDH = rejection
        rejection_target_pdc: bool = True,
        # Bounce
        bounce_confirm_pct: float = 0.15,  # rise 0.15% above PDL = bounce
        bounce_target_pdc: bool = True,
        # Common
        stop_pct: float = 0.8,           # fallback stop if level-based stop too wide
        max_stop_pct: float = 1.5,       # maximum stop distance
        # Direction / mode
        mode: str = "all",               # "all", "breakout_only", "rejection_only", "bounce_only"
        regime_filter: bool = True,      # use SPY VWAP regime
    ) -> None:
        super().__init__(symbols)
        self.entry_after_min = entry_after_min
        self.entry_end_hour = entry_end_hour
        self.approach_pct = approach_pct
        self.breakout_confirm_pct = breakout_confirm_pct
        self.breakout_stop_below_pdc = breakout_stop_below_pdc
        self.breakout_rr = breakout_rr
        self.rejection_fail_pct = rejection_fail_pct
        self.rejection_target_pdc = rejection_target_pdc
        self.bounce_confirm_pct = bounce_confirm_pct
        self.bounce_target_pdc = bounce_target_pdc
        self.stop_pct = stop_pct
        self.max_stop_pct = max_stop_pct
        self.mode = mode
        self.regime_filter = regime_filter

        self._spy: dict = {}
        self._sym: Dict[str, dict] = {}

    def on_start(self) -> None:
        self._spy = {
            "current_date": None, "day_open": None,
            "vwap_num": 0.0, "vwap_den": 0.0, "vwap": None,
        }
        self._sym = {}

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "day_high": None,
            "day_low": None,
            # Prior day levels
            "prev_day_high": None,
            "prev_day_low": None,
            "prev_day_close": None,
            # State tracking
            "approached_pdh": False,  # came within approach_pct of PDH
            "approached_pdl": False,
            "traded_today": False,
            "position_type": None,   # "breakout", "rejection", "bounce"
            "stop_level": None,
            "target_level": None,
        }

    def rules(self) -> List[str]:
        r = [
            f"Mode: {self.mode}",
            f"Entry: {self.entry_after_min}min after open → {self.entry_end_hour}:00",
        ]
        if self.mode in ("all", "breakout_only"):
            r.append(f"BREAKOUT: long when stock > PDH + {self.breakout_confirm_pct}% (bull regime)")
        if self.mode in ("all", "rejection_only"):
            r.append(f"REJECTION: short when stock approaches PDH then falls {self.rejection_fail_pct}% below (bear regime)")
        if self.mode in ("all", "bounce_only"):
            r.append(f"BOUNCE: long when stock approaches PDL then rises {self.bounce_confirm_pct}% above (bull regime)")
        r.append(f"Regime filter: {'ON' if self.regime_filter else 'OFF'}")
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
                # Save prior day levels
                if st["day_high"] is not None:
                    st["prev_day_high"] = st["day_high"]
                    st["prev_day_low"] = st["day_low"]
                    st["prev_day_close"] = bar.open  # approximate: today's open ≈ yesterday's close

                st["current_date"] = today
                st["day_open"] = bar.open
                st["day_high"] = bar.high
                st["day_low"] = bar.low
                st["approached_pdh"] = False
                st["approached_pdl"] = False
                st["traded_today"] = False
            else:
                if bar.high > (st["day_high"] or 0):
                    st["day_high"] = bar.high
                if st["day_low"] is None or bar.low < st["day_low"]:
                    st["day_low"] = bar.low

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0
            sym_bar_mins = et.hour * 60 + et.minute

            # ── Manage existing positions ────────────────────────────────
            if current_qty != 0 and st["position_type"] is not None:
                if current_qty > 0:  # long
                    if st["stop_level"] and price <= st["stop_level"]:
                        signals.append(Signal(symbol, Direction.FLAT, reason=f"pdl {st['position_type']} stop"))
                        st["position_type"] = None
                        continue
                    if st["target_level"] and price >= st["target_level"]:
                        signals.append(Signal(symbol, Direction.FLAT, reason=f"pdl {st['position_type']} target"))
                        st["position_type"] = None
                        continue
                elif current_qty < 0:  # short
                    if st["stop_level"] and price >= st["stop_level"]:
                        signals.append(Signal(symbol, Direction.FLAT, reason=f"pdl {st['position_type']} stop"))
                        st["position_type"] = None
                        continue
                    if st["target_level"] and price <= st["target_level"]:
                        signals.append(Signal(symbol, Direction.FLAT, reason=f"pdl {st['position_type']} target"))
                        st["position_type"] = None
                        continue
                continue

            if current_qty != 0:
                continue

            # Need prior day levels
            pdh = st["prev_day_high"]
            pdl = st["prev_day_low"]
            pdc = st["prev_day_close"]
            if pdh is None or pdl is None or pdc is None or pdh <= 0:
                continue

            # Timing filter
            if sym_bar_mins < open_mins + self.entry_after_min:
                continue
            if et.hour >= self.entry_end_hour:
                continue
            if st["traded_today"]:
                continue

            # Track approaches to levels
            if pdh > 0 and abs(price - pdh) / pdh * 100 < self.approach_pct:
                st["approached_pdh"] = True
            if pdl > 0 and abs(price - pdl) / pdl * 100 < self.approach_pct:
                st["approached_pdl"] = True

            # ── BREAKOUT: long above PDH ─────────────────────────────────
            if self.mode in ("all", "breakout_only"):
                if not self.regime_filter or spy_bullish:
                    if price > pdh * (1 + self.breakout_confirm_pct / 100):
                        # Breakout confirmed
                        if self.breakout_stop_below_pdc:
                            stop = pdc
                        else:
                            stop = price * (1 - self.stop_pct / 100)

                        # Check stop distance isn't too large
                        stop_dist_pct = (price - stop) / price * 100
                        if stop_dist_pct > self.max_stop_pct:
                            stop = price * (1 - self.max_stop_pct / 100)
                            stop_dist_pct = self.max_stop_pct

                        target = price + (price - stop) * self.breakout_rr

                        st["traded_today"] = True
                        st["position_type"] = "breakout"
                        st["stop_level"] = stop
                        st["target_level"] = target
                        signals.append(Signal(symbol, Direction.LONG,
                                              reason=f"pdl break PDH={pdh:.1f}"))
                        continue

            # ── REJECTION: short on PDH fail ─────────────────────────────
            if self.mode in ("all", "rejection_only"):
                if not self.regime_filter or spy_bearish:
                    if (st["approached_pdh"] and
                            price < pdh * (1 - self.rejection_fail_pct / 100)):
                        # Approached PDH but rejected
                        stop = pdh * (1 + self.approach_pct / 100)
                        stop_dist_pct = (stop - price) / price * 100
                        if stop_dist_pct > self.max_stop_pct:
                            stop = price * (1 + self.max_stop_pct / 100)

                        target = pdc if self.rejection_target_pdc else price * (1 - self.stop_pct / 100)

                        st["traded_today"] = True
                        st["position_type"] = "rejection"
                        st["stop_level"] = stop
                        st["target_level"] = target
                        signals.append(Signal(symbol, Direction.SHORT,
                                              reason=f"pdl rej PDH={pdh:.1f}"))
                        continue

            # ── BOUNCE: long off PDL ─────────────────────────────────────
            if self.mode in ("all", "bounce_only"):
                if not self.regime_filter or spy_bullish:
                    if (st["approached_pdl"] and
                            price > pdl * (1 + self.bounce_confirm_pct / 100)):
                        # Bounced off PDL
                        stop = pdl * (1 - self.approach_pct / 100)
                        stop_dist_pct = (price - stop) / price * 100
                        if stop_dist_pct > self.max_stop_pct:
                            stop = price * (1 - self.max_stop_pct / 100)

                        target = pdc if self.bounce_target_pdc else price + (price - stop) * self.breakout_rr

                        st["traded_today"] = True
                        st["position_type"] = "bounce"
                        st["stop_level"] = stop
                        st["target_level"] = target
                        signals.append(Signal(symbol, Direction.LONG,
                                              reason=f"pdl bounce PDL={pdl:.1f}"))
                        continue

        return signals
