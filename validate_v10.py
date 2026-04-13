#!/usr/bin/env python3
"""Standalone 10-year validation backtest.

Uses DAILY bars (yfinance, 10yr history) to approximate intraday strategies.
Completely independent from the main trading/ codebase.

Approximations:
  - RS Short (bear sleeve):  open→close as proxy for 9:45→15:35 intraday
  - Overnight Long (bull sleeve): close→next-open as proxy for 15:30→9:45

Position sizing: FIXED per-position $ amount (no compounding).
This gives a realistic edge signal — compounding is a separate question.

Usage:
  .venv/bin/python validate_v10.py                   # default: allweather_v10
  .venv/bin/python validate_v10.py --strategy rs_short_only
  .venv/bin/python validate_v10.py --strategy overnight_only
  .venv/bin/python validate_v10.py --start 2020-01-01

Output: JSON with per-year returns and summary.
"""

import argparse
import json
import sys
from collections import defaultdict

import pandas as pd
import yfinance as yf

# ── Config ────────────────────────────────────────────────────────────────────
SYMBOLS = [
    "SPY", "QQQ", "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META",
    "AMD", "NFLX", "GOOGL", "BA", "JPM",
]
SIGNAL_SYMBOL = "VGK"
ALL_TICKERS = list(set(SYMBOLS + [SIGNAL_SYMBOL]))

INITIAL_EQUITY = 100_000
SLIPPAGE_BPS = 5


# ── Strategies ────────────────────────────────────────────────────────────────

class BaseValidator:
    """Base class for daily-bar validation strategies."""
    name = "base"
    label = "Base"

    def __init__(self, leverage=5.0, position_frac=1/8):
        self.leverage = leverage
        self.position_frac = position_frac
        # Fixed position size — no compounding
        self.pos_size = INITIAL_EQUITY * position_frac * leverage

    def run(self, dfs, dates):
        """Return list of trade dicts with date, type, symbol, pnl."""
        raise NotImplementedError


