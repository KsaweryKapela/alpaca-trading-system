#!/usr/bin/env python3
"""Algorithmic trading system — CLI entry point.

Usage:
  python main.py backtest --symbols AAPL MSFT --start 2022-01-01 --end 2023-12-31
  python main.py backtest --symbols SPY --start 2020-01-01 --end 2023-12-31 --fast 10 --slow 30
  python main.py paper    --symbols AAPL MSFT
  python main.py live     --symbols AAPL MSFT    # real money — prompts for confirmation
"""

import argparse
import logging
import sys
from datetime import datetime

from trading.config import Config
from trading.engine.backtest import BacktestEngine
from trading.engine.live import LiveEngine
from trading.strategy.sma_cross import SMACrossStrategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _add_strategy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--symbols", nargs="+", required=True, metavar="SYM",
                        help="One or more ticker symbols")
    parser.add_argument("--fast", type=int, default=20,
                        help="Fast SMA period (default: 20)")
    parser.add_argument("--slow", type=int, default=50,
                        help="Slow SMA period (default: 50)")


def cmd_backtest(args: argparse.Namespace) -> None:
    config = Config()
    strategy = SMACrossStrategy(
        symbols=args.symbols,
        fast_period=args.fast,
        slow_period=args.slow,
    )
    engine = BacktestEngine(config)
    result = engine.run(
        strategy=strategy,
        symbols=args.symbols,
        start=datetime.fromisoformat(args.start),
        end=datetime.fromisoformat(args.end),
        data_source=args.data_source,
    )
    result.print_summary()


def cmd_paper(args: argparse.Namespace) -> None:
    config = Config()
    config.alpaca.paper = True
    strategy = SMACrossStrategy(
        symbols=args.symbols,
        fast_period=args.fast,
        slow_period=args.slow,
    )
    LiveEngine(config).run(strategy=strategy, symbols=args.symbols)


def cmd_live(args: argparse.Namespace) -> None:
    config = Config()
    config.alpaca.paper = False
    logger.warning("LIVE TRADING MODE — real money at risk!")
    confirm = input("Type 'yes' to continue: ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        sys.exit(0)
    strategy = SMACrossStrategy(
        symbols=args.symbols,
        fast_period=args.fast,
        slow_period=args.slow,
    )
    LiveEngine(config).run(strategy=strategy, symbols=args.symbols)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="trading",
        description="Rule-based algorithmic trading system",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # backtest
    bt = sub.add_parser("backtest", help="Run strategy on historical data")
    _add_strategy_args(bt)
    bt.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    bt.add_argument("--end",   required=True, help="End date YYYY-MM-DD")
    bt.add_argument("--data-source", dest="data_source",
                    choices=["yfinance", "alpaca"], default="yfinance",
                    help="Historical data source (default: yfinance)")
    bt.set_defaults(func=cmd_backtest)

    # paper
    paper = sub.add_parser("paper", help="Run strategy in Alpaca paper trading")
    _add_strategy_args(paper)
    paper.set_defaults(func=cmd_paper)

    # live
    live = sub.add_parser("live", help="Run strategy in Alpaca live trading (real money)")
    _add_strategy_args(live)
    live.set_defaults(func=cmd_live)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
