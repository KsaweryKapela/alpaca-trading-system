"""Core data models shared across all layers."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Direction(Enum):
    LONG = "long"
    FLAT = "flat"   # exit / close position


class Side(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Bar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Signal:
    symbol: str
    direction: Direction
    quantity: Optional[int] = None   # None → risk manager decides size
    reason: str = ""


@dataclass
class Order:
    symbol: str
    side: Side
    quantity: int
    created_at: datetime
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    status: OrderStatus = OrderStatus.PENDING
    fill_price: Optional[float] = None
    filled_at: Optional[datetime] = None
    commission: float = 0.0

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    def __repr__(self) -> str:
        s = f"Order({self.side.value.upper()} {self.quantity} {self.symbol} [{self.status.value}]"
        if self.fill_price:
            s += f" @ ${self.fill_price:.2f}"
        return s + ")"


@dataclass
class Position:
    symbol: str
    quantity: int       # positive = long
    avg_price: float

    def market_value(self, price: float) -> float:
        return self.quantity * price

    def unrealized_pnl(self, price: float) -> float:
        return self.quantity * (price - self.avg_price)

    def __repr__(self) -> str:
        return f"Position({self.symbol}: {self.quantity} @ ${self.avg_price:.2f})"
