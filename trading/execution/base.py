"""Abstract executor interface.

Implementations:
  SimulatedExecutor  — fills immediately with slippage (backtest)
  AlpacaExecutor     — submits market orders to Alpaca (paper / live)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from ..models import Order


class Executor(ABC):
    @abstractmethod
    def execute(
        self,
        orders: List[Order],
        prices: Dict[str, float],
        volumes: Optional[Dict[str, float]] = None,
        bar_time: Optional["datetime"] = None,
    ) -> List[Order]:
        """Execute orders and return them with updated status.

        Args:
            orders:   Orders to submit.
            prices:   Current market prices by symbol. Used by the simulated
                      executor; real brokers determine their own fill prices.
            volumes:  Bar volumes by symbol. When provided, the simulated
                      executor caps each fill to max_volume_pct * bar_volume.
            bar_time: Timestamp of the bar at which fills are executed.
                      Used by SimulatedExecutor to set a meaningful filled_at.

        Returns:
            The same order objects, mutated in-place with fill details.
        """
