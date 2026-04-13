#!/usr/bin/env python3
"""Live paper trader — 217_v10_stop30 (All-Weather v10, Margin Overlay).

Streams 1-minute bars from Alpaca, runs the strategy's on_bar() each minute,
and places market orders via Alpaca's paper trading API.

Usage:
    python live_trader.py

Required env vars:
    ALPACA_API_KEY
    ALPACA_SECRET_KEY
    ALPACA_PAPER=true   (default; set to false for live)

Deploy on Railway: set env vars above, start command = python live_trader.py
"""

import logging
import os
import queue
import sys
import threading
import time
from datetime import datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

from alpaca.data.enums import DataFeed
from alpaca.data.live import StockDataStream
from alpaca.data.models import Bar as AlpacaBar
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trading.config import RiskConfig
from trading.models import Bar, Position
from trading.risk import RiskManager
from trading.strategy.allweather_v10 import AllWeatherV10Strategy

ET = ZoneInfo("America/New_York")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("live_trader")

# ── Strategy config — exactly matches 217_v10_stop30 ─────────────────────────
SYMBOLS = [
    "SPY", "QQQ", "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META",
    "AMD", "NFLX", "COIN", "GOOGL", "BA", "JPM", "PLTR", "RIVN", "SHOP", "VGK",
]
LEVERAGE = 5.0
STRATEGY_PARAMS = dict(
    rs_threshold=1.0,
    spy_trend_days=3,
    rs_close_hour=15,
    rs_close_minute=35,
    overnight_top_k=4,
    overnight_bottom_k=4,
    overnight_stop_pct=2.0,
    global_signal_symbol="VGK",
    tier2_top_k=2,
    tier2_bottom_k=2,
)

# Fire on_bar when this fraction of symbols have arrived for the current minute
BAR_COMPLETENESS_THRESHOLD = 0.70


# ── Live Portfolio ─────────────────────────────────────────────────────────────

class LivePortfolio:
    """Portfolio interface backed by Alpaca's actual account state.

    The strategy and risk manager call:
      - portfolio.cash               → available buying power
      - portfolio.positions          → {symbol: Position}
      - portfolio.get_position(sym)  → Optional[Position]
      - portfolio.equity(prices)     → float

    All values are synced from Alpaca on demand (cached for SYNC_INTERVAL seconds).
    """

    SYNC_INTERVAL = 10  # seconds

    def __init__(self, client: TradingClient) -> None:
        self._client = client
        self._positions: Dict[str, Position] = {}
        self._cash: float = 0.0
        self._equity: float = 0.0
        self._last_sync: float = 0.0
        self.filled_orders = []  # unused but keeps interface compatible

    def sync(self) -> None:
        """Hard refresh from Alpaca REST API."""
        try:
            account = self._client.get_account()
            # buying_power = what we can actually spend (includes margin)
            self._cash = float(account.buying_power)
            self._equity = float(account.equity)

            alpaca_positions = self._client.get_all_positions()
            self._positions = {}
            for p in alpaca_positions:
                qty = int(float(p.qty))
                if qty == 0:
                    continue
                self._positions[p.symbol] = Position(
                    symbol=p.symbol,
                    quantity=qty,
                    avg_price=float(p.avg_entry_price),
                )
            self._last_sync = time.monotonic()
            log.debug(
                "Synced — equity=$%.2f  buying_power=$%.2f  open_positions=%d",
                self._equity, self._cash, len(self._positions),
            )
        except Exception as exc:
            log.error("Portfolio sync failed: %s", exc)

    def _maybe_sync(self) -> None:
        if time.monotonic() - self._last_sync > self.SYNC_INTERVAL:
            self.sync()

    @property
    def cash(self) -> float:
        self._maybe_sync()
        return self._cash

    @property
    def positions(self) -> Dict[str, Position]:
        self._maybe_sync()
        return self._positions

    def get_position(self, symbol: str) -> Optional[Position]:
        self._maybe_sync()
        return self._positions.get(symbol)

    def equity(self, prices: Dict[str, float] = None) -> float:  # noqa: ARG002
        self._maybe_sync()
        return self._equity


# ── Live Trader ────────────────────────────────────────────────────────────────