class AllWeatherV10Validator(BaseValidator):
    """Full v10: RS shorts on bear days + overnight longs on bull days."""
    name = "allweather_v10"
    label = "All-Weather v10 (Margin Overlay)"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.rs_threshold = 1.0
        self.spy_trend_days = 3
        self.overnight_top_k = 4
        self.overnight_bottom_k = 4
        self.tier2_top_k = 2
        self.tier2_bottom_k = 2
        self.min_move = 0.3

    def run(self, dfs, dates):
        spy = dfs["SPY"]
        vgk = dfs.get(SIGNAL_SYMBOL)
        spy_vwap = self._vwap_proxy(spy)
        tradable = [s for s in SYMBOLS if s != "SPY" and s in dfs]
        trades = []

        for i in range(self.spy_trend_days + 1, len(dates) - 1):
            today, tomorrow = dates[i], dates[i + 1]
            ds = today.strftime("%Y-%m-%d")

            spy_o, spy_c = spy.loc[today, "Open"], spy.loc[today, "Close"]
            spy_vwap_val = spy_vwap.loc[today] if today in spy_vwap.index else None
            spy_intra = (spy_c - spy_o) / spy_o * 100 if spy_o > 0 else 0

            spy_bear_vwap = spy_vwap_val is not None and spy_c < spy_vwap_val
            spy_bull_vwap = spy_vwap_val is not None and spy_c > spy_vwap_val
            trend_c = spy.loc[dates[i - self.spy_trend_days], "Close"]
            spy_bear_full = spy_bear_vwap and spy_c < trend_c

            vgk_bull = False
            if vgk is not None and today in vgk.index:
                vo, vc = vgk.loc[today, "Open"], vgk.loc[today, "Close"]
                if vo > 0:
                    vgk_bull = (vc - vo) / vo * 100 > 0

            # ── RS Short (signal from YESTERDAY, trade TODAY) ──
            # Yesterday's regime + RS identifies weak stocks; today we short open→close.
            # This avoids look-ahead: signal is fully known before trade opens.
            yesterday = dates[i - 1]
            if yesterday in spy.index:
                y_spy_o, y_spy_c = spy.loc[yesterday, "Open"], spy.loc[yesterday, "Close"]
                y_spy_vwap = spy_vwap.loc[yesterday] if yesterday in spy_vwap.index else None
                y_spy_intra = (y_spy_c - y_spy_o) / y_spy_o * 100 if y_spy_o > 0 else 0
                y_spy_bear = y_spy_vwap is not None and y_spy_c < y_spy_vwap
                y_trend_c = spy.loc[dates[i - 1 - self.spy_trend_days], "Close"] if (i - 1 - self.spy_trend_days) >= 0 else y_spy_c
                y_spy_bear_full = y_spy_bear and y_spy_c < y_trend_c

                if y_spy_bear_full:
                    for sym in tradable:
                        if yesterday not in dfs[sym].index or today not in dfs[sym].index:
                            continue
                        # Yesterday's RS (the signal)
                        y_so, y_sc = dfs[sym].loc[yesterday, "Open"], dfs[sym].loc[yesterday, "Close"]
                        if y_so <= 0:
                            continue
                        y_rs = (y_sc - y_so) / y_so * 100 - y_spy_intra
                        if y_rs < -self.rs_threshold:
                            # Today's trade: short at open, cover at close
                            t_o, t_c = dfs[sym].loc[today, "Open"], dfs[sym].loc[today, "Close"]
                            shares = int(self.pos_size / t_o) if t_o > 0 else 0
                            if shares > 0:
                                pnl = shares * (t_o - t_c) - shares * t_o * SLIPPAGE_BPS / 10000
                                trades.append({"date": ds, "type": "rs_short", "symbol": sym,
                                               "rs": round(y_rs, 2), "pnl": round(pnl, 2)})

            # ── Overnight Long ──
            if spy_bull_vwap or vgk_bull:
                top_k = self.overnight_top_k if spy_bull_vwap else self.tier2_top_k
                bot_k = self.overnight_bottom_k if spy_bull_vwap else self.tier2_bottom_k
                tier = 1 if spy_bull_vwap else 2

                cands = []
                for sym in tradable:
                    if today not in dfs[sym].index or tomorrow not in dfs[sym].index:
                        continue
                    so, sc = dfs[sym].loc[today, "Open"], dfs[sym].loc[today, "Close"]
                    if so <= 0:
                        continue
                    rs = (sc - so) / so * 100 - spy_intra
                    nxt_o = dfs[sym].loc[tomorrow, "Open"]
                    cands.append((sym, rs, sc, nxt_o))

                cands.sort(key=lambda x: x[1], reverse=True)
                entered = 0
                for sym, rs, entry, exit_p in cands:
                    if entered >= top_k or rs < self.min_move:
                        break
                    shares = int(self.pos_size / entry)
                    if shares > 0:
                        pnl = shares * (exit_p - entry) - shares * entry * SLIPPAGE_BPS / 10000
                        trades.append({"date": ds, "type": f"overnight_t{tier}_top",
                                       "symbol": sym, "rs": round(rs, 2), "pnl": round(pnl, 2)})
                        entered += 1

                losers = sorted([x for x in cands if x[1] < -self.min_move], key=lambda x: x[1])
                dip_n = 0
                for sym, rs, entry, exit_p in losers:
                    if dip_n >= bot_k:
                        break
                    shares = int(self.pos_size / entry)
                    if shares > 0:
                        pnl = shares * (exit_p - entry) - shares * entry * SLIPPAGE_BPS / 10000
                        trades.append({"date": ds, "type": f"overnight_t{tier}_dip",
                                       "symbol": sym, "rs": round(rs, 2), "pnl": round(pnl, 2)})
                        dip_n += 1

        return trades

    @staticmethod
    def _vwap_proxy(df):
        typical = (df["High"] + df["Low"] + df["Close"]) / 3
        return typical.rolling(20).mean()


