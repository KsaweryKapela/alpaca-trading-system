"""Risk manager: converts signals into sized, validated orders.

Rules enforced:
  - Max position size as % of total equity (scaled by leverage)
  - Max number of concurrent open positions
  - Minimum cash buffer (long entries only; short entries use proceeds)
  - No re-entry if already in the same direction
  - Daily loss limit kill-switch (blocks new entries, allows exits)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .config import RiskConfig
from .models import Direction, Order, Signal, Side
from .portfolio import Portfolio

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(self, config: RiskConfig, leverage: float = 1.0) -> None:
        self.config = config
        self.leverage = leverage  # 1.0 = no leverage; 2.0 = 2x
        self._day_start_equity: float = 0.0

    def new_day(self, equity: float) -> None:
        self._day_start_equity = equity

    def is_halted(self, portfolio: Portfolio, prices: Dict[str, float]) -> bool:
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
        if self.is_halted(portfolio, prices):
            logger.warning("Daily loss limit breached — blocking new entries")
            signals = [s for s in signals if s.direction == Direction.FLAT]
            if not signals:
                return []

        orders: List[Order] = []
        equity = portfolio.equity(prices)
        cash_floor = equity * self.config.min_cash_pct
        committed_cash: float = 0.0
        new_positions: int = 0

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
                if order:
                    committed_cash += order.quantity * price
                    new_positions += 1
            elif signal.direction == Direction.SHORT:
                order = self._build_short_order(
                    signal, portfolio, price, equity, new_positions,
                )
                if order:
                    new_positions += 1
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
        if pos.quantity > 0:
            # Close long: sell
            return Order(
                symbol=signal.symbol, side=Side.SELL, quantity=abs(pos.quantity),
                created_at=datetime.now(timezone.utc),
            )
        else:
            # Cover short: buy
            return Order(
                symbol=signal.symbol, side=Side.BUY, quantity=abs(pos.quantity),
                created_at=datetime.now(timezone.utc), is_short_cover=True,
            )

    def _build_long_order(
        self, signal, portfolio, price, equity, cash_floor, committed_cash, new_positions,
    ) -> Optional[Order]:
        pos = portfolio.get_position(signal.symbol)
        if pos and pos.quantity > 0:
            return None  # already long

        total_positions = len(portfolio.positions) + new_positions
        if total_positions >= self.config.max_positions:
            logger.warning("Max positions reached — skipping %s", signal.symbol)
            return None

        lev = signal.leverage if signal.leverage is not None else self.leverage
        if signal.quantity:
            qty = signal.quantity
        else:
            max_value = equity * self.config.max_position_pct * lev
            qty = int(max_value / price)

        available = portfolio.cash - cash_floor - committed_cash
        qty = min(qty, int(available / price))

        if qty <= 0:
            logger.warning("Insufficient cash for %s — skipping", signal.symbol)
            return None

        return Order(
            symbol=signal.symbol, side=Side.BUY, quantity=qty,
            created_at=datetime.now(timezone.utc), leverage=lev,
        )

    def _build_short_order(
        self, signal, portfolio, price, equity, new_positions,
    ) -> Optional[Order]:
        pos = portfolio.get_position(signal.symbol)
        if pos and pos.quantity < 0:
            return None  # already short

        total_positions = len(portfolio.positions) + new_positions
        if total_positions >= self.config.max_positions:
            logger.warning("Max positions reached — skipping %s", signal.symbol)
            return None

        lev = signal.leverage if signal.leverage is not None else self.leverage
        if signal.quantity:
            qty = signal.quantity
        else:
            max_value = equity * self.config.max_position_pct * lev
            qty = int(max_value / price)

        if qty <= 0:
            logger.warning("Zero quantity for short %s — skipping", signal.symbol)
            return None

        return Order(
            symbol=signal.symbol, side=Side.SELL, quantity=qty,
            created_at=datetime.now(timezone.utc), is_short_entry=True, leverage=lev,
        )
