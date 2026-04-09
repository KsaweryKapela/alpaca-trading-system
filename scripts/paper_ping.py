"""Quick paper trade smoke test: buy 1 share, hold 30 seconds, sell.

Run:
    uv run python scripts/paper_ping.py [--symbol SPY] [--hold 30]

Requires market to be open. Will abort if market is closed.
"""

import argparse
import time
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from trading.config import Config
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus


def wait_for_fill(client: TradingClient, order_id: str, timeout: int = 15) -> object:
    """Poll until the order is filled or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        order = client.get_order_by_id(order_id)
        if order.status.value in ("filled", "partially_filled"):
            return order
        if order.status.value in ("canceled", "expired", "rejected"):
            print(f"  Order {order.status.value} — aborting.")
            sys.exit(1)
        time.sleep(1)
    print(f"  Fill timed out after {timeout}s — aborting.")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Paper trade smoke test")
    parser.add_argument("--symbol", default="SPY", help="Symbol to trade (default: SPY)")
    parser.add_argument("--hold", type=int, default=30, help="Seconds to hold (default: 30)")
    parser.add_argument("--wait", action="store_true", help="Wait for market open if closed")
    args = parser.parse_args()

    config = Config()
    config.alpaca.validate()
    assert config.alpaca.paper, "This script only runs in paper mode (ALPACA_PAPER=true)"

    client = TradingClient(
        api_key=config.alpaca.api_key,
        secret_key=config.alpaca.secret_key,
        paper=True,
    )

    # Check market is open
    clock = client.get_clock()
    if not clock.is_open:
        next_open = clock.next_open.astimezone(timezone.utc)
        if not args.wait:
            print(f"Market is closed. Next open: {next_open.strftime('%Y-%m-%d %H:%M UTC')}")
            print("Re-run with --wait to auto-wait for open.")
            sys.exit(0)
        wait_s = (next_open - datetime.now(timezone.utc)).total_seconds() + 2
        print(f"Market closed. Waiting {wait_s/60:.1f} min until open...", flush=True)
        time.sleep(max(wait_s, 0))

    symbol = args.symbol.upper()
    print(f"\n{'='*42}")
    print(f"  Paper trade smoke test — {symbol}")
    print(f"{'='*42}")

    # ── BUY ───────────────────────────────────────
    print(f"\n[1/4] Submitting BUY 1 {symbol} (market order)...")
    buy_req = MarketOrderRequest(
        symbol=symbol,
        qty=1,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
    )
    buy_order = client.submit_order(buy_req)
    print(f"      Order ID: {buy_order.id}")

    print("[2/4] Waiting for fill...")
    buy_order = wait_for_fill(client, str(buy_order.id))
    buy_price = float(buy_order.filled_avg_price)
    buy_time = datetime.now(timezone.utc)
    print(f"      Filled @ ${buy_price:.4f}  ({buy_time.strftime('%H:%M:%S')} UTC)")

    # ── HOLD ──────────────────────────────────────
    print(f"\n[3/4] Holding for {args.hold} seconds", end="", flush=True)
    for _ in range(args.hold):
        time.sleep(1)
        print(".", end="", flush=True)
    print()

    # ── SELL ──────────────────────────────────────
    print("\n[4/4] Submitting SELL 1 {symbol} (market order)...".format(symbol=symbol))
    sell_req = MarketOrderRequest(
        symbol=symbol,
        qty=1,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )
    sell_order = client.submit_order(sell_req)
    print(f"      Order ID: {sell_order.id}")

    print("      Waiting for fill...")
    sell_order = wait_for_fill(client, str(sell_order.id))
    sell_price = float(sell_order.filled_avg_price)
    sell_time = datetime.now(timezone.utc)
    print(f"      Filled @ ${sell_price:.4f}  ({sell_time.strftime('%H:%M:%S')} UTC)")

    # ── RESULT ────────────────────────────────────
    gross_pnl = sell_price - buy_price
    commission = 2 * 0.005  # $0.005/share each way
    net_pnl = gross_pnl - commission
    hold_s = (sell_time - buy_time).total_seconds()

    print(f"\n{'='*42}")
    print(f"  Result")
    print(f"{'='*42}")
    print(f"  Buy price:   ${buy_price:.4f}")
    print(f"  Sell price:  ${sell_price:.4f}")
    print(f"  Gross P&L:   ${gross_pnl:+.4f}")
    print(f"  Commission:  ${commission:.4f}")
    print(f"  Net P&L:     ${net_pnl:+.4f}")
    print(f"  Hold time:   {hold_s:.1f}s")
    print(f"{'='*42}\n")


if __name__ == "__main__":
    main()
