"""Backtest engine: run a strategy on historical data.

Execution model (lookahead-free):
  Bar T close  → strategy.on_bar() → risk.validate() → orders queued
  Bar T+1 open → SimulatedExecutor fills queued orders → portfolio updated
  Bar T+1 close → equity recorded, next signals generated

Filling at the next bar's open rather than the signal bar's close ensures
the strategy cannot act on information that only exists at bar-end.

After all bars:
  equity curve → metrics (return, Sharpe, max drawdown, trade count)
"""

import logging
from datetime import datetime
from typing import List

import pandas as pd

from ..config import Config
from ..data.historical import iter_bars, load_bars_alpaca, load_bars_yfinance
from ..execution.simulated import SimulatedExecutor
from ..portfolio import Portfolio
from ..risk import RiskManager
from ..strategy.base import Strategy

logger = logging.getLogger(__name__)


class BacktestResult:
    def __init__(self, portfolio: Portfolio, equity_curve: pd.Series) -> None:
        self.portfolio = portfolio
        self.equity_curve = equity_curve

    def metrics(self) -> dict:
        ec = self.equity_curve
        if len(ec) < 2:
            return {}

        returns = ec.pct_change().dropna()
        total_ret = ec.iloc[-1] / ec.iloc[0] - 1
        sharpe = (
            (returns.mean() / returns.std()) * (252 ** 0.5)
            if returns.std() > 0 else 0.0
        )
        drawdown = (ec - ec.cummax()) / ec.cummax()

        return {
            "initial_equity": round(ec.iloc[0], 2),
            "final_equity": round(ec.iloc[-1], 2),
            "total_return_pct": round(total_ret * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown_pct": round(drawdown.min() * 100, 2),
            "num_trades": len(self.portfolio.filled_orders),
        }

    def print_summary(self) -> None:
        m = self.metrics()
        print()
        print("=" * 32)
        print("      Backtest Results")
        print("=" * 32)
        print(f"  Initial equity:  ${m['initial_equity']:>12,.2f}")
        print(f"  Final equity:    ${m['final_equity']:>12,.2f}")
        print(f"  Total return:    {m['total_return_pct']:>+11.2f}%")
        print(f"  Sharpe ratio:    {m['sharpe_ratio']:>12.2f}")
        print(f"  Max drawdown:    {m['max_drawdown_pct']:>+11.2f}%")
        print(f"  Trades:          {m['num_trades']:>12d}")
        print("=" * 32)
        print()


class BacktestEngine:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.executor = SimulatedExecutor(config.backtest)
        self.risk = RiskManager(config.risk)

    def run(
        self,
        strategy: Strategy,
        symbols: List[str],
        start: datetime,
        end: datetime,
        data_source: str = "yfinance",
    ) -> BacktestResult:
        logger.info(
            "Backtest: symbols=%s  %s → %s  source=%s",
            symbols, start.date(), end.date(), data_source,
        )

        if data_source == "alpaca":
            symbol_dfs = load_bars_alpaca(
                symbols, start, end,
                self.config.alpaca.api_key, self.config.alpaca.secret_key,
            )
        else:
            symbol_dfs = load_bars_yfinance(symbols, start, end)

        if not symbol_dfs:
            raise ValueError("No data loaded — check symbols and date range.")

        portfolio = Portfolio(self.config.backtest.initial_cash)
        strategy.on_start()

        equity_timestamps: List[datetime] = []
        equity_values: List[float] = []
        pending_orders: List = []   # orders queued from previous bar, filled at this bar's open

        for bars in iter_bars(symbol_dfs):
            open_prices = {sym: bar.open for sym, bar in bars.items()}
            close_prices = {sym: bar.close for sym, bar in bars.items()}

            # Step 1: Fill orders queued from previous bar at today's open
            if pending_orders:
                filled = self.executor.execute(pending_orders, open_prices)
                for order in filled:
                    portfolio.apply_fill(order)
                pending_orders = []

            # Step 2: Generate signals from today's close; queue for next bar
            signals = strategy.on_bar(bars, portfolio)
            pending_orders = self.risk.validate(signals, portfolio, close_prices)

            # Step 3: Record end-of-day equity (positions valued at close)
            ts = next(iter(bars.values())).timestamp
            equity_timestamps.append(ts)
            equity_values.append(portfolio.equity(close_prices))

        # Discard any signals from the final bar — no next bar to fill at
        if pending_orders:
            logger.debug("Discarding %d unfilled order(s) at end of backtest.", len(pending_orders))

        strategy.on_stop()

        equity_curve = pd.Series(
            equity_values,
            index=pd.DatetimeIndex(equity_timestamps),
            name="equity",
        )
        logger.info("Backtest complete: %d bars, %d trades.", len(equity_curve), len(portfolio.filled_orders))

        return BacktestResult(portfolio, equity_curve)
