"""Live and paper trading engine.

Data flow per bar:
  Alpaca WebSocket bar → portfolio sync → strategy.on_bar() → risk.validate() → Alpaca order submit

The portfolio is re-synced from Alpaca before each decision to capture
async fills and any manual account changes. The same strategy and risk
code runs here as in backtesting — only the data source and executor differ.
"""

import logging
from typing import Dict, List, Optional

from ..config import Config
from ..data.live import LiveDataProvider
from ..execution.alpaca_exec import AlpacaExecutor
from ..models import Bar, Position
from ..portfolio import Portfolio
from ..risk import RiskManager
from ..strategy.base import Strategy

logger = logging.getLogger(__name__)


class LiveEngine:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.executor = AlpacaExecutor(config.alpaca)
        self.risk = RiskManager(config.risk)
        self._portfolio: Optional[Portfolio] = None

    def _sync_portfolio(self) -> Portfolio:
        """Pull current cash and positions from the Alpaca account."""
        from alpaca.trading.client import TradingClient

        client = TradingClient(
            api_key=self.config.alpaca.api_key,
            secret_key=self.config.alpaca.secret_key,
            paper=self.config.alpaca.paper,
        )
        account = client.get_account()
        portfolio = Portfolio(float(account.cash))

        for pos in client.get_all_positions():
            portfolio.positions[pos.symbol] = Position(
                symbol=pos.symbol,
                quantity=int(float(pos.qty)),
                avg_price=float(pos.avg_entry_price),
            )

        mode = "PAPER" if self.config.alpaca.paper else "LIVE"
        logger.info(
            "[%s] Portfolio synced: $%.2f cash, %d position(s): %s",
            mode, portfolio.cash, len(portfolio.positions),
            list(portfolio.positions.keys()),
        )
        return portfolio

    def run(self, strategy: Strategy, symbols: List[str]) -> None:
        mode = "PAPER" if self.config.alpaca.paper else "LIVE"
        logger.info("[%s] Starting engine for %s", mode, symbols)

        self._portfolio = self._sync_portfolio()
        strategy.on_start()

        data_provider = LiveDataProvider(self.config.alpaca)

        def on_bar(bars: Dict[str, Bar]) -> None:
            # Re-sync before acting so we see any fills from prior bars
            self._portfolio = self._sync_portfolio()

            prices = {sym: bar.close for sym, bar in bars.items()}
            signals = strategy.on_bar(bars, self._portfolio)

            if not signals:
                return

            orders = self.risk.validate(signals, self._portfolio, prices)
            if not orders:
                return

            self.executor.execute(orders, prices)

        data_provider.subscribe(symbols, on_bar)

        logger.info("[%s] Engine running. Press Ctrl-C to stop.", mode)
        try:
            data_provider.run()
        except KeyboardInterrupt:
            logger.info("Shutdown requested.")
        finally:
            strategy.on_stop()
            data_provider.stop()
