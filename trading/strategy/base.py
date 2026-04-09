"""Base class for all trading strategies.

A strategy is a stateful object that:
  1. Receives bars on each timestep
  2. Maintains its own internal state (indicators, history, etc.)
  3. Returns a list of signals

Strategies must not place orders directly — they only return signals.
The risk manager and executor handle sizing and execution.
"""

from abc import ABC, abstractmethod
from typing import Dict, List

from ..models import Bar, Signal
from ..portfolio import Portfolio


class Strategy(ABC):
    def __init__(self, symbols: List[str]) -> None:
        self.symbols = symbols

    @abstractmethod
    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        """Process a new timestep and return trading signals.

        Args:
            bars: Available bars keyed by symbol. Not all symbols are
                  guaranteed to be present (halts, data gaps).
            portfolio: Current portfolio state. Treat as read-only.

        Returns:
            List of Signal objects. Return [] for no action.
        """

    def on_start(self) -> None:
        """Called once before the first bar. Override for initialization."""

    def on_stop(self) -> None:
        """Called once after the last bar. Override for cleanup/reporting."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(symbols={self.symbols})"