class LiveTrader:
    def __init__(self) -> None:
        api_key = os.environ["ALPACA_API_KEY"]
        secret_key = os.environ["ALPACA_SECRET_KEY"]
        paper = os.getenv("ALPACA_PAPER", "true").lower() != "false"

        self._trading_client = TradingClient(api_key, secret_key, paper=paper)
        self._stream = StockDataStream(api_key, secret_key, feed=DataFeed.IEX)

        self.portfolio = LivePortfolio(self._trading_client)
        self.strategy = AllWeatherV10Strategy(symbols=SYMBOLS, **STRATEGY_PARAMS)
        self.risk = RiskManager(RiskConfig(), leverage=LEVERAGE)

        # Bar accumulation — written by WebSocket thread, read by strategy thread
        self._bar_queue: queue.Queue = queue.Queue()

        self._new_day_done: Optional[str] = None  # date string, reset daily

    @staticmethod
    def _is_market_hours() -> bool:
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return False
        ot = now.replace(hour=9, minute=28, second=0, microsecond=0)
        ct = now.replace(hour=16, minute=5, second=0, microsecond=0)
        return ot <= now <= ct

    @staticmethod
    def _convert_bar(ab: AlpacaBar) -> Bar:
        return Bar(
            symbol=ab.symbol,
            timestamp=ab.timestamp,
            open=float(ab.open),
            high=float(ab.high),
            low=float(ab.low),
            close=float(ab.close),
            volume=float(ab.volume),
        )

    # ── WebSocket callback (called from alpaca's async loop) ──────────────────

    async def _ws_on_bar(self, ab: AlpacaBar) -> None:
        """Fast: just enqueue. Strategy thread does the work."""
        self._bar_queue.put(ab)

    # ── Strategy thread ───────────────────────────────────────────────────────

    def _strategy_loop(self) -> None:
        """Accumulates bars by minute; fires strategy when complete."""
        bar_buffer: Dict[str, Dict[str, Bar]] = {}  # ts_key → {symbol: Bar}
        last_fired: Optional[str] = None

        log.info("Strategy loop started.")

        while True:
            try:
                ab = self._bar_queue.get(timeout=5)
            except queue.Empty:
                continue

            if not self._is_market_hours():
                continue

            bar = self._convert_bar(ab)
            ts_key = bar.timestamp.strftime("%Y-%m-%dT%H:%M")

            bar_buffer.setdefault(ts_key, {})[bar.symbol] = bar
            bucket = bar_buffer[ts_key]

            ready = (
                ts_key != last_fired
                and "SPY" in bucket
                and len(bucket) >= int(len(SYMBOLS) * BAR_COMPLETENESS_THRESHOLD)
            )

            if ready:
                last_fired = ts_key
                self._fire(dict(bucket), ts_key)

                # Drop buckets older than current minute
                stale = [k for k in bar_buffer if k < ts_key]
                for k in stale:
                    del bar_buffer[k]

    def _fire(self, bars: Dict[str, Bar], ts_key: str) -> None:
        """Run strategy + place orders for one completed minute."""
        log.info("── %s  (%d/%d symbols) ──", ts_key, len(bars), len(SYMBOLS))

        # Hard sync before decision
        self.portfolio.sync()

        now_et = datetime.now(ET)
        today_str = now_et.strftime("%Y-%m-%d")

        # New trading day bookkeeping
        if self._new_day_done != today_str:
            self._new_day_done = today_str
            equity = self.portfolio.equity()
            self.risk.new_day(equity)
            log.info("New day %s — equity=$%.2f", today_str, equity)

        prices = {sym: b.close for sym, b in bars.items()}

        # Run strategy
        try:
            signals = self.strategy.on_bar(bars, self.portfolio)
        except Exception as exc:
            log.error("Strategy error: %s", exc, exc_info=True)
            return

        if not signals:
            return

        log.info(
            "Signals: %s",
            [(s.symbol, s.direction.value, s.reason) for s in signals],
        )

        # Size orders via risk manager
        orders = self.risk.validate(signals, self.portfolio, prices)
        if not orders:
            return

        # Place on Alpaca
        for order in orders:
            self._place_order(order)

        # Give fills a moment, then resync
        time.sleep(2)
        self.portfolio.sync()

    def _place_order(self, order) -> None:
        side = OrderSide.BUY if order.side.value == "buy" else OrderSide.SELL
        action = "COVER" if order.is_short_cover else ("SHORT" if order.is_short_entry else side.value.upper())
        try:
            req = MarketOrderRequest(
                symbol=order.symbol,
                qty=order.quantity,
                side=side,
                time_in_force=TimeInForce.DAY,
            )
            result = self._trading_client.submit_order(req)
            log.info(
                "  [fill] %-5s %-6s %-5s ×%-4d  status=%s",
                action, order.symbol, "", order.quantity, result.status,
            )
        except Exception as exc:
            log.error(
                "  [fail] %s %s ×%d — %s",
                action, order.symbol, order.quantity, exc,
            )

    # ── Entry point ───────────────────────────────────────────────────────────

    def start(self) -> None:
        log.info("=" * 60)
        log.info("Live trader — 217_v10_stop30 (All-Weather v10)")
        log.info("Symbols (%d): %s", len(SYMBOLS), ", ".join(SYMBOLS))
        log.info("Leverage: %.1fx   Paper: %s",
                 LEVERAGE, os.getenv("ALPACA_PAPER", "true"))
        log.info("=" * 60)

        # Initial sync & sanity check
        self.portfolio.sync()
        log.info(
            "Account — equity=$%.2f  buying_power=$%.2f  open_positions=%d",
            self.portfolio._equity, self.portfolio._cash, len(self.portfolio._positions),
        )

        # Initialise strategy state
        self.strategy.on_start()

        # Start strategy worker thread
        worker = threading.Thread(target=self._strategy_loop, daemon=True, name="strategy")
        worker.start()

        # Subscribe and start WebSocket (blocking)
        self._stream.subscribe_bars(self._ws_on_bar, *SYMBOLS)
        log.info("WebSocket subscribed — waiting for market bars...")
        self._stream.run()


if __name__ == "__main__":
    LiveTrader().start()
