"""Base class for all trading strategies."""

from abc import ABC, abstractmethod
from typing import Dict, List

from ..models import Bar, Signal
from ..portfolio import Portfolio


class Strategy(ABC):
    def __init__(self, symbols: List[str]) -> None:
        self.symbols = symbols

    @abstractmethod
    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        """Process a new bar and return signals. Return [] for no action."""

    @abstractmethod
    def rules(self) -> List[str]:
        """Return human-readable list of strategy rules for the frontend."""

    def on_start(self) -> None:
        """Called once before the first bar."""

    def on_stop(self) -> None:
        """Called once after the last bar."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(symbols={self.symbols})"
