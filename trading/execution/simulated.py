"""Simulated order execution for backtesting.

Fills at the next bar's open price with slippage and commission.
Handles long entries, long exits, short entries, and short covers.
"""

import logging
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Executor
from ..config import BacktestConfig
from ..models import Order, OrderStatus, Side

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")


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

            # Volume cap: only for long entries (not exits or short entries)
            is_entry = (order.side == Side.BUY and not order.is_short_cover) or \
                       (order.side == Side.SELL and order.is_short_entry)
            if is_entry and volumes is not None and self.config.max_volume_pct > 0:
                bar_vol = volumes.get(order.symbol, 0)
                if bar_vol > 0:
                    vol_cap = int(bar_vol * self.config.max_volume_pct)
                    if vol_cap < order.quantity:
                        order.quantity = vol_cap
                    if order.quantity <= 0:
                        order.status = OrderStatus.REJECTED
                        continue

            slippage = price * self.config.slippage_bps / 10_000
            # Buys fill higher (worse), sells fill lower (worse for both long exits and short entries)
            fill_price = price + slippage if order.side == Side.BUY else price - slippage

            order.fill_price = round(fill_price, 4)
            order.filled_at = bar_time or order.created_at
            order.commission = round(order.quantity * self.config.commission_per_share, 4)
            order.status = OrderStatus.FILLED

            ts_et = bar_time.astimezone(ET) if bar_time else None
            date_str = ts_et.strftime("%Y-%m-%d %H:%M ET") if ts_et else "??"
            side_label = ("SHORT" if order.is_short_entry else
                          "COVER" if order.is_short_cover else
                          order.side.value.upper())
            logger.info("  [fill] %s  %-6s %-5s  ×%-4d @ $%.2f",
                        date_str, order.symbol, side_label, order.quantity, order.fill_price)

        return orders
