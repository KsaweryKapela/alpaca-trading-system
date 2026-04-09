"""Opening Range Breakout (ORB) strategy.

Rules (per symbol, per day):
  1. During the first `range_minutes` minutes of the session (9:30–9:44 for 15m),
     accumulate the range: track the highest high and lowest low.
  2. On the first close above the range high → emit LONG signal.
  3. While in position, if close falls below range low → emit FLAT (stop loss).
  4. At or after `exit_time` NY while in position → emit FLAT (EOD flatten).
  5. Maximum one trade per symbol per day. No overnight holds.

Practical notes:
  - Designed for 1m or 5m bars. With 5m bars and range_minutes=15, the range
    spans 3 bars (9:30, 9:35, 9:40); first signal window opens at 9:45.
  - Long-only. Suitable for SPY, QQQ, and highly liquid large-caps.
  - PDT rule applies if trading in a US margin account with <$25k equity.
    Use paper trading and ETFs to test without PDT concerns.
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
    from backports.zoneinfo import ZoneInfo  # Python < 3.9

_NY = ZoneInfo("America/New_York")
_MARKET_OPEN = datetime.time(9, 30)
_MARKET_CLOSE = datetime.time(16, 0)


def _to_ny(ts: datetime.datetime) -> datetime.datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    return ts.astimezone(_NY)


class ORBStrategy(Strategy):
    """Opening Range Breakout — long-only, no overnight holds.

    Args:
        symbols:       Symbols to watch and trade.
        range_minutes: Length of the opening range in minutes. Default: 15.
        exit_time:     NY time to force-close all positions (EOD flatten).
                       Default: 15:55 (5 min before NYSE close).
    """

    def __init__(
        self,
        symbols: List[str],
        range_minutes: int = 15,
        exit_time: datetime.time = datetime.time(15, 55),
    ) -> None:
        super().__init__(symbols)
        self.range_minutes = range_minutes
        self.exit_time = exit_time
        self._range_delta = datetime.timedelta(minutes=range_minutes)

        # Per-symbol state; all reset on each new trading day
        self._cur_date: Dict[str, Optional[datetime.date]] = defaultdict(lambda: None)
        self._range_high: Dict[str, float] = {}
        self._range_low: Dict[str, float] = {}
        self._range_ready: Dict[str, bool] = defaultdict(bool)
        self._traded: Dict[str, bool] = defaultdict(bool)

    def _reset(self, symbol: str, date: datetime.date) -> None:
        self._cur_date[symbol] = date
        self._range_high[symbol] = float("-inf")
        self._range_low[symbol] = float("inf")
        self._range_ready[symbol] = False
        self._traded[symbol] = False

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        for symbol in self.symbols:
            bar = bars.get(symbol)
            if bar is None:
                continue

            ny = _to_ny(bar.timestamp)
            today = ny.date()
            t = ny.time()

            # Skip pre/post market bars
            if t < _MARKET_OPEN or t >= _MARKET_CLOSE:
                continue

            # New trading day → reset all per-day state
            if self._cur_date[symbol] != today:
                self._reset(symbol, today)

            # Range end time = market open + range_minutes
            range_end = (
                datetime.datetime.combine(today, _MARKET_OPEN, tzinfo=_NY)
                + self._range_delta
            ).time()

            pos = portfolio.get_position(symbol)
            in_position = pos is not None and pos.quantity > 0

            # ── 1. EOD exit (highest priority) ──────────────────────────────
            if t >= self.exit_time and in_position:
                signals.append(Signal(
                    symbol=symbol,
                    direction=Direction.FLAT,
                    reason=f"EOD exit @ {t}",
                ))
                self._traded[symbol] = True
                continue

            # ── 2. Building opening range ────────────────────────────────────
            if t < range_end:
                self._range_high[symbol] = max(self._range_high[symbol], bar.high)
                self._range_low[symbol] = min(self._range_low[symbol], bar.low)
                continue

            # ── 3. First bar after range: finalise, skip this bar for trading ─
            if not self._range_ready[symbol]:
                if self._range_high[symbol] == float("-inf"):
                    continue  # no range data (gap open / halt)
                self._range_ready[symbol] = True
                continue

            # ── 4. Stop loss ─────────────────────────────────────────────────
            if in_position and bar.close < self._range_low[symbol]:
                signals.append(Signal(
                    symbol=symbol,
                    direction=Direction.FLAT,
                    reason=(
                        f"Stop: {bar.close:.2f} < range_low {self._range_low[symbol]:.2f}"
                    ),
                ))
                self._traded[symbol] = True
                continue

            # ── 5. Entry: first breakout above range high ────────────────────
            if not self._traded[symbol] and not in_position:
                if bar.close > self._range_high[symbol]:
                    signals.append(Signal(
                        symbol=symbol,
                        direction=Direction.LONG,
                        reason=(
                            f"ORB breakout: {bar.close:.2f} > "
                            f"range_high {self._range_high[symbol]:.2f}"
                        ),
                    ))
                    self._traded[symbol] = True

        return signals
