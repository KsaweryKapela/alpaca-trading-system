"""Backtest engine — intraday-first design.

Execution model (lookahead-free):
  Bar T close  → strategy.on_bar() → EOD-flatten override → risk.validate() → orders queued
  Bar T+1 open → SimulatedExecutor fills queued orders → portfolio updated
  Bar T+1 close → equity recorded

EOD flatten:
  At or after EOD_FLATTEN_ET (default 15:55 ET), all open positions receive
  FLAT signals.  With 1m bars this fills at the 15:56 open — same day. ✓

Sharpe: resampled to daily equity → √252 annualisation (correct for any bar freq).
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from ..config import Config
from ..data.historical import iter_bars, load_bars_alpaca, load_bars_yfinance
from ..execution.simulated import SimulatedExecutor
from ..models import Direction, Side, Signal
from ..portfolio import Portfolio
from ..risk import RiskManager
from ..strategy.base import Strategy

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
EOD_HOUR = 15
EOD_MINUTE = 55   # flatten at 15:55 ET; fills at 15:56 (same day for 1m bars)


def _is_eod(ts: datetime) -> bool:
    et = ts.astimezone(ET)
    return et.hour > EOD_HOUR or (et.hour == EOD_HOUR and et.minute >= EOD_MINUTE)


def _is_market_open_bar(ts: datetime) -> bool:
    """True during regular session (9:30 – 16:00 ET)."""
    et = ts.astimezone(ET)
    after_open = et.hour > 9 or (et.hour == 9 and et.minute >= 30)
    before_close = et.hour < 16
    return after_open and before_close


class BacktestResult:
    def __init__(
        self,
        portfolio: Portfolio,
        equity_curve: pd.Series,
        strategy_rules: List[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        self.portfolio = portfolio
        self.equity_curve = equity_curve
        self.strategy_rules = strategy_rules or []
        self.metadata = metadata or {}

    # ── Metrics ──────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        ec = self.equity_curve
        if len(ec) < 2:
            return {}
        daily_ec = ec.resample("D").last().dropna()
        daily_returns = daily_ec.pct_change().dropna()
        total_ret = ec.iloc[-1] / ec.iloc[0] - 1
        sharpe = (
            (daily_returns.mean() / daily_returns.std()) * (252 ** 0.5)
            if len(daily_returns) > 1 and daily_returns.std() > 0 else 0.0
        )
        drawdown = (ec - ec.cummax()) / ec.cummax()

        # Actual calendar-month returns (chain month-end equity values)
        monthly_breakdown, avg_monthly_ret = self._monthly_returns(daily_ec, ec.iloc[0])

        return {
            "initial_equity": round(ec.iloc[0], 2),
            "final_equity": round(ec.iloc[-1], 2),
            "total_return_pct": round(total_ret * 100, 2),
            "monthly_return_pct": round(avg_monthly_ret * 100, 2),
            "monthly_breakdown": monthly_breakdown,
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown_pct": round(drawdown.min() * 100, 2),
            "fills": len(self.portfolio.filled_orders),
        }

    @staticmethod
    def _monthly_returns(daily_ec: pd.Series, initial_equity: float):
        """Compute per-calendar-month returns and their average.

        Each month's return is measured from the previous month's last equity
        (or from initial_equity for the first month in the window).
        """
        if len(daily_ec) < 1:
            return {}, 0.0

        # Last equity value per calendar month
        monthly_last: Dict[str, float] = {}
        for ts, eq in daily_ec.items():
            key = f"{ts.year}-{ts.month:02d}"
            monthly_last[key] = eq  # later values overwrite → last-of-month

        sorted_keys = sorted(monthly_last.keys())
        if not sorted_keys:
            return {}, 0.0

        rets: Dict[str, float] = {}
        prev_eq = initial_equity
        for key in sorted_keys:
            curr_eq = monthly_last[key]
            rets[key] = round((curr_eq / prev_eq - 1) * 100, 2)
            prev_eq = curr_eq

        avg = round(sum(rets.values()) / len(rets), 2) if rets else 0.0
        return rets, avg / 100  # return avg as a fraction for consistency

    def extended_metrics(self) -> dict:
        by_symbol: Dict[str, list] = defaultdict(list)
        for order in self.portfolio.filled_orders:
            if order.is_filled:
                by_symbol[order.symbol].append(order)

        round_trips = []
        for orders in by_symbol.values():
            round_trips.extend(self._fifo_match(orders))

        if not round_trips:
            return {"round_trips": 0, "win_rate_pct": None, "profit_factor": None,
                    "expectancy": None, "max_consecutive_losses": None}

        pnls = [rt["pnl"] for rt in round_trips]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        gross_loss = abs(sum(losses)) if losses else 0
        max_cons = streak = 0
        for p in pnls:
            streak = streak + 1 if p <= 0 else 0
            max_cons = max(max_cons, streak)
        return {
            "round_trips": len(round_trips),
            "win_rate_pct": round(len(wins) / len(round_trips) * 100, 1),
            "profit_factor": round(sum(wins) / gross_loss, 2) if gross_loss > 0 else None,
            "expectancy": round(sum(pnls) / len(pnls), 2),
            "max_consecutive_losses": max_cons,
        }

    @staticmethod
    def _fifo_match(orders: list) -> list:
        """FIFO round-trip matching for one symbol's filled orders.

        Handles partial fills and multiple entries/exits via a queue.
        Each entry in the queue: [fill_price, remaining_qty, commission_per_share].
        Commission is stored per-share so partial matches allocate correctly.
        """
        long_q: list = []   # [(price, qty, comm_per_share), ...]
        short_q: list = []
        round_trips: list = []

        for order in sorted(orders, key=lambda o: o.filled_at or o.created_at):
            p = order.fill_price
            q = order.quantity
            comm_ps = order.commission / q if q > 0 else 0.0  # commission per share

            if order.side == Side.BUY and not order.is_short_cover:
                long_q.append([p, q, comm_ps])

            elif order.side == Side.SELL and order.is_short_entry:
                short_q.append([p, q, comm_ps])

            elif order.side == Side.SELL and not order.is_short_entry:
                # Close long — match against earliest entries (FIFO)
                remaining = q
                exit_comm_ps = comm_ps
                while remaining > 0 and long_q:
                    e_price, e_qty, e_comm_ps = long_q[0]
                    matched = min(remaining, e_qty)
                    pnl = (matched * (p - e_price)
                           - matched * e_comm_ps
                           - matched * exit_comm_ps)
                    round_trips.append({"pnl": round(pnl, 4)})
                    remaining -= matched
                    long_q[0][1] -= matched
                    if long_q[0][1] == 0:
                        long_q.pop(0)

            elif order.side == Side.BUY and order.is_short_cover:
                # Cover short — match against earliest short entries (FIFO)
                remaining = q
                cover_comm_ps = comm_ps
                while remaining > 0 and short_q:
                    e_price, e_qty, e_comm_ps = short_q[0]
                    matched = min(remaining, e_qty)
                    pnl = (matched * (e_price - p)
                           - matched * e_comm_ps
                           - matched * cover_comm_ps)
                    round_trips.append({"pnl": round(pnl, 4)})
                    remaining -= matched
                    short_q[0][1] -= matched
                    if short_q[0][1] == 0:
                        short_q.pop(0)

        return round_trips

    # ── Transactions ──────────────────────────────────────────────────────────

    def transactions(self) -> List[dict]:
        """Build per-fill transaction log with correct realized PnL.

        Realized PnL at exit includes both the entry commission (allocated
        proportionally if partially closing) and the exit commission, so the
        sum of all exit PnLs reconciles with final_equity - initial_equity.
        """
        avg_prices: Dict[str, float] = {}
        quantities: Dict[str, float] = {}
        # Track total entry commission paid for the current open position.
        # Stored as commission-per-share so partial closes allocate correctly.
        entry_comm_ps: Dict[str, float] = {}   # commission per share at entry
        result = []

        for order in sorted(self.portfolio.filled_orders, key=lambda o: o.filled_at or o.created_at):
            if not order.is_filled:
                continue
            sym = order.symbol
            price = order.fill_price
            qty = order.quantity
            ts = order.filled_at or order.created_at
            date_str = ts.astimezone(ET).strftime("%Y-%m-%d")
            exit_comm_ps = order.commission / qty if qty > 0 else 0.0

            pnl = None
            if order.side == Side.BUY and not order.is_short_cover:
                # Long entry: update weighted-avg price and entry commission
                prev_qty = quantities.get(sym, 0.0)
                prev_avg = avg_prices.get(sym, price)
                prev_cps = entry_comm_ps.get(sym, 0.0)
                new_qty = prev_qty + qty
                avg_prices[sym] = (prev_qty * prev_avg + qty * price) / new_qty if new_qty else price
                # Blend entry commission per share
                entry_comm_ps[sym] = (prev_qty * prev_cps + qty * exit_comm_ps) / new_qty if new_qty else exit_comm_ps
                quantities[sym] = new_qty
                label = "BUY (open long)"

            elif order.side == Side.SELL and not order.is_short_entry:
                # Long exit: PnL = price gain − entry commission − exit commission
                entry_avg = avg_prices.get(sym, price)
                e_cps = entry_comm_ps.get(sym, 0.0)
                pnl = round(qty * (price - entry_avg) - qty * e_cps - qty * exit_comm_ps, 2)
                new_qty = quantities.get(sym, qty) - qty
                quantities[sym] = new_qty
                if new_qty <= 0:
                    avg_prices.pop(sym, None)
                    quantities.pop(sym, None)
                    entry_comm_ps.pop(sym, None)
                label = "SELL (close long)"

            elif order.side == Side.SELL and order.is_short_entry:
                # Short entry: update weighted-avg short price and entry commission
                prev_qty = abs(quantities.get(sym, 0.0))
                prev_avg = avg_prices.get(sym, price)
                prev_cps = entry_comm_ps.get(sym, 0.0)
                new_short = prev_qty + qty
                avg_prices[sym] = (prev_qty * prev_avg + qty * price) / new_short if new_short else price
                entry_comm_ps[sym] = (prev_qty * prev_cps + qty * exit_comm_ps) / new_short if new_short else exit_comm_ps
                quantities[sym] = -(prev_qty + qty)
                label = "SELL (open short)"

            elif order.side == Side.BUY and order.is_short_cover:
                # Short cover: PnL = price fall − entry commission − cover commission
                entry_avg = avg_prices.get(sym, price)
                e_cps = entry_comm_ps.get(sym, 0.0)
                pnl = round(qty * (entry_avg - price) - qty * e_cps - qty * exit_comm_ps, 2)
                new_qty = quantities.get(sym, -qty) + qty
                quantities[sym] = new_qty
                if new_qty >= 0:
                    avg_prices.pop(sym, None)
                    quantities.pop(sym, None)
                    entry_comm_ps.pop(sym, None)
                label = "BUY (cover short)"

            else:
                label = order.side.value.upper()

            result.append({
                "date": date_str,
                "asset": sym,
                "side": label,
                "size": qty,
                "price": round(price, 4),
                "pnl": pnl,
                "commission": round(order.commission, 4),
            })
        return result

    # ── Calendar — per-day detail for hover ──────────────────────────────────

    def calendar(self) -> List[dict]:
        txns = self.transactions()
        by_date: Dict[str, dict] = {}
        for t in txns:
            d = t["date"]
            if d not in by_date:
                by_date[d] = {"date": d, "trade_count": 0, "pnl": 0.0, "assets": set(), "trades": []}
            by_date[d]["trade_count"] += 1
            by_date[d]["assets"].add(t["asset"])
            by_date[d]["trades"].append(t)
            if t["pnl"] is not None:
                by_date[d]["pnl"] += t["pnl"]

        for day in by_date.values():
            day["assets"] = sorted(day["assets"])
            day["pnl"] = round(day["pnl"], 2)

        daily_ec = self.equity_curve.resample("D").last().dropna()
        result = []
        for ts in daily_ec.index:
            d = ts.strftime("%Y-%m-%d")
            day = by_date.get(d, {"date": d, "trade_count": 0, "pnl": 0.0, "assets": [], "trades": []})
            day["has_trades"] = day["trade_count"] > 0
            result.append(day)
        return sorted(result, key=lambda x: x["date"])

    # ── Full serialised dict ──────────────────────────────────────────────────

    def to_dict(self, slug: str = "", status: str = "in_progress") -> dict:
        return {
            "slug": slug,
            "status": status,
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "rules": self.strategy_rules,
            "metadata": self.metadata,
            "metrics": self.metrics(),
            "extended_metrics": self.extended_metrics(),
            "transactions": self.transactions(),
            "calendar": self.calendar(),
        }


# ── Engine ────────────────────────────────────────────────────────────────────

class BacktestEngine:
    def __init__(self, config: Config, leverage: float = 1.0, eod_flatten: bool = True) -> None:
        self.config = config
        self.leverage = leverage
        self.eod_flatten = eod_flatten
        self.executor = SimulatedExecutor(config.backtest)
        self.risk = RiskManager(config.risk, leverage=leverage)

    def run(
        self,
        strategy: Strategy,
        symbols: List[str],
        start: datetime,
        end: datetime,
        data_source: str = "alpaca",
        interval: str = "1m",
        params: Optional[dict] = None,
    ) -> BacktestResult:
        logger.info("Backtest: %s  %s→%s  %s/%s  leverage=%.1fx  eod_flatten=%s",
                    symbols, start.date(), end.date(), data_source, interval,
                    self.leverage, self.eod_flatten)

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

        result = self._run_loop(strategy, symbol_dfs)
        result.metadata.update({
            "strategy": strategy.__class__.__name__,
            "strategy_label": getattr(strategy, "label", strategy.__class__.__name__),
            "symbols": symbols,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "data_source": data_source,
            "interval": interval,
            "leverage": self.leverage,
            "initial_cash": self.config.backtest.initial_cash,
            "params": params or {},
        })
        return result

    def _run_loop(self, strategy: Strategy, symbol_dfs: Dict) -> BacktestResult:
        portfolio = Portfolio(self.config.backtest.initial_cash)
        strategy.on_start()

        equity_timestamps = []
        equity_values = []
        pending_orders = []
        _last_date = None

        for bars in iter_bars(symbol_dfs):
            ts = next(iter(bars.values())).timestamp
            # Skip bars outside regular session (pre/post market)
            if not _is_market_open_bar(ts):
                continue

            open_prices  = {sym: bar.open  for sym, bar in bars.items()}
            close_prices = {sym: bar.close for sym, bar in bars.items()}
            volumes      = {sym: bar.volume for sym, bar in bars.items()}
            bar_date = ts.astimezone(ET).date()

            if bar_date != _last_date:
                self.risk.new_day(portfolio.equity(close_prices))
                _last_date = bar_date

            # Fill orders queued from previous bar
            if pending_orders:
                filled = self.executor.execute(pending_orders, open_prices, volumes, bar_time=ts)
                for order in filled:
                    if order.is_filled:
                        portfolio.apply_fill(order)
                pending_orders = []

            # Strategy signals
            signals = strategy.on_bar(bars, portfolio)

            # EOD flatten: override/append FLAT for all open positions
            if self.eod_flatten and _is_eod(ts):
                already_closing = {s.symbol for s in signals if s.direction == Direction.FLAT}
                eod_flats = [
                    Signal(sym, Direction.FLAT, reason="EOD flatten")
                    for sym in portfolio.positions
                    if sym not in already_closing
                ]
                # Only allow FLAT signals at EOD — discard any new entries
                signals = [s for s in signals if s.direction == Direction.FLAT] + eod_flats

            pending_orders = self.risk.validate(signals, portfolio, close_prices)
            for order in pending_orders:
                order.created_at = ts

            equity_timestamps.append(ts)
            equity_values.append(portfolio.equity(close_prices))

        strategy.on_stop()

        equity_curve = pd.Series(
            equity_values,
            index=pd.DatetimeIndex(equity_timestamps),
            name="equity",
        )
        logger.info("Done: %d bars, %d fills.", len(equity_curve), len(portfolio.filled_orders))
        return BacktestResult(portfolio=portfolio, equity_curve=equity_curve,
                              strategy_rules=strategy.rules())
