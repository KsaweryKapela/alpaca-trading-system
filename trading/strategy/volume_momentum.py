"""Volume-Qualified Intraday Momentum.

Hypothesis (Gao et al. 2018, ORB+volume practitioner research):
  The reason pure intraday momentum (ITM) failed in runs 070-080 is that
  it treated ALL morning moves equally. But high-volume morning moves are
  institutional (persist), while low-volume moves are retail (reverse).

  By requiring relative volume > threshold at entry time, we filter for
  institutionally-driven moves that have staying power.

  Additionally, VWAP alignment confirms that the move has institutional
  support: a stock above VWAP on high volume = real demand.

Rules:
  1. Track each stock's volume in first N bars after open.
  2. Track rolling average of first-N-bar volume per stock (lookback days).
  3. At entry_time: compute RVOL = today's first-N-bar volume / avg volume.
  4. LONG when: return > threshold% AND RVOL > rvol_min AND price > VWAP.
  5. SHORT when: return < -threshold% AND RVOL > rvol_min AND price < VWAP.
  6. Stop: stop_pct% from entry.
  7. Direction filter.
  8. One trade per symbol per day.
  9. EOD flatten at 15:55 ET.
"""

from collections import deque
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class VolumeMomentumStrategy(Strategy):
    name = "volume_momentum"
    label = "Volume-Qualified Intraday Momentum"

    def __init__(
        self,
        symbols: List[str],
        momentum_threshold: float = 0.3,
        stop_pct: float = 1.5,
        profit_target_pct: float = 0.0,
        direction: str = "both",
        rvol_min: float = 1.5,           # minimum relative volume to qualify
        rvol_lookback: int = 10,         # days to average for RVOL baseline
        require_vwap: bool = True,       # require price on correct side of VWAP
        entry_hour: int = 10,
        entry_minute: int = 0,
    ) -> None:
        super().__init__(symbols)
        self.momentum_threshold = momentum_threshold
        self.stop_pct = stop_pct
        self.profit_target_pct = profit_target_pct
        self.direction = direction
        self.rvol_min = rvol_min
        self.rvol_lookback = rvol_lookback
        self.require_vwap = require_vwap
        self.entry_hour = entry_hour
        self.entry_minute = entry_minute
        self._state: Dict[str, dict] = {}

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "morning_volume": 0,         # cumulative volume in first N bars today
            "morning_volumes": deque(maxlen=self.rvol_lookback),  # historical morning volumes
            "vwap_num": 0.0,
            "vwap_den": 0.0,
            "vwap": None,
            "entry_attempted": False,
            "traded_today": False,
            "stop_level": None,
            "take_profit": None,
        }

    def on_start(self) -> None:
        self._state = {sym: self._fresh_sym() for sym in self.symbols}

    def rules(self) -> List[str]:
        vwap_note = "Require price on correct side of VWAP" if self.require_vwap else "No VWAP requirement"
        return [
            f"Track relative volume (RVOL) = today's morning volume / {self.rvol_lookback}-day avg",
            f"At {self.entry_hour}:{self.entry_minute:02d} ET with RVOL > {self.rvol_min}×:",
            f"  LONG if return > +{self.momentum_threshold}% AND above VWAP",
            f"  SHORT if return < -{self.momentum_threshold}% AND below VWAP",
            vwap_note,
            f"Stop: {self.stop_pct}% | Direction: {self.direction}",
            *([] if self.profit_target_pct == 0 else
              [f"Target: {self.profit_target_pct}%"]),
            f"One trade per symbol per day | EOD flatten 15:55 ET",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        for symbol in self.symbols:
            bar = bars.get(symbol)
            if bar is None:
                continue

            et = bar.timestamp.astimezone(ET)
            today = et.date()
            st = self._state[symbol]

            bar_mins = et.hour * 60 + et.minute
            open_mins = 9 * 60 + 30
            entry_mins = self.entry_hour * 60 + self.entry_minute

            # Day reset
            if st["current_date"] != today:
                # Record yesterday's morning volume before reset
                if st["current_date"] is not None and st["morning_volume"] > 0:
                    st["morning_volumes"].append(st["morning_volume"])
                st["current_date"] = today
                st["day_open"] = bar.open
                st["morning_volume"] = 0
                st["vwap_num"] = 0.0
                st["vwap_den"] = 0.0
                st["vwap"] = None
                st["entry_attempted"] = False
                st["traded_today"] = False
                st["stop_level"] = None
                st["take_profit"] = None

            # Accumulate morning volume (up to entry time)
            if bar_mins < entry_mins:
                st["morning_volume"] += bar.volume

            # Update VWAP
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
                    signals.append(Signal(symbol, Direction.FLAT, reason="vol-mom long stop"))
                elif st["take_profit"] is not None and price >= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="vol-mom long target"))
                continue

            if current_qty < 0:
                if st["stop_level"] is not None and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="vol-mom short stop"))
                elif st["take_profit"] is not None and price <= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="vol-mom short target"))
                continue

            # Entry: at specific time only
            if st["entry_attempted"] or st["traded_today"]:
                continue
            if st["day_open"] is None or st["day_open"] == 0:
                continue
            if bar_mins < entry_mins:
                continue

            st["entry_attempted"] = True
            if bar_mins > entry_mins + 5:
                continue

            # Compute RVOL
            if len(st["morning_volumes"]) < 3:
                continue  # need at least 3 days of volume history
            avg_vol = sum(st["morning_volumes"]) / len(st["morning_volumes"])
            if avg_vol == 0:
                continue
            rvol = st["morning_volume"] / avg_vol

            if rvol < self.rvol_min:
                continue  # not enough volume = not institutional

            return_pct = (price - st["day_open"]) / st["day_open"] * 100
            vwap = st["vwap"]

            allow_long = self.direction in ("both", "long_only")
            allow_short = self.direction in ("both", "short_only")

            # LONG: up on high volume, above VWAP = institutional buying
            if return_pct > self.momentum_threshold and allow_long:
                vwap_ok = (vwap is not None and price > vwap) if self.require_vwap else True
                if vwap_ok:
                    st["traded_today"] = True
                    st["stop_level"] = price * (1 - self.stop_pct / 100)
                    st["take_profit"] = (price * (1 + self.profit_target_pct / 100)
                                         if self.profit_target_pct > 0 else None)
                    signals.append(Signal(
                        symbol, Direction.LONG,
                        reason=f"vol-mom LONG +{return_pct:.1f}% RVOL={rvol:.1f}x"
                    ))

            # SHORT: down on high volume, below VWAP = institutional selling
            elif return_pct < -self.momentum_threshold and allow_short:
                vwap_ok = (vwap is not None and price < vwap) if self.require_vwap else True
                if vwap_ok:
                    st["traded_today"] = True
                    st["stop_level"] = price * (1 + self.stop_pct / 100)
                    st["take_profit"] = (price * (1 - self.profit_target_pct / 100)
                                         if self.profit_target_pct > 0 else None)
                    signals.append(Signal(
                        symbol, Direction.SHORT,
                        reason=f"vol-mom SHORT {return_pct:.1f}% RVOL={rvol:.1f}x"
                    ))

        return signals
