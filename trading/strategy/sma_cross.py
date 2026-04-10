"""SMA Crossover strategy — long/short.

Long when fast SMA > slow SMA (uptrend).
Short when fast SMA < slow SMA (downtrend).
Uses daily close prices. Requires slow_period bars of warm-up.
"""

from collections import deque
from typing import Dict, List

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio


class SMACrossStrategy(Strategy):
    """SMA crossover: go long or short based on moving average alignment."""

    name = "sma_cross"
    label = "SMA Crossover"

    def __init__(
        self,
        symbols: List[str],
        fast_period: int = 20,
        slow_period: int = 50,
    ) -> None:
        super().__init__(symbols)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self._closes: Dict[str, deque] = {}

    def on_start(self) -> None:
        self._closes = {sym: deque(maxlen=self.slow_period) for sym in self.symbols}

    def rules(self) -> List[str]:
        return [
            f"Go LONG when {self.fast_period}-day SMA crosses above {self.slow_period}-day SMA",
            f"Go SHORT when {self.fast_period}-day SMA crosses below {self.slow_period}-day SMA",
            "Hold until the opposite crossover occurs",
            "Position sized by portfolio risk manager (max position % of equity)",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        for symbol in self.symbols:
            bar = bars.get(symbol)
            if bar is None:
                continue

            closes = self._closes[symbol]
            closes.append(bar.close)

            if len(closes) < self.slow_period:
                continue

            closes_list = list(closes)
            fast_sma = sum(closes_list[-self.fast_period:]) / self.fast_period
            slow_sma = sum(closes_list) / self.slow_period

            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            if fast_sma > slow_sma:
                if current_qty <= 0:
                    if current_qty < 0:
                        # Cover short first
                        signals.append(Signal(symbol, Direction.FLAT, reason="cover short"))
                    signals.append(Signal(symbol, Direction.LONG, reason=f"SMA{self.fast_period}>{self.slow_period}"))
            elif fast_sma < slow_sma:
                if current_qty >= 0:
                    if current_qty > 0:
                        # Close long first
                        signals.append(Signal(symbol, Direction.FLAT, reason="close long"))
                    signals.append(Signal(symbol, Direction.SHORT, reason=f"SMA{self.fast_period}<{self.slow_period}"))

        return signals
