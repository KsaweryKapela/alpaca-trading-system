"""Live and paper trading engine.

Data flow per dispatched batch:
  Alpaca WebSocket bar(s) → bar buffer → portfolio sync → open-order check
  → strategy.on_bar() → risk.validate() → Alpaca order submit

Key design decisions:
  - Bars are buffered by timestamp. The strategy is only called when all
    bars for a given timestamp have arrived (detected by seeing a newer
    timestamp). This makes multi-symbol behaviour consistent with backtest.
  - Portfolio is re-synced from Alpaca before each decision, capturing
    async fills and any manual account changes.
  - Open orders are fetched during sync. Signals for symbols that already
    have an order in flight are suppressed to prevent duplicate submissions.
  - Latest prices for all symbols are maintained so that equity is not
    mispriced when a bar batch contains only a subset of held symbols.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

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
        self._pending_symbols: Set[str] = set()
        self._bar_buffer: Dict[datetime, Dict[str, Bar]] = {}
        self._latest_prices: Dict[str, float] = {}
        self._trading_client = None   # created after credential validation in run()
        self._last_trading_date: Optional[object] = None

    def _sync_portfolio(self) -> Portfolio:
        """Pull cash, positions, and open orders from Alpaca."""
        from alpaca.trading.requests import GetOrdersRequest

        account = self._trading_client.get_account()
        portfolio = Portfolio(float(account.cash))

        for pos in self._trading_client.get_all_positions():
            portfolio.positions[pos.symbol] = Position(
                symbol=pos.symbol,
                quantity=int(float(pos.qty)),
                avg_price=float(pos.avg_entry_price),
            )

        # Fetch open orders so we can suppress duplicate signal submissions
        try:
            open_orders = self._trading_client.get_orders(
                filter=GetOrdersRequest(status="open")
            )
            self._pending_symbols = {o.symbol for o in open_orders}
        except Exception as exc:
            logger.warning("Could not fetch open orders: %s — skipping duplicate check", exc)
            self._pending_symbols = set()

        mode = "PAPER" if self.config.alpaca.paper else "LIVE"
        logger.info(
            "[%s] Synced: $%.2f cash | %d position(s) | %d open order(s)",
            mode, portfolio.cash, len(portfolio.positions), len(self._pending_symbols),
        )
        return portfolio

    def _process_bars(self, bars: Dict[str, Bar], strategy: Strategy) -> None:
        """Run one complete strategy cycle for a batched set of bars."""
        self._portfolio = self._sync_portfolio()

        # Merge current bar prices with latest known prices for all held symbols.
        # Without this, portfolio.equity() falls back to avg_price for symbols
        # not present in the current bar batch, mispricing the portfolio.
        prices = {**self._latest_prices, **{sym: bar.close for sym, bar in bars.items()}}

        # Detect new trading day → reset daily loss limit tracking
        ts = next(iter(bars.values())).timestamp
        bar_date = ts.date()
        if bar_date != self._last_trading_date:
            self.risk.new_day(self._portfolio.equity(prices))
            self._last_trading_date = bar_date

        signals = strategy.on_bar(bars, self._portfolio)

        # Suppress signals for symbols with orders already in flight
        if self._pending_symbols:
            suppressed = [s for s in signals if s.symbol in self._pending_symbols]
            signals = [s for s in signals if s.symbol not in self._pending_symbols]
            if suppressed:
                logger.info(
                    "Suppressed %d signal(s) — open orders already exist for: %s",
                    len(suppressed), [s.symbol for s in suppressed],
                )

        if not signals:
            return

        orders = self.risk.validate(signals, self._portfolio, prices)
        if not orders:
            return

        self.executor.execute(orders, prices)

    def run(self, strategy: Strategy, symbols: List[str]) -> None:
        # Validate credentials before touching anything else
        self.config.alpaca.validate()

        from alpaca.trading.client import TradingClient

        self._trading_client = TradingClient(
            api_key=self.config.alpaca.api_key,
            secret_key=self.config.alpaca.secret_key,
            paper=self.config.alpaca.paper,
        )

        mode = "PAPER" if self.config.alpaca.paper else "LIVE"
        logger.info("[%s] Starting engine for %s", mode, symbols)

        self._bar_buffer = {}
        self._latest_prices = {}
        self._portfolio = self._sync_portfolio()
        strategy.on_start()

        data_provider = LiveDataProvider(self.config.alpaca)

        def on_bar(incoming: Dict[str, Bar]) -> None:
            # Update latest known prices and buffer bars by timestamp
            for sym, bar in incoming.items():
                self._latest_prices[sym] = bar.close
                if bar.timestamp not in self._bar_buffer:
                    self._bar_buffer[bar.timestamp] = {}
                self._bar_buffer[bar.timestamp][sym] = bar

            # Dispatch timestamps that are strictly older than the latest seen.
            # When we observe timestamp T+1, we know all symbols for T have arrived.
            latest_ts = max(self._bar_buffer)
            ready = sorted(ts for ts in self._bar_buffer if ts < latest_ts)

            for ts in ready:
                batched = self._bar_buffer.pop(ts)
                self._process_bars(batched, strategy)

        data_provider.subscribe(symbols, on_bar)

        logger.info("[%s] Engine running. Press Ctrl-C to stop.", mode)
        try:
            data_provider.run()
        except KeyboardInterrupt:
            logger.info("Shutdown requested.")
        finally:
            strategy.on_stop()
            data_provider.stop()
