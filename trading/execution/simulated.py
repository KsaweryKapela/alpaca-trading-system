"""Simulated order execution for backtesting.

Fills orders at the provided price with configurable slippage and commission.

Execution assumptions:
  - Fill price = bar close ± slippage (buys worse, sells worse)
  - Commission = flat per-share fee
  - No partial fills, no queue priority

For slightly more realistic results, pass next-bar open prices instead of
current-bar close prices. The engine comment shows how to do this.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List

from .base import Executor
from ..config import BacktestConfig
from ..models import Order, OrderStatus, Side

logger = logging.getLogger(__name__)


class SimulatedExecutor(Executor):
    def __init__(self, config: BacktestConfig) -> None:
        self.config = config

    def execute(self, orders: List[Order], prices: Dict[str, float]) -> List[Order]:
        for order in orders:
            price = prices.get(order.symbol)
            if price is None:
                logger.warning("No fill price for %s — rejecting", order.symbol)
                order.status = OrderStatus.REJECTED
                continue

            slippage = price * self.config.slippage_bps / 10_000
            fill_price = price + slippage if order.side == Side.BUY else price - slippage

            order.fill_price = round(fill_price, 4)
            order.filled_at = datetime.now(timezone.utc)
            order.commission = round(order.quantity * self.config.commission_per_share, 4)
            order.status = OrderStatus.FILLED

            logger.debug("Simulated fill: %s", order)

        return orders
