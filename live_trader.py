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
    """Portfolio interface backed by Alpaca's actual account state."""

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
            prev_equity = self._equity
            self._cash = float(account.buying_power)
            self._equity = float(account.equity)

            alpaca_positions = self._client.get_all_positions()
            prev_pos_count = len(self._positions)
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

            # Log position changes
            pos_count = len(self._positions)
            equity_delta = self._equity - prev_equity if prev_equity else 0
            delta_str = f"  Δequity={equity_delta:+.2f}" if prev_equity else ""
            log.info(
                "  [sync] equity=$%.2f  buying_power=$%.2f  positions=%d%s",
                self._equity, self._cash, pos_count, delta_str,
            )
            if self._positions:
                for sym, pos in self._positions.items():
                    side = "LONG" if pos.quantity > 0 else "SHORT"
                    log.info(
                        "    %-6s %-5s ×%-4d  avg=$%.2f",
                        sym, side, abs(pos.quantity), pos.avg_price,
                    )
            elif pos_count != prev_pos_count:
                log.info("    (no open positions)")
        except Exception as exc:
            log.error("  [sync] FAILED: %s", exc)

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
        self._bars_received: int = 0       # total bar count for diagnostics
        self._last_bar_log: float = 0.0    # monotonic time of last "heartbeat" log

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

    # ── WebSocket callback (must be a coroutine) ──────────────────────────────

    async def _ws_on_bar(self, ab: AlpacaBar) -> None:
        """Fast: just enqueue. Strategy thread does the work."""
        self._bar_queue.put(ab)
        self._bars_received += 1

        # Heartbeat log every 60 seconds so we know the stream is alive
        now = time.monotonic()
        if now - self._last_bar_log >= 60:
            self._last_bar_log = now
            log.info(
                "[ws] heartbeat — bars received so far: %d  queue depth: %d",
                self._bars_received, self._bar_queue.qsize(),
            )

    # ── Strategy thread ───────────────────────────────────────────────────────

    def _strategy_loop(self) -> None:
        """Accumulates bars by minute; fires strategy when complete."""
        bar_buffer: Dict[str, Dict[str, Bar]] = {}  # ts_key → {symbol: Bar}
        last_fired: Optional[str] = None

        log.info("[strategy] loop started — threshold %.0f%% of %d symbols (%d bars min)",
                 BAR_COMPLETENESS_THRESHOLD * 100, len(SYMBOLS),
                 int(len(SYMBOLS) * BAR_COMPLETENESS_THRESHOLD))

        while True:
            try:
                ab = self._bar_queue.get(timeout=5)
            except queue.Empty:
                if not self._is_market_hours():
                    now = datetime.now(ET)
                    log.debug("[strategy] outside market hours (%s), idle", now.strftime("%H:%M ET"))
                continue

            if not self._is_market_hours():
                continue

            bar = self._convert_bar(ab)
            ts_key = bar.timestamp.strftime("%Y-%m-%dT%H:%M")

            bar_buffer.setdefault(ts_key, {})[bar.symbol] = bar
            bucket = bar_buffer[ts_key]
            n_arrived = len(bucket)

            log.debug("[bar] %s  %s  O=%.2f H=%.2f L=%.2f C=%.2f  (%d/%d in bucket)",
                      ts_key, bar.symbol, bar.open, bar.high, bar.low, bar.close,
                      n_arrived, len(SYMBOLS))

            ready = (
                ts_key != last_fired
                and "SPY" in bucket
                and n_arrived >= int(len(SYMBOLS) * BAR_COMPLETENESS_THRESHOLD)
            )

            if ready:
                log.info("[strategy] firing for %s  (%d/%d symbols arrived)",
                         ts_key, n_arrived, len(SYMBOLS))
                last_fired = ts_key
                self._fire(dict(bucket), ts_key)

                # Drop buckets older than current minute
                stale = [k for k in bar_buffer if k < ts_key]
                for k in stale:
                    del bar_buffer[k]

    @staticmethod
    def _explain_signal(symbol: str, direction: str, reason: str,
                        bars: Dict[str, Bar]) -> str:
        """Translate raw signal reason into a human-readable explanation."""
        bar = bars.get(symbol)
        spy = bars.get("SPY")
        vgk = bars.get("VGK")

        sym_ret = ((bar.close - bar.open) / bar.open * 100) if bar and bar.open else None
        spy_ret = ((spy.close - spy.open) / spy.open * 100) if spy and spy.open else None
        vgk_ret = ((vgk.close - vgk.open) / vgk.open * 100) if vgk and vgk.open else None

        rs = (sym_ret - spy_ret) if sym_ret is not None and spy_ret is not None else None

        if "RS=" in reason:
            rs_val = reason.split("RS=")[1]
            return (
                f"BEAR DAY SHORT — {symbol} is underperforming SPY by {rs_val} "
                f"(stock {sym_ret:+.2f}% vs SPY {spy_ret:+.2f}%). "
                f"Entry: SPY below VWAP + 3-day downtrend. Short open→15:35."
            )
        if "T1 +" in reason:
            rs_val = reason.split("T1 +")[1]
            return (
                f"OVERNIGHT LONG (Tier 1, winner) — {symbol} is today's RS leader vs SPY "
                f"(stock {sym_ret:+.2f}% vs SPY {spy_ret:+.2f}%, RS={rs:+.2f}%). "
                f"Bull session: SPY>VWAP. Buy at close, sell 20min after tomorrow's open."
            )
        if "T1 dip" in reason:
            rs_val = reason.split("T1 dip ")[1]
            return (
                f"OVERNIGHT LONG (Tier 1, dip buy) — {symbol} is today's weakest vs SPY "
                f"(stock {sym_ret:+.2f}% vs SPY {spy_ret:+.2f}%, RS={rs:+.2f}%). "
                f"Contrarian overnight on bull session (SPY>VWAP). Buy at close, sell 20min after open."
            )
        if "T2 +" in reason:
            rs_val = reason.split("T2 +")[1]
            vgk_str = f"VGK {vgk_ret:+.2f}%" if vgk_ret is not None else "VGK bullish"
            return (
                f"OVERNIGHT LONG (Tier 2, winner) — {symbol} RS leader "
                f"(stock {sym_ret:+.2f}% vs SPY {spy_ret:+.2f}%). "
                f"Global signal triggered: {vgk_str} (European markets up). "
                f"Buy at close, sell 20min after tomorrow's open."
            )
        if "T2 dip" in reason:
            vgk_str = f"VGK {vgk_ret:+.2f}%" if vgk_ret is not None else "VGK bullish"
            return (
                f"OVERNIGHT LONG (Tier 2, dip buy) — {symbol} RS laggard "
                f"(stock {sym_ret:+.2f}% vs SPY {spy_ret:+.2f}%). "
                f"Global signal: {vgk_str}. Buy at close, sell 20min after tomorrow's open."
            )
        if "stop" in reason.lower():
            return f"EXIT (stop loss) — {symbol} hit the {2.0}% stop level."
        if "target" in reason.lower():
            return f"EXIT (profit target) — {symbol} hit the profit target."
        if "exit" in reason.lower():
            return f"EXIT (time) — {symbol} 20-min post-open window expired, closing overnight long."
        if "RS close" in reason:
            return f"EXIT (scheduled) — {symbol} RS short closing at 15:35 (margin overlay window)."
        if "RS stop" in reason:
            return f"EXIT (RS stop) — {symbol} short stop triggered."
        if "RS target" in reason:
            return f"EXIT (RS target) — {symbol} short hit profit target."
        return f"{direction.upper()} {symbol} — {reason}"

    def _log_market_context(self, bars: Dict[str, Bar]) -> None:
        """Log SPY and VGK regime context for this minute."""
        spy = bars.get("SPY")
        vgk = bars.get("VGK")

        if spy and spy.open:
            spy_ret = (spy.close - spy.open) / spy.open * 100
            # Rough regime guess: positive day return → likely above VWAP
            regime = "BULL (SPY up today)" if spy_ret > 0 else "BEAR (SPY down today)"
            log.info("[market] SPY  O=$%.2f  C=$%.2f  ret=%+.2f%%  regime=~%s",
                     spy.open, spy.close, spy_ret, regime)

        if vgk and vgk.open:
            vgk_ret = (vgk.close - vgk.open) / vgk.open * 100
            signal_str = "BULLISH — may trigger Tier 2 overnight entries" if vgk_ret > 0 else "BEARISH — no Tier 2 entries"
            log.info("[market] VGK  O=$%.2f  C=$%.2f  ret=%+.2f%%  global_signal=%s",
                     vgk.open, vgk.close, vgk_ret, signal_str)

    def _fire(self, bars: Dict[str, Bar], ts_key: str) -> None:
        """Run strategy + place orders for one completed minute."""
        spy_bar = bars.get("SPY")
        spy_info = (f"SPY O={spy_bar.open:.2f} C={spy_bar.close:.2f}" if spy_bar else "SPY missing")
        log.info("── %s  %s  (%d symbols) ──", ts_key, spy_info, len(bars))

        # Hard sync before decision
        self.portfolio.sync()

        now_et = datetime.now(ET)
        today_str = now_et.strftime("%Y-%m-%d")

        # New trading day bookkeeping
        if self._new_day_done != today_str:
            self._new_day_done = today_str
            equity = self.portfolio.equity()
            self.risk.new_day(equity)
            log.info("[day] new trading day %s — start equity=$%.2f", today_str, equity)

        prices = {sym: b.close for sym, b in bars.items()}

        # Run strategy
        try:
            signals = self.strategy.on_bar(bars, self.portfolio)
        except Exception as exc:
            log.error("[strategy] on_bar error: %s", exc, exc_info=True)
            return

        if not signals:
            log.debug("[strategy] no signals this bar")
            return

        # Market context only when there's something to act on
        self._log_market_context(bars)

        log.info("[strategy] %d signal(s):", len(signals))
        for s in signals:
            explanation = self._explain_signal(s.symbol, s.direction.value, s.reason, bars)
            log.info("    %s", explanation)

        # Size orders via risk manager
        orders = self.risk.validate(signals, self.portfolio, prices)
        if not orders:
            log.warning("[risk] all signals blocked by risk manager (cash/position limits)")
            return

        log.info("[risk] %d order(s) approved:", len(orders))
        for o in orders:
            action = "COVER" if o.is_short_cover else ("SHORT" if o.is_short_entry else o.side.value.upper())
            log.info("    %-5s %-6s ×%d  @ mkt (~$%.2f each, total ~$%.0f)",
                     action, o.symbol, o.quantity,
                     prices.get(o.symbol, 0),
                     o.quantity * prices.get(o.symbol, 0))

        # Place on Alpaca
        for order in orders:
            self._place_order(order, prices)

        # Give fills a moment, then resync
        time.sleep(2)
        log.info("[orders] waiting 2s for fills, then resyncing...")
        self.portfolio.sync()

    def _place_order(self, order, prices: Dict[str, float]) -> None:
        side = OrderSide.BUY if order.side.value == "buy" else OrderSide.SELL
        action = "COVER" if order.is_short_cover else ("SHORT" if order.is_short_entry else side.value.upper())
        est_value = order.quantity * prices.get(order.symbol, 0)
        try:
            req = MarketOrderRequest(
                symbol=order.symbol,
                qty=order.quantity,
                side=side,
                time_in_force=TimeInForce.DAY,
            )
            result = self._trading_client.submit_order(req)
            log.info(
                "  [order] %-5s %-6s ×%-4d  est_value=$%.0f  id=%s  status=%s",
                action, order.symbol, order.quantity, est_value,
                str(result.id)[:8], result.status,
            )
        except Exception as exc:
            log.error(
                "  [order] FAILED %-5s %-6s ×%d — %s",
                action, order.symbol, order.quantity, exc,
            )

    # ── Entry point ───────────────────────────────────────────────────────────

    def start(self) -> None:
        log.info("=" * 60)
        log.info("Live trader — 217_v10_stop30 (All-Weather v10)")
        log.info("Symbols (%d): %s", len(SYMBOLS), ", ".join(SYMBOLS))
        log.info("Leverage: %.1fx   Paper: %s",
                 LEVERAGE, os.getenv("ALPACA_PAPER", "true"))
        log.info("Bar threshold: %.0f%% of symbols must arrive before firing",
                 BAR_COMPLETENESS_THRESHOLD * 100)
        log.info("=" * 60)

        # Initial sync & sanity check
        log.info("[startup] syncing account state...")
        self.portfolio.sync()

        if self.portfolio._positions:
            log.info("[startup] existing open positions carried over:")
            for sym, pos in self.portfolio._positions.items():
                side = "LONG" if pos.quantity > 0 else "SHORT"
                log.info("    %-6s %-5s ×%d  avg=$%.2f", sym, side,
                         abs(pos.quantity), pos.avg_price)
        else:
            log.info("[startup] no existing open positions")

        # Initialise strategy state
        self.strategy.on_start()
        log.info("[startup] strategy initialised")

        # Start strategy worker thread
        worker = threading.Thread(target=self._strategy_loop, daemon=True, name="strategy")
        worker.start()

        # Subscribe and start WebSocket (blocking)
        self._stream.subscribe_bars(self._ws_on_bar, *SYMBOLS)
        log.info("[startup] WebSocket subscribed — waiting for market bars...")
        self._stream.run()


if __name__ == "__main__":
    LiveTrader().start()
