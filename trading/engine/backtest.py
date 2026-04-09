"""Backtest engine: run a strategy on historical data.

Execution model (lookahead-free):
  Bar T close  → strategy.on_bar() → risk.validate() → orders queued
  Bar T+1 open → SimulatedExecutor fills queued orders → portfolio updated
  Bar T+1 close → equity recorded, next signals generated

Filling at the next bar's open rather than the signal bar's close ensures
the strategy cannot act on information that only exists at bar-end.

After all bars:
  equity curve → metrics (return, Sharpe, max drawdown, trade count)

Sharpe is computed on daily returns (equity curve resampled to calendar days)
so the annualization factor is always √252, regardless of bar frequency.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from ..config import Config
from ..data.historical import iter_bars, load_bars_alpaca, load_bars_yfinance
from ..execution.simulated import SimulatedExecutor
from ..models import Side
from ..portfolio import Portfolio
from ..risk import RiskManager
from ..strategy.base import Strategy

logger = logging.getLogger(__name__)


class BacktestResult:
    def __init__(
        self,
        portfolio: Portfolio,
        equity_curve: pd.Series,
        metadata: Optional[dict] = None,
    ) -> None:
        self.portfolio = portfolio
        self.equity_curve = equity_curve
        self.metadata = metadata or {}

    def metrics(self) -> dict:
        ec = self.equity_curve
        if len(ec) < 2:
            return {}

        # Resample to daily before computing Sharpe so the √252 factor is correct
        # regardless of bar frequency (1m, 5m, 1h, 1d all produce the same result).
        daily_ec = ec.resample("D").last().dropna()
        daily_returns = daily_ec.pct_change().dropna()

        total_ret = ec.iloc[-1] / ec.iloc[0] - 1
        sharpe = (
            (daily_returns.mean() / daily_returns.std()) * (252 ** 0.5)
            if len(daily_returns) > 1 and daily_returns.std() > 0 else 0.0
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

    def extended_metrics(self) -> dict:
        """Compute round-trip trade statistics from the filled order list.

        Pairs each BUY with its next SELL for the same symbol to compute:
          - win_rate: fraction of round trips that were profitable
          - profit_factor: gross wins / gross losses (∞ if no losses)
          - expectancy: average P&L per round trip in dollars
          - max_consecutive_losses: longest losing streak
          - avg_trade_duration_bars: mean bars between entry and exit
        """
        # Group filled orders by symbol
        by_symbol: Dict[str, list] = defaultdict(list)
        for order in self.portfolio.filled_orders:
            if order.is_filled:
                by_symbol[order.symbol].append(order)

        round_trips = []
        for symbol, orders in by_symbol.items():
            buys = [o for o in orders if o.side == Side.BUY]
            sells = [o for o in orders if o.side == Side.SELL]
            # Match in chronological order
            for buy, sell in zip(
                sorted(buys, key=lambda o: o.filled_at),
                sorted(sells, key=lambda o: o.filled_at),
            ):
                qty = min(buy.quantity, sell.quantity)
                pnl = qty * (sell.fill_price - buy.fill_price) - buy.commission - sell.commission
                duration = (sell.filled_at - buy.filled_at).total_seconds()
                round_trips.append({"pnl": pnl, "duration_s": duration})

        if not round_trips:
            return {
                "round_trips": 0,
                "win_rate_pct": None,
                "profit_factor": None,
                "expectancy": None,
                "max_consecutive_losses": None,
                "avg_trade_duration_s": None,
            }

        pnls = [rt["pnl"] for rt in round_trips]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        gross_loss = abs(sum(losses)) if losses else 0

        # Max consecutive losses
        max_cons_loss = 0
        streak = 0
        for p in pnls:
            if p <= 0:
                streak += 1
                max_cons_loss = max(max_cons_loss, streak)
            else:
                streak = 0

        return {
            "round_trips": len(round_trips),
            "win_rate_pct": round(len(wins) / len(round_trips) * 100, 1),
            "profit_factor": round(sum(wins) / gross_loss, 2) if gross_loss > 0 else None,
            "expectancy": round(sum(pnls) / len(pnls), 2),
            "max_consecutive_losses": max_cons_loss,
            "avg_trade_duration_s": round(
                sum(rt["duration_s"] for rt in round_trips) / len(round_trips), 0
            ),
        }

    def round_trips(self) -> List[dict]:
        """Return detailed round-trip records for dashboard/report export."""
        by_symbol: Dict[str, list] = defaultdict(list)
        for order in self.portfolio.filled_orders:
            if order.is_filled:
                by_symbol[order.symbol].append(order)

        round_trips: List[dict] = []
        for symbol, orders in by_symbol.items():
            buys = sorted(
                [o for o in orders if o.side == Side.BUY],
                key=lambda o: o.filled_at or o.created_at,
            )
            sells = sorted(
                [o for o in orders if o.side == Side.SELL],
                key=lambda o: o.filled_at or o.created_at,
            )
            for buy, sell in zip(buys, sells):
                qty = min(buy.quantity, sell.quantity)
                buy_fill = buy.fill_price or 0.0
                sell_fill = sell.fill_price or 0.0
                pnl = qty * (sell_fill - buy_fill) - buy.commission - sell.commission
                entry_ts = buy.filled_at or buy.created_at
                exit_ts = sell.filled_at or sell.created_at
                duration_s = (exit_ts - entry_ts).total_seconds()
                basis = qty * buy_fill
                round_trips.append(
                    {
                        "symbol": symbol,
                        "quantity": qty,
                        "entry_at": entry_ts.isoformat(),
                        "exit_at": exit_ts.isoformat(),
                        "entry_price": round(buy_fill, 4),
                        "exit_price": round(sell_fill, 4),
                        "entry_commission": round(buy.commission, 4),
                        "exit_commission": round(sell.commission, 4),
                        "pnl": round(pnl, 2),
                        "return_pct": round((pnl / basis) * 100, 3) if basis else None,
                        "duration_hours": round(duration_s / 3600, 2),
                        "won": pnl > 0,
                    }
                )

        return sorted(round_trips, key=lambda trade: trade["exit_at"])

    def report_dict(self) -> dict:
        """Serialize the run into a machine-readable report for the dashboard."""
        metrics = self.metrics()
        extended = self.extended_metrics()
        round_trips = self.round_trips()
        equity = self.equity_curve.dropna().sort_index()
        daily_ec = equity.resample("D").last().dropna()
        prev_daily = daily_ec.shift(1)
        monthly_ec = daily_ec.resample("ME").last().dropna()
        prev_monthly = monthly_ec.shift(1)

        daily = []
        for ts, value in daily_ec.items():
            prev_value = prev_daily.loc[ts]
            pnl = None if pd.isna(prev_value) else round(value - prev_value, 2)
            ret = None
            if not pd.isna(prev_value) and prev_value:
                ret = round((value / prev_value - 1) * 100, 3)
            daily.append(
                {
                    "date": ts.date().isoformat(),
                    "equity": round(float(value), 2),
                    "pnl": pnl,
                    "return_pct": ret,
                }
            )

        monthly = []
        for ts, value in monthly_ec.items():
            prev_value = prev_monthly.loc[ts]
            ret = None
            if not pd.isna(prev_value) and prev_value:
                ret = round((value / prev_value - 1) * 100, 3)
            monthly.append(
                {
                    "month": ts.strftime("%Y-%m"),
                    "equity": round(float(value), 2),
                    "return_pct": ret,
                }
            )

        fills = []
        for order in self.portfolio.filled_orders:
            if not order.is_filled:
                continue
            fills.append(
                {
                    "id": order.id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "quantity": order.quantity,
                    "created_at": order.created_at.isoformat(),
                    "filled_at": (order.filled_at or order.created_at).isoformat(),
                    "fill_price": round(order.fill_price or 0.0, 4),
                    "commission": round(order.commission, 4),
                }
            )

        return {
            "metadata": self.metadata,
            "metrics": metrics,
            "extended_metrics": extended,
            "equity_curve": [
                {
                    "timestamp": ts.isoformat(),
                    "equity": round(float(value), 2),
                }
                for ts, value in equity.items()
            ],
            "daily": daily,
            "monthly": monthly,
            "fills": fills,
            "round_trips": round_trips,
        }

    def export_json(self, path: Path) -> Path:
        """Write a structured report JSON for dashboard consumption."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(self.report_dict(), handle, indent=2)
        return path

    def print_summary(self) -> None:
        m = self.metrics()
        x = self.extended_metrics()
        print()
        print("=" * 36)
        print("         Backtest Results")
        print("=" * 36)
        print(f"  Initial equity:  ${m['initial_equity']:>12,.2f}")
        print(f"  Final equity:    ${m['final_equity']:>12,.2f}")
        print(f"  Total return:    {m['total_return_pct']:>+11.2f}%")
        print(f"  Sharpe ratio:    {m['sharpe_ratio']:>12.2f}")
        print(f"  Max drawdown:    {m['max_drawdown_pct']:>+11.2f}%")
        print(f"  Trades (fills):  {m['num_trades']:>12d}")
        if x["round_trips"]:
            print("-" * 36)
            print(f"  Round trips:     {x['round_trips']:>12d}")
            wr = x['win_rate_pct']
            print(f"  Win rate:        {wr:>11.1f}%")
            pf = x['profit_factor']
            print(f"  Profit factor:   {str(round(pf, 2)) if pf is not None else 'N/A':>12}")
            print(f"  Expectancy:      ${x['expectancy']:>11.2f}")
            print(f"  Max consec loss: {x['max_consecutive_losses']:>12d}")
            dur_s = x['avg_trade_duration_s']
            if dur_s is not None:
                dur_h = round(dur_s / 3600, 1)
                print(f"  Avg duration:    {dur_h:>10.1f} hr")
        print("=" * 36)
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
        interval: str = "1d",
    ) -> BacktestResult:
        logger.info(
            "Backtest: symbols=%s  %s → %s  source=%s  interval=%s",
            symbols, start.date(), end.date(), data_source, interval,
        )

        if data_source == "alpaca":
            symbol_dfs = load_bars_alpaca(
                symbols, start, end,
                self.config.alpaca.api_key, self.config.alpaca.secret_key,
                interval=interval,
            )
        else:
            symbol_dfs = load_bars_yfinance(symbols, start, end, interval=interval)

        if not symbol_dfs:
            raise ValueError("No data loaded — check symbols and date range.")

        result = self._run_with_dfs(strategy, symbol_dfs)
        result.metadata.update(
            {
                "strategy": strategy.__class__.__name__,
                "symbols": symbols,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "data_source": data_source,
                "interval": interval,
                "initial_cash": self.config.backtest.initial_cash,
                "commission_per_share": self.config.backtest.commission_per_share,
                "slippage_bps": self.config.backtest.slippage_bps,
                "max_volume_pct": self.config.backtest.max_volume_pct,
                "max_position_pct": self.config.risk.max_position_pct,
                "max_positions": self.config.risk.max_positions,
                "min_cash_pct": self.config.risk.min_cash_pct,
                "max_daily_loss_pct": self.config.risk.max_daily_loss_pct,
            }
        )
        return result

    def _run_with_dfs(
        self,
        strategy: Strategy,
        symbol_dfs: Dict,
        initial_cash: Optional[float] = None,
    ) -> BacktestResult:
        """Core backtest loop. Accepts pre-loaded DataFrames so walk-forward
        can slice the data without re-fetching from the data source."""
        portfolio = Portfolio(initial_cash or self.config.backtest.initial_cash)
        strategy.on_start()

        equity_timestamps: List[datetime] = []
        equity_values: List[float] = []
        pending_orders: List = []
        _last_date = None

        for bars in iter_bars(symbol_dfs):
            open_prices = {sym: bar.open for sym, bar in bars.items()}
            close_prices = {sym: bar.close for sym, bar in bars.items()}
            volumes = {sym: bar.volume for sym, bar in bars.items()}

            ts = next(iter(bars.values())).timestamp
            bar_date = ts.date()

            # Detect new trading day → reset daily loss tracking
            if bar_date != _last_date:
                self.risk.new_day(portfolio.equity(close_prices))
                _last_date = bar_date

            # Step 1: Fill orders queued from previous bar at today's open.
            # Pass bar_time so SimulatedExecutor stamps filled_at with the
            # actual fill-bar timestamp (enables accurate trade duration metrics).
            if pending_orders:
                filled = self.executor.execute(pending_orders, open_prices, volumes, bar_time=ts)
                for order in filled:
                    portfolio.apply_fill(order)
                pending_orders = []

            # Step 2: Generate signals from today's close; queue for next bar.
            # Override Order.created_at with the signal-bar timestamp so
            # round-trip duration = filled_at(exit) - created_at(entry).
            signals = strategy.on_bar(bars, portfolio)
            pending_orders = self.risk.validate(signals, portfolio, close_prices)
            for order in pending_orders:
                order.created_at = ts

            # Step 3: Record end-of-day equity (positions valued at close)
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
        logger.info(
            "Backtest complete: %d bars, %d fills.",
            len(equity_curve), len(portfolio.filled_orders),
        )

        return BacktestResult(portfolio, equity_curve)
