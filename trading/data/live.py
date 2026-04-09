"""Live market data via Alpaca WebSocket streaming.

Bars arrive in real time and are converted to our internal Bar model
before being dispatched to the registered callback.
"""

import logging
from typing import Callable, Dict, List

from ..config import AlpacaConfig
from ..models import Bar

logger = logging.getLogger(__name__)


class LiveDataProvider:
    """Subscribe to real-time minute/daily bars via Alpaca WebSocket.

    Usage:
        provider = LiveDataProvider(config)
        provider.subscribe(["AAPL", "MSFT"], my_callback)
        provider.run()          # blocks; Ctrl-C to stop
    """

    def __init__(self, config: AlpacaConfig) -> None:
        from alpaca.data.live import StockDataStream

        self._config = config
        # "iex" feed is free tier; upgrade to "sip" for full SIP feed
        self._stream = StockDataStream(
            api_key=config.api_key,
            secret_key=config.secret_key,
            feed="iex",
        )

    def subscribe(
        self,
        symbols: List[str],
        callback: Callable[[Dict[str, Bar]], None],
    ) -> None:
        """Register a callback invoked on each incoming bar."""

        async def _handler(alpaca_bar) -> None:
            bar = Bar(
                symbol=alpaca_bar.symbol,
                timestamp=alpaca_bar.timestamp,
                open=float(alpaca_bar.open),
                high=float(alpaca_bar.high),
                low=float(alpaca_bar.low),
                close=float(alpaca_bar.close),
                volume=float(alpaca_bar.volume),
            )
            callback({alpaca_bar.symbol: bar})

        self._stream.subscribe_bars(_handler, *symbols)
        logger.info("Subscribed to live bars for %s", symbols)

    def run(self) -> None:
        """Start the WebSocket event loop. Blocks until stopped."""
        logger.info("Starting live data stream...")
        self._stream.run()

    def stop(self) -> None:
        self._stream.stop()
