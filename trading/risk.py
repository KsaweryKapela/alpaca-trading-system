"""Risk manager: converts signals into sized, validated orders.

Rules enforced:
  - Max position size as % of total equity
  - Max number of concurrent open positions
  - Minimum cash buffer (never go fully invested)
  - No re-entry if already in the position
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .config import RiskConfig
from .models import Direction, Order, Signal, Side
from .portfolio import Portfolio

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(self, config: RiskConfig) -> None:
        self.config = config

    def validate(
        self,
        signals: List[Signal],
        portfolio: Portfolio,
        prices: Dict[str, float],
    ) -> List[Order]:
        """Convert signals into orders, applying position sizing and risk rules."""
        orders: List[Order] = []
        equity = portfolio.equity(prices)
        cash_floor = equity * self.config.min_cash_pct

        for signal in signals:
            price = prices.get(signal.symbol)
            if not price:
                logger.warning("No price for %s — skipping signal", signal.symbol)
                continue

            if signal.direction == Direction.FLAT:
                order = self._build_close_order(signal, portfolio)
            elif signal.direction == Direction.LONG:
                order = self._build_long_order(signal, portfolio, price, equity, cash_floor)
            else:
                continue

            if order:
                logger.debug("Order queued: %s", order)
                orders.append(order)

        return orders

    def _build_close_order(self, signal: Signal, portfolio: Portfolio) -> Optional[Order]:
        pos = portfolio.get_position(signal.symbol)
        if not pos or pos.quantity == 0:
            return None
        return Order(
            symbol=signal.symbol,
            side=Side.SELL if pos.quantity > 0 else Side.BUY,
            quantity=abs(pos.quantity),
            created_at=datetime.now(timezone.utc),
        )

    def _build_long_order(
        self,
        signal: Signal,
        portfolio: Portfolio,
        price: float,
        equity: float,
        cash_floor: float,
    ) -> Optional[Order]:
        pos = portfolio.get_position(signal.symbol)
        if pos and pos.quantity > 0:
            return None  # already long, skip

        if len(portfolio.positions) >= self.config.max_positions:
            logger.warning(
                "Max positions (%d) reached — skipping %s",
                self.config.max_positions, signal.symbol,
            )
            return None

        # Determine quantity
        if signal.quantity:
            qty = signal.quantity
        else:
            max_value = equity * self.config.max_position_pct
            qty = int(max_value / price)

        # Constrain by available cash above the floor
        available = portfolio.cash - cash_floor
        qty = min(qty, int(available / price))

        if qty <= 0:
            logger.warning("Insufficient cash for %s — skipping", signal.symbol)
            return None

        return Order(
            symbol=signal.symbol,
            side=Side.BUY,
            quantity=qty,
            created_at=datetime.now(timezone.utc),
        )
