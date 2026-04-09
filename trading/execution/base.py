"""Abstract executor interface.

Implementations:
  SimulatedExecutor  — fills immediately with slippage (backtest)
  AlpacaExecutor     — submits market orders to Alpaca (paper / live)
"""

from abc import ABC, abstractmethod
from typing import Dict, List

from ..models import Order


class Executor(ABC):
    @abstractmethod
    def execute(self, orders: List[Order], prices: Dict[str, float]) -> List[Order]:
        """Execute orders and return them with updated status.

        Args:
            orders: Orders to submit.
            prices: Current market prices by symbol. Used by the simulated
                    executor; real brokers determine their own fill prices.

        Returns:
            The same order objects, mutated in-place with fill details.
        """