class RSShortOnlyValidator(BaseValidator):
    """Bear sleeve only — yesterday's weak RS → short today open→close."""
    name = "rs_short_only"
    label = "RS Short Only"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.rs_threshold = 1.0
        self.spy_trend_days = 3

    def run(self, dfs, dates):
        spy = dfs["SPY"]
        spy_vwap = AllWeatherV10Validator._vwap_proxy(spy)
        tradable = [s for s in SYMBOLS if s != "SPY" and s in dfs]
        trades = []

        for i in range(self.spy_trend_days + 2, len(dates)):
            today = dates[i]
            yesterday = dates[i - 1]
            ds = today.strftime("%Y-%m-%d")

            # Yesterday's regime (the signal)
            y_spy_o, y_spy_c = spy.loc[yesterday, "Open"], spy.loc[yesterday, "Close"]
            y_spy_vwap = spy_vwap.loc[yesterday] if yesterday in spy_vwap.index else None
            y_spy_intra = (y_spy_c - y_spy_o) / y_spy_o * 100 if y_spy_o > 0 else 0
            y_spy_bear = y_spy_vwap is not None and y_spy_c < y_spy_vwap
            y_trend_c = spy.loc[dates[i - 1 - self.spy_trend_days], "Close"]
            if not (y_spy_bear and y_spy_c < y_trend_c):
                continue

            for sym in tradable:
                if yesterday not in dfs[sym].index or today not in dfs[sym].index:
                    continue
                # Yesterday's RS (signal)
                y_so, y_sc = dfs[sym].loc[yesterday, "Open"], dfs[sym].loc[yesterday, "Close"]
                if y_so <= 0:
                    continue
                y_rs = (y_sc - y_so) / y_so * 100 - y_spy_intra
                if y_rs < -self.rs_threshold:
                    # Today's trade
                    t_o, t_c = dfs[sym].loc[today, "Open"], dfs[sym].loc[today, "Close"]
                    shares = int(self.pos_size / t_o) if t_o > 0 else 0
                    if shares > 0:
                        pnl = shares * (t_o - t_c) - shares * t_o * SLIPPAGE_BPS / 10000
                        trades.append({"date": ds, "type": "rs_short", "symbol": sym,
                                       "rs": round(y_rs, 2), "pnl": round(pnl, 2)})
        return trades


class OvernightOnlyValidator(BaseValidator):
    """Bull sleeve only — overnight longs on bullish days."""
    name = "overnight_only"
    label = "Overnight Long Only"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.top_k = 4
        self.bot_k = 4
        self.min_move = 0.3

    def run(self, dfs, dates):
        spy = dfs["SPY"]
        spy_vwap = AllWeatherV10Validator._vwap_proxy(spy)
        tradable = [s for s in SYMBOLS if s != "SPY" and s in dfs]
        trades = []

        for i in range(21, len(dates) - 1):
            today, tomorrow = dates[i], dates[i + 1]
            ds = today.strftime("%Y-%m-%d")
            spy_o, spy_c = spy.loc[today, "Open"], spy.loc[today, "Close"]
            spy_vwap_val = spy_vwap.loc[today] if today in spy_vwap.index else None
            if not (spy_vwap_val and spy_c > spy_vwap_val):
                continue
            spy_intra = (spy_c - spy_o) / spy_o * 100 if spy_o > 0 else 0

            cands = []
            for sym in tradable:
                if today not in dfs[sym].index or tomorrow not in dfs[sym].index:
                    continue
                so, sc = dfs[sym].loc[today, "Open"], dfs[sym].loc[today, "Close"]
                if so <= 0:
                    continue
                rs = (sc - so) / so * 100 - spy_intra
                nxt_o = dfs[sym].loc[tomorrow, "Open"]
                cands.append((sym, rs, sc, nxt_o))

            cands.sort(key=lambda x: x[1], reverse=True)
            entered = 0
            for sym, rs, entry, exit_p in cands:
                if entered >= self.top_k or rs < self.min_move:
                    break
                shares = int(self.pos_size / entry)
                if shares > 0:
                    pnl = shares * (exit_p - entry) - shares * entry * SLIPPAGE_BPS / 10000
                    trades.append({"date": ds, "type": "overnight_top", "symbol": sym,
                                   "rs": round(rs, 2), "pnl": round(pnl, 2)})
                    entered += 1

            losers = sorted([x for x in cands if x[1] < -self.min_move], key=lambda x: x[1])
            dip_n = 0
            for sym, rs, entry, exit_p in losers:
                if dip_n >= self.bot_k:
                    break
                shares = int(self.pos_size / entry)
                if shares > 0:
                    pnl = shares * (exit_p - entry) - shares * entry * SLIPPAGE_BPS / 10000
                    trades.append({"date": ds, "type": "overnight_dip", "symbol": sym,
                                   "rs": round(rs, 2), "pnl": round(pnl, 2)})
                    dip_n += 1

        return trades


