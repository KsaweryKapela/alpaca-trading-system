"""VWAP Mean Reversion strategy.

Rules (per symbol, per day):
  1. Compute intraday VWAP bar by bar from market open.
     VWAP = Σ(typical_price × volume) / Σ(volume)
     typical_price = (high + low + close) / 3
  2. Skip the first `entry_start` minutes (opening noise distorts VWAP).
  3. When close < VWAP × (1 − entry_dev) and no position held:
       → emit LONG signal. Record entry_price.
  4. While in position:
       a. If close ≥ VWAP → emit FLAT (target: revert to VWAP).
       b. If close < entry_price × (1 − stop_pct) → emit FLAT (stop loss).
       c. At or after exit_time → emit FLAT (EOD flatten).
  5. One trade per symbol per day. Long-only.

Design notes:
  - entry_dev = 0.007 (0.7%) is chosen based on literature suggesting 0.5-1.2%
    deviation on 5m bars. 0.1% is noise; 0.7% is a meaningful intraday deviation.
  - R:R ≈ 0.7%/0.5% = 1.4 if stop is hit before target. In practice target is
    reached more often than stop on mean-reverting instruments.
  - Skipping the first 30 min avoids VWAP computed on only a few bars (noisy).
"""

import datetime
from collections import defaultdict
from typing import Dict, List, Optional

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

_NY = ZoneInfo("America/New_York")
_MARKET_OPEN = datetime.time(9, 30)
_MARKET_CLOSE = datetime.time(16, 0)


def _to_ny(ts: datetime.datetime) -> datetime.datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    return ts.astimezone(_NY)


class VWAPReversionStrategy(Strategy):
    """VWAP mean reversion — long-only, intraday, no overnight holds.

    Args:
        symbols:      Symbols to watch and trade.
        entry_dev:    Enter when close < VWAP × (1 − entry_dev). Default: 0.007 (0.7%).
        stop_pct:     Stop loss as fraction of entry price. Default: 0.005 (0.5%).
        entry_start:  NY time before which no entries are allowed (opening noise filter).
                      Default: 10:00 (skip first 30 min).
        exit_time:    NY time for EOD flatten. Default: 15:55.
    """

    def __init__(
        self,
        symbols: List[str],
        entry_dev: float = 0.007,
        stop_pct: float = 0.005,
        entry_start: datetime.time = datetime.time(10, 0),
        exit_time: datetime.time = datetime.time(15, 55),
    ) -> None:
        super().__init__(symbols)
        self.entry_dev = entry_dev
        self.stop_pct = stop_pct
        self.entry_start = entry_start
        self.exit_time = exit_time

        # Per-symbol daily state
        self._cur_date: Dict[str, Optional[datetime.date]] = defaultdict(lambda: None)
        self._vwap_num: Dict[str, float] = defaultdict(float)   # Σ(tp × vol)
        self._vwap_den: Dict[str, float] = defaultdict(float)   # Σ(vol)
        self._traded: Dict[str, bool] = defaultdict(bool)
        self._entry_price: Dict[str, Optional[float]] = defaultdict(lambda: None)

    def _reset(self, symbol: str, date: datetime.date) -> None:
        self._cur_date[symbol] = date
        self._vwap_num[symbol] = 0.0
        self._vwap_den[symbol] = 0.0
        self._traded[symbol] = False
        self._entry_price[symbol] = None

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        for symbol in self.symbols:
            bar = bars.get(symbol)
            if bar is None:
                continue

            ny = _to_ny(bar.timestamp)
            today = ny.date()
            t = ny.time()

            # Skip pre/post market
            if t < _MARKET_OPEN or t >= _MARKET_CLOSE:
                continue

            # New day reset
            if self._cur_date[symbol] != today:
                self._reset(symbol, today)

            # Update VWAP
            if bar.volume > 0:
                typical = (bar.high + bar.low + bar.close) / 3
                self._vwap_num[symbol] += typical * bar.volume
                self._vwap_den[symbol] += bar.volume

            if self._vwap_den[symbol] == 0:
                continue
            vwap = self._vwap_num[symbol] / self._vwap_den[symbol]

            pos = portfolio.get_position(symbol)
            in_position = pos is not None and pos.quantity > 0

            # ── 1. EOD exit ──────────────────────────────────────────────────
            if t >= self.exit_time and in_position:
                signals.append(Signal(
                    symbol=symbol,
                    direction=Direction.FLAT,
                    reason=f"EOD exit @ {t}",
                ))
                self._traded[symbol] = True
                self._entry_price[symbol] = None
                continue

            # ── 2. In-position management ────────────────────────────────────
            if in_position:
                # Use portfolio's recorded avg_price (actual fill price) for
                # stop calculation — avoids the signal-bar-close vs fill-open gap.
                ep = pos.avg_price
                # Target: price returned to VWAP
                if bar.close >= vwap:
                    signals.append(Signal(
                        symbol=symbol,
                        direction=Direction.FLAT,
                        reason=f"Target: close {bar.close:.2f} >= VWAP {vwap:.2f}",
                    ))
                    self._traded[symbol] = True
                    self._entry_price[symbol] = None
                    continue
                # Stop loss
                stop_level = ep * (1 - self.stop_pct)
                if bar.close < stop_level:
                    signals.append(Signal(
                        symbol=symbol,
                        direction=Direction.FLAT,
                        reason=(
                            f"Stop: close {bar.close:.2f} < {stop_level:.2f} "
                            f"(avg_price {ep:.2f} - {self.stop_pct*100:.1f}%)"
                        ),
                    ))
                    self._traded[symbol] = True
                    self._entry_price[symbol] = None
                    continue

            # ── 3. Entry: dip to VWAP − entry_dev ───────────────────────────
            if not self._traded[symbol] and not in_position:
                # Skip opening noise window
                if t < self.entry_start:
                    continue
                entry_threshold = vwap * (1 - self.entry_dev)
                if bar.close < entry_threshold:
                    signals.append(Signal(
                        symbol=symbol,
                        direction=Direction.LONG,
                        reason=(
                            f"VWAP dip: close {bar.close:.2f} < "
                            f"VWAP {vwap:.2f} - {self.entry_dev*100:.1f}% "
                            f"= {entry_threshold:.2f}"
                        ),
                    ))
                    self._traded[symbol] = True
                    self._entry_price[symbol] = bar.close

        return signals
