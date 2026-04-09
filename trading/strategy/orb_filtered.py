"""ORB with volume confirmation and market regime filter.

Extends the base ORBStrategy with two additional entry gates:

  1. Volume filter
     Entry bar volume must be >= volume_multiplier × average range bar volume.
     Low-volume breakouts are noise; genuine breakouts expand volume.

  2. Regime filter
     Only trade on days where the regime symbol (default: SPY) closed the
     previous session above its N-day SMA. ORB works on trending days;
     the regime filter skips choppy/bearish market conditions.

Both filters are optional:
  - Set volume_multiplier=0 to disable volume filter.
  - Set regime_symbol=None to disable regime filter.

Regime data is loaded from yfinance (daily bars, 3 years) at construction
time. yfinance daily data is available for 50+ years, so this always works
regardless of the test period.
"""

import datetime
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set

import pandas as pd

from .orb import ORBStrategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

_NY = ZoneInfo("America/New_York")


class ORBFilteredStrategy(ORBStrategy):
    """ORB with volume confirmation and market regime filter.

    Args:
        symbols:           Symbols to watch and trade.
        range_minutes:     Opening range duration in minutes. Default: 15.
        exit_time:         NY time for EOD flatten. Default: 15:55.
        volume_multiplier: Entry bar volume must be >= this × avg range volume.
                           Set to 0 to disable. Default: 1.5.
        sma_period:        SMA period for regime filter. Default: 20.
        regime_symbol:     Symbol used to determine market regime.
                           Set to None to disable. Default: "SPY".
    """

    def __init__(
        self,
        symbols: List[str],
        range_minutes: int = 15,
        exit_time: datetime.time = datetime.time(15, 55),
        volume_multiplier: float = 1.5,
        sma_period: int = 20,
        regime_symbol: Optional[str] = "SPY",
    ) -> None:
        super().__init__(symbols, range_minutes, exit_time)
        self.volume_multiplier = volume_multiplier
        self.sma_period = sma_period
        self.regime_symbol = regime_symbol

        # {date: True if above SMA (trade allowed)}
        self._regime_cache: Dict[datetime.date, bool] = {}
        if regime_symbol:
            self._load_regime(regime_symbol, sma_period)

        # Per-symbol range bar volumes (reset daily alongside parent state)
        self._range_volumes: Dict[str, List[float]] = defaultdict(list)

    # ── Regime data loading ───────────────────────────────────────────────────

    def _load_regime(self, symbol: str, sma_period: int) -> None:
        """Load daily bars and pre-compute above/below SMA for every date."""
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed — regime filter disabled")
            self.regime_symbol = None
            return

        logger.info("Loading regime data for %s (%d-day SMA)...", symbol, sma_period)
        df = yf.download(symbol, period="5y", interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            logger.warning("No regime data returned for %s — regime filter disabled", symbol)
            self.regime_symbol = None
            return

        # Handle MultiIndex columns from newer yfinance versions
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        close = df["Close"].squeeze()
        sma = close.rolling(sma_period).mean()

        count = 0
        for dt, c, s in zip(close.index, close.values, sma.values):
            if pd.notna(s):
                self._regime_cache[dt.date()] = bool(c > s)
                count += 1

        logger.info("Regime cache built: %d trading days for %s", count, symbol)

    def _is_regime_ok(self, date: datetime.date) -> bool:
        """Return True if trading is allowed on this date."""
        if not self.regime_symbol:
            return True
        # Use previous session's close (most recent date before today in cache)
        # to avoid lookahead into today's close.
        prev = None
        for cached_date in sorted(self._regime_cache):
            if cached_date < date:
                prev = cached_date
            elif cached_date >= date:
                break
        if prev is None:
            return True  # no history → allow
        return self._regime_cache[prev]

    # ── State reset ──────────────────────────────────────────────────────────

    def _reset(self, symbol: str, date: datetime.date) -> None:
        super()._reset(symbol, date)
        self._range_volumes[symbol] = []

    # ── Bar handler ──────────────────────────────────────────────────────────

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        for symbol in self.symbols:
            bar = bars.get(symbol)
            if bar is None:
                continue

            from .orb import _to_ny, _MARKET_OPEN, _MARKET_CLOSE
            ny = _to_ny(bar.timestamp)
            today = ny.date()
            t = ny.time()

            if t < _MARKET_OPEN or t >= _MARKET_CLOSE:
                continue

            if self._cur_date[symbol] != today:
                self._reset(symbol, today)

            range_end = (
                datetime.datetime.combine(today, _MARKET_OPEN, tzinfo=_NY)
                + self._range_delta
            ).time()

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
                continue

            # ── 2. Build opening range ───────────────────────────────────────
            if t < range_end:
                self._range_high[symbol] = max(self._range_high[symbol], bar.high)
                self._range_low[symbol] = min(self._range_low[symbol], bar.low)
                self._range_volumes[symbol].append(bar.volume)
                continue

            # ── 3. Finalise range (first bar after range window) ─────────────
            if not self._range_ready[symbol]:
                if self._range_high[symbol] == float("-inf"):
                    continue  # no range bars (halt / gap open)
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

            # ── 5. Entry: volume + regime gated ─────────────────────────────
            if not self._traded[symbol] and not in_position:
                if bar.close <= self._range_high[symbol]:
                    continue  # no breakout

                # Regime filter: skip if market is not in uptrend
                if self.regime_symbol and not self._is_regime_ok(today):
                    logger.debug(
                        "%s %s: skipping entry — regime filter (SPY below %d-day SMA)",
                        today, symbol, self.sma_period,
                    )
                    continue

                # Volume filter: skip if entry bar is low volume
                if self.volume_multiplier > 0 and self._range_volumes[symbol]:
                    avg_range_vol = sum(self._range_volumes[symbol]) / len(self._range_volumes[symbol])
                    if avg_range_vol > 0 and bar.volume < self.volume_multiplier * avg_range_vol:
                        logger.debug(
                            "%s %s: skipping entry — volume filter "
                            "(bar=%d < %.1f×avg=%d)",
                            today, symbol, int(bar.volume),
                            self.volume_multiplier, int(avg_range_vol),
                        )
                        continue

                signals.append(Signal(
                    symbol=symbol,
                    direction=Direction.LONG,
                    reason=(
                        f"ORB+vol+regime breakout: {bar.close:.2f} > "
                        f"range_high {self._range_high[symbol]:.2f}, "
                        f"vol={int(bar.volume)}"
                    ),
                ))
                self._traded[symbol] = True

        return signals