class BuyAndHoldValidator(BaseValidator):
    """Simple buy & hold benchmark — equal weight 1x, per-year decomposition."""
    name = "buy_and_hold"
    label = "Buy & Hold (Equal Weight, 1x)"

    def run(self, dfs, dates):
        tradable = [s for s in SYMBOLS if s in dfs]
        per_stock = INITIAL_EQUITY / len(tradable)  # always 1x for benchmark
        trades = []

        for sym in tradable:
            df = dfs[sym]
            first_price = df.iloc[0]["Open"]
            shares = int(per_stock / first_price) if first_price > 0 else 0
            if shares <= 0:
                continue
            # Emit one trade per year: open=first trading day, close=last trading day
            years = sorted(set(d.year for d in df.index))
            for yr in years:
                yr_df = df[df.index.year == yr]
                if len(yr_df) < 2:
                    continue
                yr_open = yr_df.iloc[0]["Open"]
                yr_close = yr_df.iloc[-1]["Close"]
                pnl = shares * (yr_close - yr_open)
                trades.append({
                    "date": yr_df.index[0].strftime("%Y-%m-%d"),
                    "type": "buy_and_hold",
                    "symbol": sym,
                    "rs": 0,
                    "pnl": round(pnl, 2),
                })
        return trades


VALIDATORS = {
    "allweather_v10": AllWeatherV10Validator,
    "rs_short_only":  RSShortOnlyValidator,
    "overnight_only": OvernightOnlyValidator,
    "buy_and_hold":   BuyAndHoldValidator,
}


# ── Compute results ──────────────────────────────────────────────────────────

