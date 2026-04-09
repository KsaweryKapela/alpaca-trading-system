"""Portfolio: tracks cash, positions, and trade history.

Updated by the execution layer after fills.
Read by strategy and risk manager to inform decisions.
"""

import logging
from typing import Dict, List, Optional

from .models import Order, Position, Side

logger = logging.getLogger(__name__)


class Portfolio:
    def __init__(self, initial_cash: float) -> None:
        self.cash: float = initial_cash
        self.positions: Dict[str, Position] = {}
        self.filled_orders: List[Order] = []
        self._initial_cash: float = initial_cash

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_position(self, symbol: str) -> Optional[Position]:
        return self.positions.get(symbol)

    def equity(self, prices: Dict[str, float]) -> float:
        """Cash + mark-to-market value of all open positions."""
        mkt = sum(
            pos.quantity * prices.get(pos.symbol, pos.avg_price)
            for pos in self.positions.values()
        )
        return self.cash + mkt

    # ── Write ─────────────────────────────────────────────────────────────────

    def apply_fill(self, order: Order) -> None:
        """Update cash and positions after a confirmed fill."""
        assert order.is_filled and order.fill_price is not None, f"Order not filled: {order}"

        cost = order.quantity * order.fill_price

        if order.side == Side.BUY:
            self.cash -= cost + order.commission
            pos = self.positions.get(order.symbol)
            if pos is None:
                self.positions[order.symbol] = Position(
                    symbol=order.symbol,
                    quantity=order.quantity,
                    avg_price=order.fill_price,
                )
            else:
                total_qty = pos.quantity + order.quantity
                pos.avg_price = (
                    pos.quantity * pos.avg_price + order.quantity * order.fill_price
                ) / total_qty
                pos.quantity = total_qty
        else:  # SELL
            self.cash += cost - order.commission
            pos = self.positions.get(order.symbol)
            if pos:
                pos.quantity -= order.quantity
                if pos.quantity == 0:
                    del self.positions[order.symbol]

        self.filled_orders.append(order)
        logger.info(
            "%s %d %s @ $%.2f  (commission $%.4f)  cash → $%.2f",
            order.side.value.upper(), order.quantity, order.symbol,
            order.fill_price, order.commission, self.cash,
        )

    # ── Reporting ─────────────────────────────────────────────────────────────

    def summary(self, prices: Dict[str, float]) -> dict:
        equity = self.equity(prices)
        return {
            "cash": round(self.cash, 2),
            "equity": round(equity, 2),
            "pnl": round(equity - self._initial_cash, 2),
            "pnl_pct": round((equity / self._initial_cash - 1) * 100, 2),
            "open_positions": len(self.positions),
            "total_trades": len(self.filled_orders),
        }

    def __repr__(self) -> str:
        return (
            f"Portfolio(cash=${self.cash:,.2f}, "
            f"positions={list(self.positions.keys())})"
        )
