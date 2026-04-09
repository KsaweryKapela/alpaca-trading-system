"""Walk-forward validation for backtested strategies.

Splits a date range into rolling in-sample (training) + out-of-sample (test)
windows and runs a backtest on each window, returning per-window results.

Usage
-----
    from trading.research.walk_forward import walk_forward
    from trading.engine.backtest import BacktestEngine
    from trading.strategy.orb import ORBStrategy
    from trading.config import Config
    import datetime

    results = walk_forward(
        engine=BacktestEngine(Config()),
        strategy_factory=lambda: ORBStrategy(symbols=["SPY"]),
        symbol_dfs=symbol_dfs,           # pre-loaded via load_bars_alpaca / load_bars_yfinance
        train_days=180,
        test_days=60,
    )
    for r in results:
        m = r["test_result"].metrics()
        print(r["train_start"].date(), "→", r["test_end"].date(),
              f"  Sharpe={m['sharpe_ratio']}  Return={m['total_return_pct']}%")

Why walk-forward?
-----------------
A single backtest can be curve-fitted — parameters that look optimal over the
full period often degrade out-of-sample. Walk-forward guards against this by:

  1. Using the training window only to select/confirm parameters.
  2. Measuring performance exclusively on the test window (never seen during
     selection). The test windows chain together to cover the full period.

Interpreting results:
  - If test-window Sharpe is systematically below train-window Sharpe, the
    strategy is overfitting.
  - Consistent test-window Sharpe ≥ 0.5 across at least 4 windows is
    stronger evidence of edge than a single full-period backtest.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Callable, Dict, List

import pandas as pd

from ..engine.backtest import BacktestEngine, BacktestResult
from ..strategy.base import Strategy

logger = logging.getLogger(__name__)


def walk_forward(
    engine: BacktestEngine,
    strategy_factory: Callable[[], Strategy],
    symbol_dfs: Dict[str, pd.DataFrame],
    train_days: int = 180,
    test_days: int = 60,
) -> List[dict]:
    """Run rolling walk-forward validation.

    Parameters
    ----------
    engine:
        A configured BacktestEngine instance.
    strategy_factory:
        Zero-argument callable that returns a fresh Strategy for each window.
        Must return a new instance each call — strategies carry per-day state.
    symbol_dfs:
        Pre-loaded bar DataFrames keyed by symbol (output of load_bars_*).
    train_days:
        Length of each training window in calendar days.
    test_days:
        Length of each test window in calendar days.

    Returns
    -------
    List of dicts, one per fold:
        {
            "fold": int,
            "train_start": datetime, "train_end": datetime,
            "test_start": datetime,  "test_end": datetime,
            "train_result": BacktestResult,
            "test_result":  BacktestResult,
        }
    """
    if not symbol_dfs:
        raise ValueError("symbol_dfs is empty — load data before calling walk_forward.")

    # Determine the global date range from the first symbol's index
    first_df = next(iter(symbol_dfs.values()))
    all_timestamps = pd.DatetimeIndex(first_df.index)
    global_start = all_timestamps.min().to_pydatetime()
    global_end = all_timestamps.max().to_pydatetime()

    window = timedelta(days=train_days)
    step = timedelta(days=test_days)

    results = []
    fold = 0
    train_start = global_start

    while True:
        train_end = train_start + window
        test_start = train_end
        test_end = test_start + step

        if test_end > global_end:
            break

        fold += 1
        logger.info(
            "Walk-forward fold %d: train %s→%s  test %s→%s",
            fold, train_start.date(), train_end.date(),
            test_start.date(), test_end.date(),
        )

        train_dfs = _slice_dfs(symbol_dfs, train_start, train_end)
        test_dfs = _slice_dfs(symbol_dfs, test_start, test_end)

        if not _has_enough_bars(train_dfs, 5) or not _has_enough_bars(test_dfs, 5):
            logger.warning("Fold %d: insufficient bars — skipping.", fold)
            train_start += step
            continue

        train_strategy = strategy_factory()
        train_result = engine._run_with_dfs(train_strategy, train_dfs)

        test_strategy = strategy_factory()
        test_result = engine._run_with_dfs(test_strategy, test_dfs)

        results.append({
            "fold": fold,
            "train_start": train_start,
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
            "train_result": train_result,
            "test_result": test_result,
        })

        train_start += step

    if not results:
        logger.warning(
            "Walk-forward produced no folds. "
            "Increase date range or reduce train_days/test_days."
        )

    return results


def print_walk_forward_summary(results: List[dict]) -> None:
    """Print a compact table of walk-forward fold results."""
    if not results:
        print("No walk-forward results to display.")
        return

    print()
    print("=" * 72)
    print("  Walk-Forward Summary")
    print("=" * 72)
    print(f"  {'Fold':>4}  {'Train window':>22}  {'Test window':>22}  {'Sharpe':>7}  {'Return':>7}")
    print("-" * 72)

    test_sharpes = []
    for r in results:
        m = r["test_result"].metrics()
        sharpe = m.get("sharpe_ratio", 0)
        ret = m.get("total_return_pct", 0)
        test_sharpes.append(sharpe)
        print(
            f"  {r['fold']:>4}  "
            f"{str(r['train_start'].date()):>11} → {str(r['train_end'].date()):<11}  "
            f"{str(r['test_start'].date()):>11} → {str(r['test_end'].date()):<11}  "
            f"{sharpe:>+7.2f}  {ret:>+6.2f}%"
        )

    print("-" * 72)
    avg = sum(test_sharpes) / len(test_sharpes) if test_sharpes else 0
    positive = sum(1 for s in test_sharpes if s > 0)
    print(f"  Avg test Sharpe: {avg:+.2f}   Positive folds: {positive}/{len(test_sharpes)}")
    print("=" * 72)
    print()


def _slice_dfs(
    symbol_dfs: Dict[str, pd.DataFrame],
    start,
    end,
) -> Dict[str, pd.DataFrame]:
    sliced = {}
    for sym, df in symbol_dfs.items():
        mask = (df.index >= pd.Timestamp(start)) & (df.index < pd.Timestamp(end))
        sliced_df = df.loc[mask]
        if not sliced_df.empty:
            sliced[sym] = sliced_df
    return sliced


def _has_enough_bars(symbol_dfs: Dict[str, pd.DataFrame], min_bars: int) -> bool:
    return all(len(df) >= min_bars for df in symbol_dfs.values())
