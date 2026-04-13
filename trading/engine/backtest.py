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

        # ── New diagnostic metrics ──────────────────────────────────────
        avg_win = round(sum(wins) / len(wins), 2) if wins else 0.0
        avg_loss = round(sum(losses) / len(losses), 2) if losses else 0.0
        payoff_ratio = round(avg_win / abs(avg_loss), 2) if avg_loss != 0 else None

        # Sortino ratio (daily, √252 annualised — penalises downside vol only)
        ec = self.equity_curve
        sortino = 0.0
        if len(ec) > 1:
            daily_ec = ec.resample("D").last().dropna()
            daily_rets = daily_ec.pct_change().dropna()
            if len(daily_rets) > 1:
                downside = daily_rets[daily_rets < 0]
                downside_std = downside.std() if len(downside) > 1 else 0.0
                if downside_std > 0:
                    sortino = round((daily_rets.mean() / downside_std) * (252 ** 0.5), 2)

        # Calmar ratio = annualised return / max drawdown
        calmar = 0.0
        if len(ec) > 1:
            total_ret = ec.iloc[-1] / ec.iloc[0] - 1
            trading_days = len(ec.resample("D").last().dropna())
            ann_ret = total_ret * (252 / max(trading_days, 1))
            dd = (ec - ec.cummax()) / ec.cummax()
            max_dd = abs(dd.min())
            if max_dd > 0:
                calmar = round(ann_ret / max_dd, 2)

        # Worst day / worst week
        worst_day = 0.0
        worst_week = 0.0
        if len(ec) > 1:
            daily_ec = ec.resample("D").last().dropna()
            daily_pct = daily_ec.pct_change().dropna()
            worst_day = round(daily_pct.min() * 100, 2) if len(daily_pct) > 0 else 0.0
            weekly_ec = ec.resample("W").last().dropna()
            weekly_pct = weekly_ec.pct_change().dropna()
            worst_week = round(weekly_pct.min() * 100, 2) if len(weekly_pct) > 0 else 0.0

        # Commission drag
        total_comm = sum(o.commission for o in self.portfolio.filled_orders if o.is_filled)
        initial_eq = ec.iloc[0] if len(ec) > 0 else 100000.0
        comm_drag_pct = round(total_comm / initial_eq * 100, 2)

        return {
            "round_trips": len(round_trips),
            "win_rate_pct": round(len(wins) / len(round_trips) * 100, 1),
            "profit_factor": round(sum(wins) / gross_loss, 2) if gross_loss > 0 else None,
            "expectancy": round(sum(pnls) / len(pnls), 2),
            "max_consecutive_losses": max_cons,
            # New diagnostics
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "payoff_ratio": payoff_ratio,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "worst_day_pct": worst_day,
            "worst_week_pct": worst_week,
            "commission_drag_pct": comm_drag_pct,
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
        entry_comm_ps: Dict[str, float] = {}   # commission per share at entry
        entry_leverage: Dict[str, float] = {}  # leverage used at entry
        result = []

        for order in sorted(self.portfolio.filled_orders, key=lambda o: o.filled_at or o.created_at):
            if not order.is_filled:
                continue
            sym = order.symbol
            price = order.fill_price
            qty = order.quantity
            ts = order.filled_at or order.created_at
            ts_et = ts.astimezone(ET)
            date_str = ts_et.strftime("%Y-%m-%d")
            time_str = ts_et.strftime("%H:%M")
            exit_comm_ps = order.commission / qty if qty > 0 else 0.0

            pnl = None
            if order.side == Side.BUY and not order.is_short_cover:
                # Long entry: update weighted-avg price and entry commission
                prev_qty = quantities.get(sym, 0.0)
                prev_avg = avg_prices.get(sym, price)
                prev_cps = entry_comm_ps.get(sym, 0.0)
                new_qty = prev_qty + qty
                avg_prices[sym] = (prev_qty * prev_avg + qty * price) / new_qty if new_qty else price
                entry_comm_ps[sym] = (prev_qty * prev_cps + qty * exit_comm_ps) / new_qty if new_qty else exit_comm_ps
                entry_leverage[sym] = order.leverage
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
                    entry_leverage.pop(sym, None)
                label = "SELL (close long)"

            elif order.side == Side.SELL and order.is_short_entry:
                # Short entry: update weighted-avg short price and entry commission
                prev_qty = abs(quantities.get(sym, 0.0))
                prev_avg = avg_prices.get(sym, price)
                prev_cps = entry_comm_ps.get(sym, 0.0)
                new_short = prev_qty + qty
                avg_prices[sym] = (prev_qty * prev_avg + qty * price) / new_short if new_short else price
                entry_comm_ps[sym] = (prev_qty * prev_cps + qty * exit_comm_ps) / new_short if new_short else exit_comm_ps
                entry_leverage[sym] = order.leverage
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
                    entry_leverage.pop(sym, None)
                label = "BUY (cover short)"

            else:
                label = order.side.value.upper()

            result.append({
                "date": date_str,
                "time": time_str,
                "asset": sym,
                "side": label,
                "size": qty,
                "price": round(price, 4),
                "pnl": pnl,
                "commission": round(order.commission, 4),
                "leverage": entry_leverage.get(sym, order.leverage),
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

    # ── Per-symbol breakdown ──────────────────────────────────────────────────

    def per_symbol_metrics(self) -> dict:
        """Per-symbol breakdown: PnL, round-trip stats, Sharpe, max DD, and monthly returns.

        Sharpe, DD and monthly are derived from each symbol's daily realized PnL series,
        normalized by portfolio initial equity (i.e. contribution to portfolio return).
        This is mathematically correct: values sum to portfolio-level contributions.
        """
        by_symbol: Dict[str, list] = defaultdict(list)
        for order in self.portfolio.filled_orders:
            if order.is_filled:
                by_symbol[order.symbol].append(order)

        # Single pass over transactions: aggregate fills, PnL, wins/losses, daily PnL series
        txns = self.transactions()
        txn_fills:      Dict[str, int]   = defaultdict(int)
        txn_pnl:        Dict[str, float] = defaultdict(float)
        txn_win_count:  Dict[str, int]   = defaultdict(int)
        txn_gross_win:  Dict[str, float] = defaultdict(float)
        txn_gross_loss: Dict[str, float] = defaultdict(float)
        daily_pnl_by_sym: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for t in txns:
            sym = t["asset"]
            txn_fills[sym] += 1
            p = t.get("pnl")
            if p is not None:
                txn_pnl[sym] += p
                daily_pnl_by_sym[sym][t["date"]] += p
                if p > 0:
                    txn_win_count[sym] += 1
                    txn_gross_win[sym] += p
                else:
                    txn_gross_loss[sym] += abs(p)

        initial_equity = float(self.equity_curve.iloc[0]) if len(self.equity_curve) > 0 else 100000.0
        daily_ec = self.equity_curve.resample("D").last().dropna()
        all_dates = [ts.strftime("%Y-%m-%d") for ts in daily_ec.index]

        result: Dict[str, dict] = {}
        for sym in by_symbol:
            rts = self._fifo_match(by_symbol[sym])
            total_pnl = round(txn_pnl[sym], 2)
            gw  = txn_gross_win[sym]
            gl  = txn_gross_loss[sym]
            wc  = txn_win_count[sym]
            rt  = len(rts)

            # Daily realized PnL series aligned to all portfolio trading days
            sym_daily = pd.Series(
                [daily_pnl_by_sym[sym].get(d, 0.0) for d in all_dates],
                dtype=float,
            )
            daily_ret = sym_daily / initial_equity  # contribution to portfolio return

            # Sharpe — same √252 annualisation as portfolio-level metric
            sharpe = (
                (daily_ret.mean() / daily_ret.std()) * (252 ** 0.5)
                if len(daily_ret) > 1 and daily_ret.std() > 0 else 0.0
            )

            # Max drawdown on cumulative realized PnL / initial_equity
            cum_ret = sym_daily.cumsum() / initial_equity
            max_dd  = round((cum_ret - cum_ret.cummax()).min() * 100, 2)

            # Monthly returns: sum realized PnL per calendar month / initial_equity
            monthly_pnl: Dict[str, float] = defaultdict(float)
            for d in all_dates:
                monthly_pnl[d[:7]] += daily_pnl_by_sym[sym].get(d, 0.0)
            monthly_rets = {
                k: round(v / initial_equity * 100, 2)
                for k, v in sorted(monthly_pnl.items())
            }
            avg_monthly = round(sum(monthly_rets.values()) / len(monthly_rets), 2) if monthly_rets else 0.0

            result[sym] = {
                "total_pnl":         total_pnl,
                "return_pct":        round(total_pnl / initial_equity * 100, 2),
                "fills":             txn_fills[sym],
                "round_trips":       rt,
                "win_count":         wc,
                "gross_win":         round(gw, 2),
                "gross_loss":        round(gl, 2),
                "win_rate_pct":      round(wc / rt * 100, 1) if rt else None,
                "profit_factor":     round(gw / gl, 2) if gl > 0 else None,
                "expectancy":        round(total_pnl / rt, 2) if rt else None,
                "sharpe_ratio":      round(sharpe, 2),
                "max_drawdown_pct":  max_dd,
                "monthly_return_pct": avg_monthly,
                "monthly_breakdown": monthly_rets,
            }
        return result

    # ── Validation invariants ─────────────────────────────────────────────────

    def validation(self) -> dict:
        """Compute and return structural invariants for trust-checking.

        Persisted in the report so regressions are visible from the artifact.
        Checks:
          - overnight_holds: round-trips where exit date ≠ entry date (must be 0)
          - open_positions_at_end: positions still open after run ends (must be 0)
          - pnl_reconciled: abs(sum of exit PnLs − net equity change) < $1
        Note: per_symbol Sharpe/DD/monthly are each symbol's daily PnL contribution
        normalised by portfolio initial equity — correct for portfolio contribution
        analysis but not equivalent to a standalone single-asset backtest.
        """
        txns = self.transactions()

        # Overnight-hold check: track entry date per symbol, compare on exit
        overnight = 0
        entry_dates: Dict[str, str] = {}
        for t in txns:
            sym = t["asset"]
            if t["pnl"] is None:        # entry leg
                entry_dates[sym] = t["date"]
            else:                        # exit leg
                ed = entry_dates.get(sym)
                if ed and ed != t["date"]:
                    overnight += 1
                entry_dates.pop(sym, None)

        # Open positions remaining at end of run
        open_pos = sum(1 for pos in self.portfolio.positions.values()
                       if abs(pos.quantity) > 0)

        # PnL reconciliation: txn exits vs net equity change
        txn_pnl = sum(t["pnl"] for t in txns if t["pnl"] is not None)
        net_pnl = float(self.equity_curve.iloc[-1] - self.equity_curve.iloc[0]) if len(self.equity_curve) > 0 else 0.0
        delta = round(abs(txn_pnl - net_pnl), 2)

        return {
            "overnight_holds":        overnight,
            "open_positions_at_end":  open_pos,
            "txn_pnl":                round(txn_pnl, 2),
            "net_pnl":                round(net_pnl, 2),
            "pnl_delta":              delta,
            "pnl_reconciled":         delta < 1.0,
            "per_symbol_risk_note":   (
                "Sharpe/DD/monthly per symbol = daily PnL contribution / portfolio "
                "initial_equity. Correct for portfolio attribution; not a standalone "
                "single-asset backtest."
            ),
        }

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
            "per_symbol_metrics": self.per_symbol_metrics(),
            "transactions": self.transactions(),
            "calendar": self.calendar(),
            "validation": self.validation(),
        }


# ── Engine ────────────────────────────────────────────────────────────────────

class BacktestEngine:
    def __init__(self, config: Config, leverage: float = 1.0, eod_flatten: bool = True) -> None:
        self.config = config
        self.leverage = leverage
        self.eod_flatten = eod_flatten
        self.executor = SimulatedExecutor(config.backtest)
        self.risk = RiskManager(config.risk, leverage=leverage)

    def load_data(
        self,
        symbols: List[str],
        start: datetime,
        end: datetime,
        data_source: str = "alpaca",
        interval: str = "1m",
    ) -> Dict:
        """Load bar data for the given window. Separated from run() so callers can
        pre-load multiple windows in parallel before running the bar loops."""
        logger.info("Loading data: %d symbols  %s→%s  %s/%s",
                    len(symbols), start.date(), end.date(), data_source, interval)
        if data_source == "alpaca":
            return load_bars_alpaca(
                symbols, start, end,
                self.config.alpaca.api_key, self.config.alpaca.secret_key,
                interval=interval,
            )
        return load_bars_yfinance(symbols, start, end, interval=interval)

    def run(
        self,
        strategy: Strategy,
        symbols: List[str],
        start: datetime,
        end: datetime,
        data_source: str = "alpaca",
        interval: str = "1m",
        params: Optional[dict] = None,
        symbol_dfs: Optional[Dict] = None,   # pass pre-loaded data to skip loading
    ) -> BacktestResult:
        if symbol_dfs is None:
            symbol_dfs = self.load_data(symbols, start, end, data_source, interval)

        if not symbol_dfs:
            raise ValueError("No data loaded — check symbols and date range.")

        logger.info("Running bar loop: %d symbols  %s→%s  leverage=%.1fx",
                    len(symbol_dfs), start.date(), end.date(), self.leverage)
        # Buy & hold return per symbol: (last_close - first_close) / first_close
        buy_and_hold: Dict[str, float] = {}
        for sym, df in symbol_dfs.items():
            try:
                first = float(df["Close"].iloc[0])
                last  = float(df["Close"].iloc[-1])
                buy_and_hold[sym] = round((last - first) / first * 100, 2)
            except Exception:
                pass

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
            "buy_and_hold": buy_and_hold,
        })
        return result

    def _run_loop(self, strategy: Strategy, symbol_dfs: Dict) -> BacktestResult:
        portfolio = Portfolio(self.config.backtest.initial_cash)
        strategy.on_start()

        # ── Bar coverage report ──────────────────────────────────────────────
        bar_counts = {sym: len(df) for sym, df in symbol_dfs.items()}
        if bar_counts:
            median_count = sorted(bar_counts.values())[len(bar_counts) // 2]
            for sym, cnt in sorted(bar_counts.items()):
                coverage = cnt / median_count if median_count else 1.0
                if coverage < 0.5:
                    logger.warning(
                        "Sparse bar coverage: %s has %d bars (%.0f%% of median %d) — "
                        "orders for this symbol may be delayed at sparse timestamps",
                        sym, cnt, coverage * 100, median_count,
                    )
                else:
                    logger.info("Bar coverage: %s — %d bars", sym, cnt)

        equity_timestamps = []
        equity_values = []
        pending_orders: list = []
        _last_date = None
        _bar_count = 0
        _fill_count = 0

        for bars in iter_bars(symbol_dfs):
            ts = next(iter(bars.values())).timestamp
            # Skip bars outside regular session (pre/post market)
            if not _is_market_open_bar(ts):
                continue

            open_prices  = {sym: bar.open  for sym, bar in bars.items()}
            close_prices = {sym: bar.close for sym, bar in bars.items()}
            volumes      = {sym: bar.volume for sym, bar in bars.items()}
            bar_date = ts.astimezone(ET).date()

            _bar_count += 1
            if bar_date != _last_date:
                if _last_date is not None:
                    eq = portfolio.equity(close_prices)
                    logger.info("  %s  bars=%-5d  fills=%-4d  equity=$%s",
                                _last_date, _bar_count, _fill_count, f"{eq:>10,.0f}")
                self.risk.new_day(portfolio.equity(close_prices))
                _last_date = bar_date
                _bar_count = 0

            # Fill orders queued from previous bars.
            # Only attempt to fill an order when its symbol has a bar this timestamp.
            # Carry forward orders for absent symbols within the same trading day;
            # discard any that aged past their creation date (stale / next-day).
            if pending_orders:
                fillable = [o for o in pending_orders if o.symbol in bars]
                carry    = [
                    o for o in pending_orders
                    if o.symbol not in bars
                    and o.created_at.astimezone(ET).date() == bar_date
                ]
                discarded = len(pending_orders) - len(fillable) - len(carry)
                if discarded:
                    logger.debug(
                        "%d pending order(s) discarded (symbol absent for rest of day)", discarded
                    )

                if fillable:
                    filled = self.executor.execute(fillable, open_prices, volumes, bar_time=ts)
                    for order in filled:
                        if order.is_filled:
                            portfolio.apply_fill(order)
                            _fill_count += 1

                pending_orders = carry

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

            new_orders = self.risk.validate(signals, portfolio, close_prices)
            for order in new_orders:
                order.created_at = ts
            pending_orders.extend(new_orders)

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
