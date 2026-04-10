"""RSI Mean Reversion strategy — long/short.

Long when RSI falls below oversold threshold (buy the dip).
Short when RSI rises above overbought threshold (sell the rip).
Exit long when RSI recovers above exit_long threshold.
Exit short when RSI falls below exit_short threshold.

Uses Wilder's RSI on daily close prices.
"""

from typing import Dict, List, Optional

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio


class RSIReversionStrategy(Strategy):
    """RSI mean reversion: long on oversold, short on overbought."""

    name = "rsi_reversion"
    label = "RSI Mean Reversion"

    def __init__(
        self,
        symbols: List[str],
        rsi_period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        exit_long: float = 55.0,   # exit long when RSI recovers here
        exit_short: float = 45.0,  # exit short when RSI drops here
    ) -> None:
        super().__init__(symbols)
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.exit_long = exit_long
        self.exit_short = exit_short
        self._state: Dict[str, dict] = {}

    def on_start(self) -> None:
        self._state = {
            sym: {"avg_gain": None, "avg_loss": None, "prev_close": None, "bars": 0}
            for sym in self.symbols
        }

    def rules(self) -> List[str]:
        return [
            f"Go LONG when RSI({self.rsi_period}) drops below {self.oversold} (oversold)",
            f"Exit LONG when RSI({self.rsi_period}) recovers above {self.exit_long}",
            f"Go SHORT when RSI({self.rsi_period}) rises above {self.overbought} (overbought)",
            f"Exit SHORT when RSI({self.rsi_period}) drops below {self.exit_short}",
            f"RSI uses Wilder smoothing on daily close prices",
        ]

    def _update_rsi(self, state: dict, close: float) -> Optional[float]:
        """Update Wilder RSI state, return current RSI or None if not ready."""
        prev = state["prev_close"]
        state["prev_close"] = close
        state["bars"] += 1

        if prev is None:
            return None

        change = close - prev
        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        if state["avg_gain"] is None:
            # Accumulate initial period
            if state["bars"] <= self.rsi_period:
                state["_gains"] = state.get("_gains", []) + [gain]
                state["_losses"] = state.get("_losses", []) + [loss]
                if state["bars"] == self.rsi_period:
                    state["avg_gain"] = sum(state["_gains"]) / self.rsi_period
                    state["avg_loss"] = sum(state["_losses"]) / self.rsi_period
                return None
        else:
            # Wilder smoothing
            state["avg_gain"] = (state["avg_gain"] * (self.rsi_period - 1) + gain) / self.rsi_period
            state["avg_loss"] = (state["avg_loss"] * (self.rsi_period - 1) + loss) / self.rsi_period

        if state["avg_loss"] == 0:
            return 100.0
        rs = state["avg_gain"] / state["avg_loss"]
        return 100 - 100 / (1 + rs)

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        for symbol in self.symbols:
            bar = bars.get(symbol)
            if bar is None:
                continue

            state = self._state[symbol]
            rsi = self._update_rsi(state, bar.close)
            if rsi is None:
                continue

            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            if rsi < self.oversold and current_qty <= 0:
                if current_qty < 0:
                    signals.append(Signal(symbol, Direction.FLAT, reason="cover short"))
                signals.append(Signal(symbol, Direction.LONG, reason=f"RSI={rsi:.1f}<{self.oversold}"))

            elif rsi > self.overbought and current_qty >= 0:
                if current_qty > 0:
                    signals.append(Signal(symbol, Direction.FLAT, reason="close long"))
                signals.append(Signal(symbol, Direction.SHORT, reason=f"RSI={rsi:.1f}>{self.overbought}"))

            elif current_qty > 0 and rsi > self.exit_long:
                signals.append(Signal(symbol, Direction.FLAT, reason=f"RSI={rsi:.1f}>{self.exit_long} exit long"))

            elif current_qty < 0 and rsi < self.exit_short:
                signals.append(Signal(symbol, Direction.FLAT, reason=f"RSI={rsi:.1f}<{self.exit_short} exit short"))

        return signals
