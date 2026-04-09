"""Alpaca order executor — paper and live trading.

Submits market orders via the Alpaca REST API.
Paper vs live is determined by AlpacaConfig.paper.

Orders fill asynchronously — status is PENDING after submission.
The live engine re-syncs portfolio state from Alpaca on each bar
rather than tracking individual fill notifications.
"""

import logging
from typing import Dict, List

from .base import Executor
from ..config import AlpacaConfig
from ..models import Order, OrderStatus, Side

logger = logging.getLogger(__name__)


class AlpacaExecutor(Executor):
    def __init__(self, config: AlpacaConfig) -> None:
        from alpaca.trading.client import TradingClient

        self._client = TradingClient(
            api_key=config.api_key,
            secret_key=config.secret_key,
            paper=config.paper,
        )
        self._paper = config.paper

    def execute(self, orders: List[Order], prices: Dict[str, float] = None) -> List[Order]:
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        mode = "PAPER" if self._paper else "LIVE"

        for order in orders:
            try:
                alpaca_side = OrderSide.BUY if order.side == Side.BUY else OrderSide.SELL
                request = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.quantity,
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY,
                )
                alpaca_order = self._client.submit_order(order_data=request)
                order.id = str(alpaca_order.id)
                order.status = OrderStatus.PENDING  # fills are async

                logger.info("[%s] Submitted %s", mode, order)

            except Exception as exc:
                logger.error("[%s] Order failed for %s: %s", mode, order.symbol, exc)
                order.status = OrderStatus.REJECTED

        return orders
