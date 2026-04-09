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
from typing import Dict, List, Optional

from .base import Executor
from ..config import BacktestConfig
from ..models import Order, OrderStatus, Side

logger = logging.getLogger(__name__)


class SimulatedExecutor(Executor):
    def __init__(self, config: BacktestConfig) -> None:
        self.config = config

    def execute(
        self,
        orders: List[Order],
        prices: Dict[str, float],
        volumes: Optional[Dict[str, float]] = None,
        bar_time=None,
    ) -> List[Order]:
        for order in orders:
            price = prices.get(order.symbol)
            if price is None:
                logger.warning("No fill price for %s — rejecting", order.symbol)
                order.status = OrderStatus.REJECTED
                continue

            # Cap fill quantity to max_volume_pct of the bar's volume.
            # Only applied to buys (entries) — never to sells (exits), so that
            # closing an existing position is never split into partial fills.
            if order.side == Side.BUY and volumes is not None and self.config.max_volume_pct > 0:
                bar_vol = volumes.get(order.symbol, 0)
                if bar_vol > 0:
                    vol_cap = int(bar_vol * self.config.max_volume_pct)
                    if vol_cap < order.quantity:
                        logger.debug(
                            "Volume cap: %s buy reduced %d → %d shares (bar vol=%d)",
                            order.symbol, order.quantity, vol_cap, int(bar_vol),
                        )
                        order.quantity = vol_cap
                    if order.quantity <= 0:
                        order.status = OrderStatus.REJECTED
                        continue

            slippage = price * self.config.slippage_bps / 10_000
            fill_price = price + slippage if order.side == Side.BUY else price - slippage

            order.fill_price = round(fill_price, 4)
            # Use bar_time (the fill bar's timestamp) so extended_metrics()
            # can compute accurate trade durations across bars.
            order.filled_at = bar_time or order.created_at
            order.commission = round(order.quantity * self.config.commission_per_share, 4)
            order.status = OrderStatus.FILLED

            logger.debug("Simulated fill: %s", order)

        return orders
