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
        self._day_start_equity: float = 0.0

    def new_day(self, equity: float) -> None:
        """Record equity at the start of a new trading day for loss-limit tracking."""
        self._day_start_equity = equity

    def is_halted(self, portfolio: Portfolio, prices: Dict[str, float]) -> bool:
        """Return True if the daily loss limit has been breached."""
        if self.config.max_daily_loss_pct <= 0 or self._day_start_equity <= 0:
            return False
        equity = portfolio.equity(prices)
        pnl_pct = (equity - self._day_start_equity) / self._day_start_equity
        return pnl_pct < -self.config.max_daily_loss_pct

    def validate(
        self,
        signals: List[Signal],
        portfolio: Portfolio,
        prices: Dict[str, float],
    ) -> List[Order]:
        """Convert signals into orders, applying position sizing and risk rules.

        Tracks cash committed and positions opened within the same batch so
        that multiple simultaneous buy signals cannot together exceed the
        intended cash buffer or position limits.

        When the daily loss limit is breached, new long entries are blocked.
        Exit signals (FLAT) are always allowed through.
        """
        if self.is_halted(portfolio, prices):
            logger.warning("Daily loss limit breached — blocking new entries")
            signals = [s for s in signals if s.direction == Direction.FLAT]
            if not signals:
                return []

        orders: List[Order] = []
        equity = portfolio.equity(prices)
        cash_floor = equity * self.config.min_cash_pct
        committed_cash: float = 0.0   # cash reserved by earlier orders in this batch
        new_positions: int = 0        # positions opened by earlier orders in this batch

        for signal in signals:
            price = prices.get(signal.symbol)
            if not price:
                logger.warning("No price for %s — skipping signal", signal.symbol)
                continue

            if signal.direction == Direction.FLAT:
                order = self._build_close_order(signal, portfolio)
            elif signal.direction == Direction.LONG:
                order = self._build_long_order(
                    signal, portfolio, price, equity, cash_floor,
                    committed_cash, new_positions,
                )
            else:
                continue

            if order:
                if order.side == Side.BUY:
                    committed_cash += order.quantity * price
                    new_positions += 1
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
        committed_cash: float,
        new_positions: int,
    ) -> Optional[Order]:
        pos = portfolio.get_position(signal.symbol)
        if pos and pos.quantity > 0:
            return None  # already long, skip

        # Account for positions already queued in this same batch
        total_positions = len(portfolio.positions) + new_positions
        if total_positions >= self.config.max_positions:
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

        # Constrain by cash still available after earlier orders in this batch
        available = portfolio.cash - cash_floor - committed_cash
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
