"""SMA crossover strategy — the canonical rule-based example.

Signal logic (per symbol):
  LONG  when fast SMA crosses *above* slow SMA  (bullish crossover)
  FLAT  when fast SMA crosses *below* slow SMA  (exit signal)

No position management here — that belongs to the risk manager.
"""

from collections import deque
from typing import Deque, Dict, List, Optional

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio


class SMACrossStrategy(Strategy):
    """Moving-average crossover strategy.

    Args:
        symbols:      Symbols to watch and potentially trade.
        fast_period:  Lookback for the fast SMA.
        slow_period:  Lookback for the slow SMA.
    """

    def __init__(
        self,
        symbols: List[str],
        fast_period: int = 20,
        slow_period: int = 50,
    ) -> None:
        super().__init__(symbols)
        if fast_period >= slow_period:
            raise ValueError(
                f"fast_period ({fast_period}) must be < slow_period ({slow_period})"
            )
        self.fast_period = fast_period
        self.slow_period = slow_period

        # Per-symbol rolling price windows
        self._prices: Dict[str, Deque[float]] = {
            s: deque(maxlen=slow_period) for s in symbols
        }
        self._prev_fast_above: Dict[str, Optional[bool]] = {s: None for s in symbols}

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        for symbol in self.symbols:
            bar = bars.get(symbol)
            if bar is None:
                continue

            self._prices[symbol].append(bar.close)
            prices = list(self._prices[symbol])

            if len(prices) < self.slow_period:
                continue  # not enough history yet

            fast_sma = sum(prices[-self.fast_period:]) / self.fast_period
            slow_sma = sum(prices) / self.slow_period
            fast_above = fast_sma > slow_sma

            prev = self._prev_fast_above[symbol]
            if prev is not None:
                if fast_above and not prev:
                    signals.append(Signal(
                        symbol=symbol,
                        direction=Direction.LONG,
                        reason=f"SMA{self.fast_period} crossed above SMA{self.slow_period}",
                    ))
                elif not fast_above and prev:
                    signals.append(Signal(
                        symbol=symbol,
                        direction=Direction.FLAT,
                        reason=f"SMA{self.fast_period} crossed below SMA{self.slow_period}",
                    ))

            self._prev_fast_above[symbol] = fast_above

        return signals
