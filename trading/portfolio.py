"""Portfolio: tracks cash, positions, and trade history.

Long positions: quantity > 0, cash decreases on entry.
Short positions: quantity < 0, cash increases on entry (receive proceeds),
                 margin requirement = abs(quantity) * entry_price held as collateral.

Equity = cash + sum(quantity * price) for each position.
For short positions, quantity is negative, so short losses subtract from equity correctly.
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

    def get_position(self, symbol: str) -> Optional[Position]:
        return self.positions.get(symbol)

    def equity(self, prices: Dict[str, float]) -> float:
        """Cash + mark-to-market value of all open positions.
        Short positions have negative market value, which correctly reduces equity
        when the price rises against the short.
        """
        mkt = sum(
            pos.quantity * prices.get(pos.symbol, pos.avg_price)
            for pos in self.positions.values()
        )
        return self.cash + mkt

    def apply_fill(self, order: Order) -> None:
        """Update cash and positions after a confirmed fill."""
        assert order.is_filled and order.fill_price is not None

        price = order.fill_price
        qty = order.quantity
        cost = qty * price

        if order.side == Side.BUY:
            if order.is_short_cover:
                # Covering a short: buy back shares, cash decreases
                self.cash -= cost + order.commission
                pos = self.positions.get(order.symbol)
                if pos:
                    pos.quantity += qty   # was negative, moves toward zero
                    if pos.quantity == 0:
                        del self.positions[order.symbol]
            else:
                # Normal long entry
                self.cash -= cost + order.commission
                pos = self.positions.get(order.symbol)
                if pos is None:
                    self.positions[order.symbol] = Position(
                        symbol=order.symbol, quantity=qty, avg_price=price
                    )
                else:
                    total_qty = pos.quantity + qty
                    pos.avg_price = (pos.quantity * pos.avg_price + qty * price) / total_qty
                    pos.quantity = total_qty

        else:  # Side.SELL
            if order.is_short_entry:
                # Opening a short: sell borrowed shares, cash increases
                self.cash += cost - order.commission
                pos = self.positions.get(order.symbol)
                if pos is None:
                    self.positions[order.symbol] = Position(
                        symbol=order.symbol, quantity=-qty, avg_price=price
                    )
                else:
                    # Averaging into short
                    new_qty = pos.quantity - qty   # more negative
                    if new_qty != 0:
                        pos.avg_price = (
                            abs(pos.quantity) * pos.avg_price + qty * price
                        ) / abs(new_qty)
                    pos.quantity = new_qty
            else:
                # Closing a long position
                self.cash += cost - order.commission
                pos = self.positions.get(order.symbol)
                if pos:
                    pos.quantity -= qty
                    if pos.quantity == 0:
                        del self.positions[order.symbol]

        self.filled_orders.append(order)
        logger.info(
            "%s %d %s @ $%.2f  cash → $%.2f",
            order.side.value.upper(), qty, order.symbol, price, self.cash,
        )

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
