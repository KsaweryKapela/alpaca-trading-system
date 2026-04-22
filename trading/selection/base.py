"""Base classes for stock selection."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import date

from ..models import Bar


@dataclass
class ScoredStock:
    """A stock with a selection score and metadata."""
    symbol: str
    score: float                     # higher = more tradable
    direction_bias: str = "neutral"  # "long", "short", "neutral"
    tags: Dict[str, float] = field(default_factory=dict)  # component scores

    def __repr__(self) -> str:
        return f"ScoredStock({self.symbol} score={self.score:.2f} bias={self.direction_bias})"


class Selector(ABC):
    """Base class for stock selectors.

    A selector receives all bars for all symbols on each tick and maintains
    internal state. At any point, it can be asked for the current selection
    (ranked list of ScoredStock).
    """

    def __init__(self, symbols: List[str]) -> None:
        self.symbols = symbols

    @abstractmethod
    def update(self, bars: Dict[str, Bar], current_date: date) -> None:
        """Update internal state with new bar data."""

    @abstractmethod
    def select(self, top_n: int = 10) -> List[ScoredStock]:
        """Return the top-N stocks ranked by score."""

    def reset_day(self, current_date: date) -> None:
        """Called at the start of each new day."""