def download_data(start, end):
    print("Downloading daily data...", file=sys.stderr)
    dfs = {}
    for sym in ALL_TICKERS:
        try:
            df = yf.download(sym, start=start, end=end, interval="1d",
                             progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df = df.droplevel(level=1, axis=1)
            if len(df) > 50:
                dfs[sym] = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
                print(f"  {sym}: {len(dfs[sym])} bars", file=sys.stderr)
        except Exception as e:
            print(f"  {sym}: FAILED — {e}", file=sys.stderr)
    return dfs


def compute_results(trades, strategy_label):
    # Per-year
    yearly = defaultdict(lambda: {"pnl": 0.0, "trades": 0})
    for t in trades:
        yr = t["date"][:4]
        yearly[yr]["pnl"] += t["pnl"]
        yearly[yr]["trades"] += 1

    per_year = {}
    cumulative_eq = INITIAL_EQUITY
    for yr in sorted(yearly):
        y = yearly[yr]
        start_eq = cumulative_eq
        cumulative_eq += y["pnl"]
        ret = y["pnl"] / INITIAL_EQUITY * 100  # return on initial (no compounding)
        per_year[yr] = {
            "return_on_initial_pct": round(ret, 2),
            "pnl": round(y["pnl"], 2),
            "trades": y["trades"],
        }

    total_pnl = sum(t["pnl"] for t in trades)
    total_ret = total_pnl / INITIAL_EQUITY * 100
    n_years = max(len(per_year), 1)
    avg_annual = total_ret / n_years

    # Win rate
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))

    # Equity curve from daily PnL for Sharpe/DD
    daily_pnl = defaultdict(float)
    for t in trades:
        daily_pnl[t["date"]] += t["pnl"]
    if daily_pnl:
        eq_series = pd.Series(daily_pnl).sort_index().cumsum() + INITIAL_EQUITY
        dd = (eq_series - eq_series.cummax()) / eq_series.cummax()
        max_dd = round(dd.min() * 100, 2)
        daily_rets = eq_series.pct_change().dropna()
        sharpe = 0
        if len(daily_rets) > 1 and daily_rets.std() > 0:
            sharpe = round((daily_rets.mean() / daily_rets.std()) * (252 ** 0.5), 2)
    else:
        max_dd, sharpe = 0, 0

    # Sleeve breakdown
    types = set(t["type"] for t in trades)
    sleeve = {}
    for tp in sorted(types):
        tt = [t for t in trades if t["type"] == tp]
        tw = [t for t in tt if t["pnl"] > 0]
        sleeve[tp] = {
            "trades": len(tt),
            "pnl": round(sum(t["pnl"] for t in tt), 2),
            "win_rate_pct": round(len(tw) / len(tt) * 100, 1) if tt else 0,
        }

    return {
        "strategy": strategy_label,
        "summary": {
            "initial_equity": INITIAL_EQUITY,
            "final_equity": round(INITIAL_EQUITY + total_pnl, 2),
            "total_return_pct": round(total_ret, 2),
            "avg_annual_return_pct": round(avg_annual, 2),
            "sharpe": sharpe,
            "max_drawdown_pct": max_dd,
            "total_trades": len(trades),
            "win_rate_pct": round(len(wins) / len(trades) * 100, 1) if trades else 0,
            "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
            "years": n_years,
        },
        "sleeve_breakdown": sleeve,
        "per_year": per_year,
        "note": (
            "Daily-bar approximation. RS short=open→close, overnight long=close→next-open. "
            "Position sizing is FIXED (no compounding) — returns are additive on initial equity."
        ),
    }


def main():
    p = argparse.ArgumentParser(description="10-year strategy validation (daily bars)")
    p.add_argument("--strategy", default="allweather_v10", choices=list(VALIDATORS),
                   help="Strategy to validate")
    p.add_argument("--start", default="2016-01-01")
    p.add_argument("--end", default="2026-04-12")
    p.add_argument("--leverage", type=float, default=5.0)
    p.add_argument("--symbols", nargs="+", default=None,
                   help="Override the default symbol universe (SPY always included as market proxy)")
    args = p.parse_args()

    # Override global SYMBOLS if --symbols provided
    if args.symbols:
        global SYMBOLS, ALL_TICKERS
        syms = [s.upper() for s in args.symbols]
        if "SPY" not in syms:
            syms = ["SPY"] + syms
        SYMBOLS = syms
        ALL_TICKERS = list(set(SYMBOLS + [SIGNAL_SYMBOL]))

    dfs = download_data(args.start, args.end)
    if "SPY" not in dfs:
        print("ERROR: SPY data required", file=sys.stderr)
        sys.exit(1)

    dates = dfs["SPY"].index
    cls = VALIDATORS[args.strategy]
    validator = cls(leverage=args.leverage)

    print(f"Running {validator.label} — {args.start} → {args.end}...", file=sys.stderr)
    trades = validator.run(dfs, dates)

    results = compute_results(trades, validator.label)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
