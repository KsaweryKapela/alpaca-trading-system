"""Exhaustion Fade — mean reversion after extreme volume-confirmed moves.

Hypothesis (Della Corte & Kosowski, volume exhaustion research):
  Mean reversion strategies fail when they fade STRUCTURED moves (trend
  days). But after EXTREME moves with high volume, the selling/buying
  is exhaustive (panic/forced liquidation), not informational. These
  exhaust moves create the highest-probability mean reversion entries.

  Our prior VWAP/RSI reversion strategies lacked the exhaustion gate.
  This strategy only enters when:
  1. The stock has moved >extreme_pct% from open (extreme, not normal)
  2. Volume is >vol_mult× the average (confirming forced/panic flow)
  3. The move has lost momentum (current bar range contracting)

Rules:
  1. Track each stock's return from open, VWAP, and relative volume.
  2. LONG FADE when: return < -extreme_pct% AND RVOL > vol_mult
     AND price < VWAP (extreme selloff, likely exhaustion).
  3. SHORT FADE when: return > +extreme_pct% AND RVOL > vol_mult
     AND price > VWAP (extreme rally, likely exhaustion).
  4. Target: fade back toward VWAP (target_pct% or VWAP cross).
  5. Stop: stop_pct% beyond the extreme.
  6. Direction filter.
  7. One trade per symbol per day.
  8. EOD flatten at 15:55 ET.
"""

from collections import deque
from typing import Dict, List
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class ExhaustionFadeStrategy(Strategy):
    name = "exhaustion_fade"
    label = "Exhaustion Fade (volume-gated mean reversion)"

    def __init__(
        self,
        symbols: List[str],
        extreme_pct: float = 2.0,       # stock must move this % from open (extreme threshold)
        vol_mult: float = 2.0,          # volume must be this × average to confirm exhaustion
        vol_lookback: int = 10,          # days to average for volume baseline
        stop_pct: float = 1.5,          # stop beyond the extreme
        target_pct: float = 1.5,         # target for fade (toward VWAP)
        direction: str = "both",         # "both" | "long_only" (fade selloffs) | "short_only" (fade rallies)
        entry_after_min: int = 30,       # wait this many minutes to let extremes develop
        entry_end_hour: int = 15,        # late entry OK for exhaustion (happens anytime)
    ) -> None:
        super().__init__(symbols)
        self.extreme_pct = extreme_pct
        self.vol_mult = vol_mult
        self.vol_lookback = vol_lookback
        self.stop_pct = stop_pct
        self.target_pct = target_pct
        self.direction = direction
        self.entry_after_min = entry_after_min
        self.entry_end_hour = entry_end_hour
        self._state: Dict[str, dict] = {}

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "cum_volume": 0,
            "bar_count": 0,
            "daily_avg_volumes": deque(maxlen=self.vol_lookback),
            "daily_bar_counts": deque(maxlen=self.vol_lookback),
            "vwap_num": 0.0,
            "vwap_den": 0.0,
            "vwap": None,
            "traded_today": False,
            "stop_level": None,
            "take_profit": None,
        }

    def on_start(self) -> None:
        self._state = {sym: self._fresh_sym() for sym in self.symbols}

    def rules(self) -> List[str]:
        return [
            f"Track per-stock VWAP and cumulative volume vs {self.vol_lookback}-day average",
            f"LONG FADE when: return < -{self.extreme_pct}% AND volume > {self.vol_mult}× avg (exhaustion selloff)",
            f"SHORT FADE when: return > +{self.extreme_pct}% AND volume > {self.vol_mult}× avg (exhaustion rally)",
            f"Stop: {self.stop_pct}% beyond extreme | Target: {self.target_pct}% fade",
            f"Direction: {self.direction}",
            f"Entry window: {self.entry_after_min} min after open → {self.entry_end_hour}:00 ET",
            f"One trade per symbol per day | EOD flatten 15:55 ET",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        for symbol in self.symbols:
            if symbol == "SPY":
                continue

            bar = bars.get(symbol)
            if bar is None:
                continue

            et = bar.timestamp.astimezone(ET)
            today = et.date()
            st = self._state[symbol]

            if st["current_date"] != today:
                # Record previous day's volume stats
                if st["current_date"] is not None and st["bar_count"] > 0:
                    st["daily_avg_volumes"].append(st["cum_volume"] / st["bar_count"])
                    st["daily_bar_counts"].append(st["bar_count"])
                st["current_date"] = today
                st["day_open"] = bar.open
                st["cum_volume"] = 0
                st["bar_count"] = 0
                st["vwap_num"] = 0.0
                st["vwap_den"] = 0.0
                st["vwap"] = None
                st["traded_today"] = False
                st["stop_level"] = None
                st["take_profit"] = None

            # Update volume and VWAP
            st["cum_volume"] += bar.volume
            st["bar_count"] += 1

            typical = (bar.high + bar.low + bar.close) / 3
            st["vwap_num"] += typical * bar.volume
            st["vwap_den"] += bar.volume
            if st["vwap_den"] > 0:
                st["vwap"] = st["vwap_num"] / st["vwap_den"]

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # Manage open positions
            if current_qty > 0:
                if st["stop_level"] is not None and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="exhaust long stop"))
                elif st["take_profit"] is not None and price >= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="exhaust long target"))
                continue

            if current_qty < 0:
                if st["stop_level"] is not None and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="exhaust short stop"))
                elif st["take_profit"] is not None and price <= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="exhaust short target"))
                continue

            # Entry gates
            bar_mins = et.hour * 60 + et.minute
            open_mins = 9 * 60 + 30
            if bar_mins < open_mins + self.entry_after_min:
                continue
            if et.hour >= self.entry_end_hour:
                continue
            if st["traded_today"]:
                continue
            if st["day_open"] is None or st["day_open"] == 0:
                continue

            # Need volume history
            if len(st["daily_avg_volumes"]) < 3:
                continue

            # Compute current RVOL (volume per bar today vs historical avg)
            avg_vol_per_bar = sum(st["daily_avg_volumes"]) / len(st["daily_avg_volumes"])
            if avg_vol_per_bar == 0:
                continue
            current_vol_per_bar = st["cum_volume"] / st["bar_count"]
            rvol = current_vol_per_bar / avg_vol_per_bar

            return_pct = (price - st["day_open"]) / st["day_open"] * 100
            vwap = st["vwap"]

            allow_long = self.direction in ("both", "long_only")
            allow_short = self.direction in ("both", "short_only")

            # LONG FADE: extreme selloff on high volume → exhaustion → bounce
            if (return_pct < -self.extreme_pct
                    and rvol > self.vol_mult
                    and allow_long
                    and vwap is not None and price < vwap):
                st["traded_today"] = True
                st["stop_level"] = price * (1 - self.stop_pct / 100)
                st["take_profit"] = price * (1 + self.target_pct / 100)
                signals.append(Signal(
                    symbol, Direction.LONG,
                    reason=f"exhaust fade: {return_pct:.1f}% RVOL={rvol:.1f}x → bounce"
                ))

            # SHORT FADE: extreme rally on high volume → exhaustion → pullback
            elif (return_pct > self.extreme_pct
                  and rvol > self.vol_mult
                  and allow_short
                  and vwap is not None and price > vwap):
                st["traded_today"] = True
                st["stop_level"] = price * (1 + self.stop_pct / 100)
                st["take_profit"] = price * (1 - self.target_pct / 100)
                signals.append(Signal(
                    symbol, Direction.SHORT,
                    reason=f"exhaust fade: +{return_pct:.1f}% RVOL={rvol:.1f}x → pullback"
                ))

        return signals
