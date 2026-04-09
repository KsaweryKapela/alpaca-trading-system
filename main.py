#!/usr/bin/env python3
"""Algorithmic trading system — CLI entry point.

Usage examples:
  # SMA crossover — daily bars
  python main.py backtest --symbols AAPL MSFT --start 2022-01-01 --end 2024-01-01

  # Opening Range Breakout — 5-minute bars (last 60 days from yfinance)
  python main.py backtest --strategy orb --symbols SPY QQQ \\
      --start 2026-02-01 --end 2026-04-01 --interval 5m

  # ORB with Alpaca historical data (more history available)
  python main.py backtest --strategy orb --symbols SPY \\
      --start 2025-01-01 --end 2026-01-01 --interval 5m --data-source alpaca

  # Paper trade
  python main.py paper --strategy orb --symbols SPY QQQ
  python main.py live  --strategy sma --symbols AAPL MSFT   # real money — prompts
"""

import argparse
import datetime
import logging
import sys

from trading.config import Config
from trading.engine.backtest import BacktestEngine
from trading.engine.live import LiveEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _build_strategy(args, symbols):
    """Instantiate the requested strategy from CLI args."""
    strategy = getattr(args, "strategy", "sma")

    if strategy == "orb":
        from trading.strategy.orb import ORBStrategy
        h, m = map(int, args.exit_time.split(":"))
        return ORBStrategy(
            symbols=symbols,
            range_minutes=args.range_minutes,
            exit_time=datetime.time(h, m),
        )

    if strategy == "orb-filtered":
        from trading.strategy.orb_filtered import ORBFilteredStrategy
        h, m = map(int, args.exit_time.split(":"))
        return ORBFilteredStrategy(
            symbols=symbols,
            range_minutes=args.range_minutes,
            exit_time=datetime.time(h, m),
            volume_multiplier=args.volume_mult,
            sma_period=args.sma_period,
            regime_symbol=args.regime_symbol or None,
        )

    # default: sma
    from trading.strategy.sma_cross import SMACrossStrategy
    return SMACrossStrategy(
        symbols=symbols,
        fast_period=args.fast,
        slow_period=args.slow,
    )


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--symbols", nargs="+", required=True, metavar="SYM",
                        help="One or more ticker symbols")
    parser.add_argument("--strategy", choices=["sma", "orb", "orb-filtered"], default="sma",
                        help="Strategy to run (default: sma)")
    # SMA args
    parser.add_argument("--fast", type=int, default=20,
                        help="[sma] Fast SMA period (default: 20)")
    parser.add_argument("--slow", type=int, default=50,
                        help="[sma] Slow SMA period (default: 50)")
    # ORB args
    parser.add_argument("--range-minutes", dest="range_minutes", type=int, default=15,
                        help="[orb] Opening range duration in minutes (default: 15)")
    parser.add_argument("--exit-time", dest="exit_time", default="15:55",
                        help="[orb] EOD exit time in NY HH:MM (default: 15:55)")
    # ORB-filtered args
    parser.add_argument("--volume-mult", dest="volume_mult", type=float, default=1.5,
                        help="[orb-filtered] Volume multiplier for entry filter (default: 1.5)")
    parser.add_argument("--sma-period", dest="sma_period", type=int, default=20,
                        help="[orb-filtered] SMA period for regime filter (default: 20)")
    parser.add_argument("--regime-symbol", dest="regime_symbol", default="SPY",
                        help="[orb-filtered] Regime filter symbol (default: SPY, empty=disabled)")


def cmd_backtest(args: argparse.Namespace) -> None:
    config = Config()
    strategy = _build_strategy(args, args.symbols)
    engine = BacktestEngine(config)
    result = engine.run(
        strategy=strategy,
        symbols=args.symbols,
        start=datetime.datetime.fromisoformat(args.start),
        end=datetime.datetime.fromisoformat(args.end),
        data_source=args.data_source,
        interval=args.interval,
    )
    result.print_summary()


def cmd_paper(args: argparse.Namespace) -> None:
    config = Config()
    config.alpaca.paper = True
    strategy = _build_strategy(args, args.symbols)
    LiveEngine(config).run(strategy=strategy, symbols=args.symbols)


def cmd_live(args: argparse.Namespace) -> None:
    config = Config()
    config.alpaca.paper = False
    logger.warning("LIVE TRADING MODE — real money at risk!")
    confirm = input("Type 'yes' to continue: ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        sys.exit(0)
    strategy = _build_strategy(args, args.symbols)
    LiveEngine(config).run(strategy=strategy, symbols=args.symbols)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="trading",
        description="Rule-based algorithmic trading system",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── backtest ──────────────────────────────────────────────────────────────
    bt = sub.add_parser("backtest", help="Run strategy on historical data")
    _add_common_args(bt)
    bt.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    bt.add_argument("--end",   required=True, help="End date YYYY-MM-DD")
    bt.add_argument("--interval", default="1d",
                    help="Bar interval: 1m, 5m, 15m, 1h, 1d (default: 1d)")
    bt.add_argument("--data-source", dest="data_source",
                    choices=["yfinance", "alpaca"], default="yfinance",
                    help="Historical data source (default: yfinance)")
    bt.set_defaults(func=cmd_backtest)

    # ── paper ─────────────────────────────────────────────────────────────────
    paper = sub.add_parser("paper", help="Run strategy in Alpaca paper trading")
    _add_common_args(paper)
    paper.set_defaults(func=cmd_paper)

    # ── live ──────────────────────────────────────────────────────────────────
    live = sub.add_parser("live", help="Run strategy in Alpaca live trading (real money)")
    _add_common_args(live)
    live.set_defaults(func=cmd_live)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
