#!/usr/bin/env python3
"""Experiment runner — Claude uses this to run strategy experiments.

Usage:
  .venv/bin/python run_experiment.py \\
    --strategy orb \\
    --slug 001_orb \\
    [--start 2026-01-01] \\
    [--end 2026-04-10] \\
    [--leverage 1.0] \\
    [--interval 1m] \\
    [--data-source alpaca] \\
    [--range-minutes 15] \\
    [--stop-pct 0.5] \\
    [--entry-dev-pct 0.3] \\
    [--entry-end-hour 14]

Outputs:
  experiments/reports/<slug>.json   — structured report (read by frontend)
  experiments/runs/<slug>.md        — run note template (filled in by Claude)
  experiments/STATUS.md             — updated current state

The run note template is pre-filled with results; Claude adds qualitative
analysis (hypothesis, evaluation, decision).
"""

import argparse
import json
import logging
import multiprocessing as mp
import queue as _queue
import sys
import time
import traceback as _tb
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent

sys.path.insert(0, str(ROOT))
from trading.config import Config, EVAL_START, EVAL_END, DEFAULT_UNIVERSE
from trading.engine.backtest import BacktestEngine
from trading.strategy import STRATEGIES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def next_run_number() -> int:
    runs_dir = ROOT / "experiments" / "runs"
    existing = sorted(runs_dir.glob("*.md"))
    if not existing:
        return 1
    last = existing[-1].stem  # e.g. "011_orb"
    try:
        return int(last.split("_")[0]) + 1
    except (ValueError, IndexError):
        return len(existing) + 1


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run a strategy experiment.")
    p.add_argument("--strategy", required=True, choices=list(STRATEGIES), help="Strategy ID")
    p.add_argument("--slug", default=None, help="Run slug (auto-assigned if omitted)")
    p.add_argument("--start", default=EVAL_START, help="Start date YYYY-MM-DD")
    p.add_argument("--end", default=EVAL_END, help="End date YYYY-MM-DD")
    p.add_argument("--leverage", type=float, default=1.0)
    p.add_argument("--interval", default="1m", help="Bar interval (default 1m)")
    p.add_argument("--data-source", default="alpaca", choices=["alpaca", "yfinance"])
    p.add_argument("--symbols", nargs="+", default=None,
                   help="Override symbol universe (default: full DEFAULT_UNIVERSE)")
    p.add_argument("--status", default="in_progress",
                   choices=["in_progress", "rejected", "promising", "revised"],
                   help="Initial status to write into the report")

    # ORB params
    p.add_argument("--range-minutes", type=int, default=15)
    p.add_argument("--stop-pct", type=float, default=0.5)
    p.add_argument("--orb-direction", default="both", choices=["both", "long_only", "short_only"])

    # VWAP params (shared)
    p.add_argument("--entry-dev-pct", type=float, default=0.3)
    p.add_argument("--entry-end-hour", type=int, default=14)

    # VWAP Momentum params
    p.add_argument("--profit-target-mult", type=float, default=2.0)
    p.add_argument("--stop-mult", type=float, default=1.0)

    # Gap Fill params
    p.add_argument("--min-gap-pct", type=float, default=0.3)
    p.add_argument("--max-gap-pct", type=float, default=3.0)
    p.add_argument("--fill-target-pct", type=float, default=1.0)
    p.add_argument("--gap-direction", default="both", choices=["both", "up_only", "down_only"])

    # ORB SPY filter params
    p.add_argument("--profit-target-pct", type=float, default=0.0,
                   help="Profit target % from entry (0 = EOD flatten only)")
    p.add_argument("--no-regime-filter", action="store_true",
                   help="Disable SPY VWAP regime filter (debug/baseline)")
    p.add_argument("--stock-vwap-filter", action="store_true",
                   help="Require stock itself to be below its own VWAP for short entry")
    p.add_argument("--gap-filter-pct", type=float, default=0.0,
                   help="Require gap-down > this %% for short entry (0 = off)")
    p.add_argument("--max-trades-per-day", type=int, default=1,
                   help="Max entries per symbol per day (1=no re-entry, 2=allow one re-entry)")
    p.add_argument("--reentry-cooldown", type=int, default=5,
                   help="Bars to wait after exit before re-entering")
    p.add_argument("--spy-decline-pct", type=float, default=0.0,
                   help="Require SPY down >X%% from day open at entry time (0 = off)")
    p.add_argument("--min-range-pct", type=float, default=0.0,
                   help="Require ORB range width >X%% of range_low (0 = off; filters tight stable stocks)")
    p.add_argument("--auto-direction", action="store_true",
                   help="Auto-set ORB direction from SPY opening gap each day (regime-adaptive)")
    p.add_argument("--spy-gap-threshold", type=float, default=0.0,
                   help="Min SPY gap %% to trigger auto-direction (0=any gap; >0=only trade on gap days)")

    # Momentum Spike params
    p.add_argument("--vol-window", type=int, default=20,
                   help="Bars for rolling avg volume baseline (momentum_spike)")
    p.add_argument("--vol-mult", type=float, default=2.0,
                   help="Volume must exceed vol-mult × avg to qualify (momentum_spike)")
    p.add_argument("--breakout-window", type=int, default=10,
                   help="Bars for rolling high/low breakout level (momentum_spike)")
    p.add_argument("--ms-direction", default="both",
                   choices=["both", "long_only", "short_only"],
                   help="Direction filter for momentum_spike")

    # RSI Intraday params
    p.add_argument("--rsi-period", type=int, default=14,
                   help="RSI lookback period (rsi_intraday)")
    p.add_argument("--overbought", type=float, default=75.0,
                   help="RSI overbought threshold — short entry (rsi_intraday)")
    p.add_argument("--oversold", type=float, default=25.0,
                   help="RSI oversold threshold — long entry (rsi_intraday)")
    p.add_argument("--exit-short-rsi", type=float, default=55.0,
                   help="RSI level to exit short (rsi_intraday)")
    p.add_argument("--exit-long-rsi", type=float, default=45.0,
                   help="RSI level to exit long (rsi_intraday)")
    p.add_argument("--rsi-direction", default="both",
                   choices=["both", "long_only", "short_only"],
                   help="Direction filter for rsi_intraday")

    # Fake Breakout params
    p.add_argument("--fb-window", type=int, default=15,
                   help="Bars for rolling high/low range (fake_breakout)")
    p.add_argument("--breakout-pct", type=float, default=0.1,
                   help="Min %% pierce above/below level to qualify as breakout (fake_breakout)")
    p.add_argument("--stop-buffer-pct", type=float, default=0.1,
                   help="Buffer beyond wick extreme for stop placement (fake_breakout)")
    p.add_argument("--target-pct", type=float, default=1.5,
                   help="%% profit target from entry (fake_breakout)")
    p.add_argument("--fb-direction", default="both",
                   choices=["both", "long_only", "short_only"],
                   help="Direction filter for fake_breakout")

    # Relative Strength params
    p.add_argument("--rs-threshold", type=float, default=0.5,
                   help="Min RS difference %% (stock vs SPY return from open) to enter (relative_strength)")
    p.add_argument("--entry-after-min", type=int, default=5,
                   help="Wait this many minutes after open before entering (relative_strength)")
    p.add_argument("--rs-direction", default="both",
                   choices=["both", "long_only", "short_only"],
                   help="Direction filter for relative_strength")
    p.add_argument("--spy-trend-days", type=int, default=0,
                   help="Multi-day SPY trend filter: only short when SPY < close N days ago (0=off)")
    p.add_argument("--spy-gap-dn-pct", type=float, default=0.0,
                   help="Gap-down filter: only short when SPY opens >=X%% below prior close (0=off)")
    p.add_argument("--spy-rise-pct", type=float, default=0.0,
                   help="Bull confirmation: only long when SPY up >=X%% from day open (0=off)")

    # EMA Trend params
    p.add_argument("--fast-period", type=int, default=9,
                   help="Fast EMA period (ema_trend)")
    p.add_argument("--slow-period", type=int, default=21,
                   help="Slow EMA period (ema_trend)")
    p.add_argument("--profit-mult", type=float, default=2.0,
                   help="Profit target as multiple of stop distance (ema_trend)")
    p.add_argument("--ema-direction", default="both",
                   choices=["both", "long_only", "short_only"],
                   help="Direction filter for ema_trend")
    p.add_argument("--ema-regime-filter", action="store_true",
                   help="Enable SPY VWAP regime filter for ema_trend")

    # Gap and Go params
    p.add_argument("--gap-hold-ratio", type=float, default=0.5,
                   help="Fraction of gap that must still be held at 9:45 for entry (0.5=half)")

    # Intraday Momentum params
    p.add_argument("--momentum-threshold", type=float, default=0.3,
                   help="% from open needed to trigger entry (intraday_momentum)")
    p.add_argument("--itm-stop-pct", type=float, default=1.5,
                   help="Stop % from entry (intraday_momentum)")
    p.add_argument("--itm-direction", default="both",
                   choices=["both", "long_only", "short_only"],
                   help="Direction filter for intraday_momentum")
    p.add_argument("--itm-entry-hour", type=int, default=10,
                   help="ET hour for entry check (intraday_momentum)")
    p.add_argument("--itm-entry-minute", type=int, default=0,
                   help="ET minute for entry check (intraday_momentum)")

    # Cross-Sectional Revert / Volume / Exhaustion params
    p.add_argument("--top-k", type=int, default=3,
                   help="Short top K morning winners (cross_sectional_revert)")
    p.add_argument("--bottom-k", type=int, default=3,
                   help="Long bottom K morning losers (cross_sectional_revert)")
    p.add_argument("--rvol-min", type=float, default=1.5,
                   help="Minimum relative volume to qualify (volume_momentum)")
    p.add_argument("--tier2-top-k", type=int, default=1,
                   help="Reduced top-K for tier-2 nights (allweather_v4)")
    p.add_argument("--tier2-bottom-k", type=int, default=1,
                   help="Reduced bottom-K for tier-2 nights (allweather_v4)")
    p.add_argument("--exit-win-min", type=int, default=15,
                   help="Minutes after open to exit winning overnight positions")
    p.add_argument("--exit-loss-min", type=int, default=5,
                   help="Minutes after open to exit losing overnight positions")
    p.add_argument("--fear-symbol", default="UVXY",
                   help="VIX proxy ETF for fear reversion signal")
    p.add_argument("--fear-threshold", type=float, default=3.0,
                   help="Fear ETF must be up this %% for tier-3 override")
    p.add_argument("--selloff-threshold", type=float, default=1.0,
                   help="SPY must be down this %% for selloff reversion")
    p.add_argument("--tier3-top-k", type=int, default=1,
                   help="Positions on fear/selloff nights")
    p.add_argument("--tier3-bottom-k", type=int, default=1,
                   help="Positions on fear/selloff nights")
    p.add_argument("--dow-boost-days", default="TUE,WED,THU",
                   help="Comma-separated days for DoW boost")
    p.add_argument("--dow-extra-k", type=int, default=1,
                   help="Extra positions on DoW boost days")
    p.add_argument("--global-signal", default="VGK",
                   help="International ETF for global signal (VGK, EFA, EWG)")
    p.add_argument("--global-min-return", type=float, default=0.3,
                   help="Min return %% on global ETF for tier-2 override")
    p.add_argument("--sma-period", type=int, default=10,
                   help="SPY SMA period for bull trend in allweather_v2 (10=~2 weeks)")
    p.add_argument("--extreme-pct", type=float, default=2.0,
                   help="Min extreme move %% from open (exhaustion_fade)")

    # AllWeather v6 params
    p.add_argument("--sma-bull-period", type=int, default=5,
                   help="SPY SMA period for bull regime detection (allweather_v6)")
    p.add_argument("--long-top-k", type=int, default=3,
                   help="Top-K momentum winners for swing longs (allweather_v6)")
    p.add_argument("--long-bottom-k", type=int, default=3,
                   help="Bottom-K dip buys for swing longs (allweather_v6)")
    p.add_argument("--trail-stop-pct", type=float, default=3.0,
                   help="Trailing stop %% from peak (allweather_v6)")
    p.add_argument("--max-hold-days", type=int, default=15,
                   help="Max days to hold swing position (allweather_v6)")
    p.add_argument("--min-rs-entry", type=float, default=0.3,
                   help="Min RS move to qualify for swing entry (allweather_v6)")
    p.add_argument("--exit-morning-min", type=int, default=15,
                   help="Minutes after open to exit longs on regime change (allweather_v6)")

    # AllWeather v7 params
    p.add_argument("--long-max-positions", type=int, default=8,
                   help="Max concurrent long swing positions (allweather_v7)")
    p.add_argument("--catastrophe-stop-pct", type=float, default=15.0,
                   help="Only exit individual long on this %% drop (allweather_v7)")
    p.add_argument("--rebalance-daily", action="store_true", default=True,
                   help="Add new positions daily in bull regime (allweather_v7)")

    # AllWeather v8 params
    p.add_argument("--loser-exit-min", type=int, default=15,
                   help="Exit losers this many min after open (allweather_v8)")
    p.add_argument("--winner-hold-hour", type=int, default=15,
                   help="Hold winners until this hour ET (allweather_v8)")
    p.add_argument("--winner-hold-min", type=int, default=25,
                   help="Hold winners until this minute ET (allweather_v8)")
    p.add_argument("--multiday-extend", action="store_true", default=False,
                   help="Extend winning positions to next day (allweather_v8)")
    p.add_argument("--max-extend-days", type=int, default=3,
                   help="Max days to extend winners (allweather_v8)")
    p.add_argument("--extend-stop-pct", type=float, default=3.0,
                   help="Trailing stop for extended positions (allweather_v8)")

    # AllWeather v9 params
    p.add_argument("--tom-top-k", type=int, default=5,
                   help="Top-K winners on TOM days (allweather_v9)")
    p.add_argument("--tom-bottom-k", type=int, default=5,
                   help="Bottom-K dip buys on TOM days (allweather_v9)")
    p.add_argument("--base-top-k", type=int, default=1,
                   help="Top-K on non-TOM days (allweather_v9)")
    p.add_argument("--base-bottom-k", type=int, default=1,
                   help="Bottom-K on non-TOM days (allweather_v9)")
    p.add_argument("--prefer-high-beta-tom", action="store_true", default=True,
                   help="Prefer high-beta stocks on TOM days (allweather_v9)")

    # AllWeather v10 params
    p.add_argument("--rs-close-hour", type=int, default=15,
                   help="Hour to close RS shorts (allweather_v10, default 15)")
    p.add_argument("--rs-close-minute", type=int, default=35,
                   help="Minute to close RS shorts (allweather_v10, default 35 = AFTER overnight entry)")

    # Prior Day Levels params
    p.add_argument("--pdl-mode", default="all",
                   choices=["all", "breakout_only", "rejection_only", "bounce_only"],
                   help="Prior-day level mode (prior_day_levels)")
    p.add_argument("--approach-pct", type=float, default=0.1,
                   help="% within level to count as approach (prior_day_levels)")
    p.add_argument("--breakout-confirm-pct", type=float, default=0.05,
                   help="% above PDH for breakout confirm (prior_day_levels)")
    p.add_argument("--breakout-rr", type=float, default=1.5,
                   help="Risk:reward for breakout (prior_day_levels)")
    p.add_argument("--rejection-fail-pct", type=float, default=0.15,
                   help="% below PDH for rejection (prior_day_levels)")
    p.add_argument("--bounce-confirm-pct", type=float, default=0.15,
                   help="% above PDL for bounce (prior_day_levels)")
    p.add_argument("--max-stop-pct-pdl", type=float, default=1.5,
                   help="Max stop distance %% (prior_day_levels)")

    # AllWeather v11 params
    p.add_argument("--gap-filter", action="store_true", default=True,
                   help="Enable gap quality filter (allweather_v11)")
    p.add_argument("--no-gap-filter", action="store_true", default=False,
                   help="Disable gap quality filter")
    p.add_argument("--gap-fade-pct", type=float, default=2.0,
                   help="Skip stocks gapped > this %% (allweather_v11)")
    p.add_argument("--use-daily-ema", action="store_true", default=False,
                   help="Use daily EMA instead of VWAP for regime (allweather_v11)")
    p.add_argument("--daily-ema-period", type=int, default=20,
                   help="Daily EMA period (allweather_v11)")
    p.add_argument("--breadth-filter", action="store_true", default=True,
                   help="Enable breadth filter (allweather_v11)")
    p.add_argument("--no-breadth-filter", action="store_true", default=False,
                   help="Disable breadth filter")
    p.add_argument("--breadth-min-pct", type=float, default=45.0,
                   help="Min %% stocks up for breadth (allweather_v11)")
    p.add_argument("--use-overnight-beta", action="store_true", default=True,
                   help="Prefer high overnight-gap stocks (allweather_v11)")

    # Modular strategy selector type
    p.add_argument("--selector", default="composite",
                   choices=["composite", "adaptive", "abnormality", "momentum"],
                   help="Stock selector type for modular strategy")

    # Morning Spike Fade params
    p.add_argument("--spike-pct", type=float, default=1.0,
                   help="Stock must be up/down this %% from open to trigger fade (morning_spike_fade)")
    p.add_argument("--fade-target-pct", type=float, default=1.5,
                   help="Profit target %% for fade (morning_spike_fade)")
    p.add_argument("--fade-direction", default="both",
                   choices=["both", "short_only", "long_only"],
                   help="Direction filter for morning_spike_fade")
    p.add_argument("--no-vwap-extended", action="store_true",
                   help="Disable VWAP extension requirement (morning_spike_fade)")
    p.add_argument("--fade-regime-filter", action="store_true",
                   help="Enable SPY VWAP regime filter for fade direction (morning_spike_fade)")

    # Overnight Momentum params
    p.add_argument("--min-return-pct", type=float, default=0.5,
                   help="Min session return %% to enter overnight (overnight_momentum)")
    p.add_argument("--overnight-stop-pct", type=float, default=2.0,
                   help="Stop %% from entry for overnight holds")
    p.add_argument("--overnight-direction", default="both",
                   choices=["both", "long_only", "short_only"],
                   help="Direction for overnight_momentum")
    p.add_argument("--overnight-regime-filter", action="store_true",
                   help="SPY VWAP regime filter for overnight_momentum")
    p.add_argument("--exit-after-min", type=int, default=15,
                   help="Exit this many minutes after next-day open (overnight_momentum)")
    p.add_argument("--bull-regime", default="vwap",
                   choices=["vwap", "up_from_open", "none"],
                   help="Bull regime filter mode for allweather overnight sleeve")
    p.add_argument("--max-position-pct", type=float, default=0.10,
                   help="Max position size as fraction of equity (default 0.10 = 10%%)")
    p.add_argument("--no-eod-flatten", action="store_true",
                   help="Disable EOD flatten (for overnight/swing strategies)")

    # RS enhancements
    p.add_argument("--max-daily-signals", type=int, default=0,
                   help="Cap total RS signals per day (0=unlimited); approximates rank-and-trade")
    p.add_argument("--atr-expansion", action="store_true",
                   help="Only trade when SPY session range > rolling average (skip dead tape)")
    p.add_argument("--atr-lookback", type=int, default=14,
                   help="Days to average for ATR expansion baseline")

    # VWAP Trend params
    p.add_argument("--spy-min-move-pct", type=float, default=0.2,
                   help="SPY must be this %% from open to confirm session (vwap_trend)")
    p.add_argument("--rs-confirm-pct", type=float, default=0.0,
                   help="Stock must outperform SPY by this %% to enter (vwap_trend, 0=off)")
    p.add_argument("--vwap-direction", default="both",
                   choices=["both", "long_only", "short_only"],
                   help="Direction filter for vwap_trend")

    return p


def make_strategy(strategy_id: str, symbols, args):
    cls = STRATEGIES[strategy_id]
    if strategy_id == "orb":
        return cls(symbols, range_minutes=args.range_minutes, stop_pct=args.stop_pct,
                   direction=args.orb_direction), {
            "range_minutes": args.range_minutes,
            "stop_pct": args.stop_pct,
            "direction": args.orb_direction,
        }
    elif strategy_id == "vwap_reversion":
        return cls(symbols, entry_dev_pct=args.entry_dev_pct, stop_pct=args.stop_pct,
                   entry_end_hour=args.entry_end_hour), {
            "entry_dev_pct": args.entry_dev_pct,
            "stop_pct": args.stop_pct,
            "entry_end_hour": args.entry_end_hour,
        }
    elif strategy_id == "vwap_momentum":
        return cls(symbols, entry_dev_pct=args.entry_dev_pct,
                   profit_target_mult=args.profit_target_mult,
                   stop_mult=args.stop_mult,
                   entry_end_hour=args.entry_end_hour), {
            "entry_dev_pct": args.entry_dev_pct,
            "profit_target_mult": args.profit_target_mult,
            "stop_mult": args.stop_mult,
            "entry_end_hour": args.entry_end_hour,
        }
    elif strategy_id == "gap_fill":
        return cls(symbols, min_gap_pct=args.min_gap_pct, max_gap_pct=args.max_gap_pct,
                   stop_mult=args.stop_mult, fill_target_pct=args.fill_target_pct,
                   direction=args.gap_direction), {
            "min_gap_pct": args.min_gap_pct,
            "max_gap_pct": args.max_gap_pct,
            "stop_mult": args.stop_mult,
            "fill_target_pct": args.fill_target_pct,
            "direction": args.gap_direction,
        }
    elif strategy_id == "ema_trend":
        return cls(symbols, fast_period=args.fast_period, slow_period=args.slow_period,
                   stop_pct=args.stop_pct, profit_mult=args.profit_mult,
                   entry_end_hour=args.entry_end_hour,
                   direction=args.ema_direction,
                   regime_filter=args.ema_regime_filter), {
            "fast_period": args.fast_period,
            "slow_period": args.slow_period,
            "stop_pct": args.stop_pct,
            "profit_mult": args.profit_mult,
            "entry_end_hour": args.entry_end_hour,
            "direction": args.ema_direction,
            "regime_filter": args.ema_regime_filter,
        }
    elif strategy_id == "orb_spy_filter":
        return cls(symbols, range_minutes=args.range_minutes, stop_pct=args.stop_pct,
                   profit_target_pct=args.profit_target_pct,
                   direction=args.orb_direction,
                   regime_filter=not args.no_regime_filter,
                   stock_vwap_filter=args.stock_vwap_filter,
                   gap_filter_pct=args.gap_filter_pct,
                   max_trades_per_day=args.max_trades_per_day,
                   reentry_cooldown=args.reentry_cooldown,
                   spy_decline_pct=args.spy_decline_pct,
                   min_range_pct=args.min_range_pct,
                   auto_direction=args.auto_direction,
                   spy_gap_threshold=args.spy_gap_threshold), {
            "range_minutes": args.range_minutes,
            "stop_pct": args.stop_pct,
            "profit_target_pct": args.profit_target_pct,
            "direction": args.orb_direction,
            "regime_filter": not args.no_regime_filter,
            "stock_vwap_filter": args.stock_vwap_filter,
            "gap_filter_pct": args.gap_filter_pct,
            "max_trades_per_day": args.max_trades_per_day,
            "reentry_cooldown": args.reentry_cooldown,
            "spy_decline_pct": args.spy_decline_pct,
            "min_range_pct": args.min_range_pct,
            "auto_direction": args.auto_direction,
            "spy_gap_threshold": args.spy_gap_threshold,
        }
    elif strategy_id == "momentum_spike":
        return cls(symbols, vol_window=args.vol_window, vol_mult=args.vol_mult,
                   breakout_window=args.breakout_window, stop_pct=args.stop_pct,
                   direction=args.ms_direction,
                   regime_filter=not args.no_regime_filter,
                   entry_end_hour=args.entry_end_hour), {
            "vol_window": args.vol_window,
            "vol_mult": args.vol_mult,
            "breakout_window": args.breakout_window,
            "stop_pct": args.stop_pct,
            "direction": args.ms_direction,
            "regime_filter": not args.no_regime_filter,
            "entry_end_hour": args.entry_end_hour,
        }
    elif strategy_id == "rsi_intraday":
        return cls(symbols, rsi_period=args.rsi_period,
                   overbought=args.overbought, oversold=args.oversold,
                   exit_short=args.exit_short_rsi, exit_long=args.exit_long_rsi,
                   stop_pct=args.stop_pct,
                   profit_target_pct=args.profit_target_pct,
                   direction=args.rsi_direction,
                   regime_filter=not args.no_regime_filter,
                   entry_end_hour=args.entry_end_hour), {
            "rsi_period": args.rsi_period,
            "overbought": args.overbought,
            "oversold": args.oversold,
            "exit_short_rsi": args.exit_short_rsi,
            "exit_long_rsi": args.exit_long_rsi,
            "stop_pct": args.stop_pct,
            "profit_target_pct": args.profit_target_pct,
            "direction": args.rsi_direction,
            "regime_filter": not args.no_regime_filter,
            "entry_end_hour": args.entry_end_hour,
        }
    elif strategy_id == "fake_breakout":
        return cls(symbols, window=args.fb_window,
                   breakout_pct=args.breakout_pct,
                   stop_buffer_pct=args.stop_buffer_pct,
                   target_pct=args.target_pct,
                   direction=args.fb_direction,
                   regime_filter=not args.no_regime_filter,
                   entry_end_hour=args.entry_end_hour), {
            "window": args.fb_window,
            "breakout_pct": args.breakout_pct,
            "stop_buffer_pct": args.stop_buffer_pct,
            "target_pct": args.target_pct,
            "direction": args.fb_direction,
            "regime_filter": not args.no_regime_filter,
            "entry_end_hour": args.entry_end_hour,
        }
    elif strategy_id == "relative_strength":
        return cls(symbols, rs_threshold=args.rs_threshold,
                   stop_pct=args.stop_pct,
                   profit_target_pct=args.profit_target_pct,
                   direction=args.rs_direction,
                   regime_filter=not args.no_regime_filter,
                   spy_decline_pct=args.spy_decline_pct,
                   spy_trend_days=args.spy_trend_days,
                   spy_gap_dn_pct=args.spy_gap_dn_pct,
                   spy_rise_pct=args.spy_rise_pct,
                   entry_after_min=args.entry_after_min,
                   entry_end_hour=args.entry_end_hour,
                   max_daily_signals=args.max_daily_signals,
                   atr_expansion_filter=args.atr_expansion,
                   atr_lookback=args.atr_lookback), {
            "rs_threshold": args.rs_threshold,
            "stop_pct": args.stop_pct,
            "profit_target_pct": args.profit_target_pct,
            "direction": args.rs_direction,
            "regime_filter": not args.no_regime_filter,
            "spy_decline_pct": args.spy_decline_pct,
            "spy_trend_days": args.spy_trend_days,
            "spy_gap_dn_pct": args.spy_gap_dn_pct,
            "spy_rise_pct": args.spy_rise_pct,
            "entry_after_min": args.entry_after_min,
            "entry_end_hour": args.entry_end_hour,
            "max_daily_signals": args.max_daily_signals,
            "atr_expansion_filter": args.atr_expansion,
            "atr_lookback": args.atr_lookback,
        }
    elif strategy_id == "vwap_trend":
        return cls(symbols, stop_pct=args.stop_pct,
                   profit_target_pct=args.profit_target_pct,
                   direction=args.vwap_direction,
                   spy_min_move_pct=args.spy_min_move_pct,
                   rs_confirm_pct=args.rs_confirm_pct,
                   entry_end_hour=args.entry_end_hour), {
            "stop_pct": args.stop_pct,
            "profit_target_pct": args.profit_target_pct,
            "direction": args.vwap_direction,
            "spy_min_move_pct": args.spy_min_move_pct,
            "rs_confirm_pct": args.rs_confirm_pct,
            "entry_end_hour": args.entry_end_hour,
        }
    elif strategy_id == "gap_and_go":
        return cls(symbols, min_gap_pct=args.min_gap_pct,
                   max_gap_pct=args.max_gap_pct,
                   gap_hold_ratio=args.gap_hold_ratio,
                   stop_pct=args.stop_pct,
                   profit_target_pct=args.profit_target_pct,
                   spy_min_move_pct=args.spy_min_move_pct,
                   entry_after_min=args.entry_after_min,
                   entry_end_hour=args.entry_end_hour), {
            "min_gap_pct": args.min_gap_pct,
            "max_gap_pct": args.max_gap_pct,
            "gap_hold_ratio": args.gap_hold_ratio,
            "stop_pct": args.stop_pct,
            "profit_target_pct": args.profit_target_pct,
            "spy_min_move_pct": args.spy_min_move_pct,
            "entry_after_min": args.entry_after_min,
            "entry_end_hour": args.entry_end_hour,
        }
    elif strategy_id == "vwap_reclaim":
        return cls(symbols, stop_pct=args.stop_pct,
                   profit_target_pct=args.profit_target_pct,
                   spy_min_move_pct=args.spy_min_move_pct,
                   rs_min_pct=args.rs_confirm_pct,
                   entry_end_hour=args.entry_end_hour), {
            "stop_pct": args.stop_pct,
            "profit_target_pct": args.profit_target_pct,
            "spy_min_move_pct": args.spy_min_move_pct,
            "rs_min_pct": args.rs_confirm_pct,
            "entry_end_hour": args.entry_end_hour,
        }
    elif strategy_id == "intraday_momentum":
        return cls(symbols,
                   momentum_threshold=args.momentum_threshold,
                   stop_pct=args.itm_stop_pct,
                   profit_target_pct=args.profit_target_pct,
                   direction=args.itm_direction,
                   entry_hour=args.itm_entry_hour,
                   entry_minute=args.itm_entry_minute), {
            "momentum_threshold": args.momentum_threshold,
            "stop_pct": args.itm_stop_pct,
            "profit_target_pct": args.profit_target_pct,
            "direction": args.itm_direction,
            "entry_hour": args.itm_entry_hour,
            "entry_minute": args.itm_entry_minute,
        }
    elif strategy_id == "combined_rs_momentum":
        return cls(symbols,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_profit_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour,
                   momentum_threshold=args.momentum_threshold,
                   itm_stop_pct=args.itm_stop_pct,
                   itm_entry_hour=args.itm_entry_hour,
                   itm_entry_minute=args.itm_entry_minute), {
            "rs_threshold": args.rs_threshold,
            "rs_stop_pct": args.stop_pct,
            "rs_profit_target_pct": args.profit_target_pct,
            "spy_trend_days": args.spy_trend_days,
            "rs_entry_after_min": args.entry_after_min,
            "rs_entry_end_hour": args.entry_end_hour,
            "momentum_threshold": args.momentum_threshold,
            "itm_stop_pct": args.itm_stop_pct,
            "itm_entry_hour": args.itm_entry_hour,
            "itm_entry_minute": args.itm_entry_minute,
        }
    elif strategy_id == "morning_spike_fade":
        return cls(symbols,
                   spike_pct=args.spike_pct,
                   stop_pct=args.stop_pct,
                   target_pct=args.fade_target_pct,
                   direction=args.fade_direction,
                   require_vwap_extended=not args.no_vwap_extended,
                   regime_filter=args.fade_regime_filter,
                   entry_after_min=args.entry_after_min,
                   entry_end_hour=args.entry_end_hour), {
            "spike_pct": args.spike_pct,
            "stop_pct": args.stop_pct,
            "target_pct": args.fade_target_pct,
            "direction": args.fade_direction,
            "require_vwap_extended": not args.no_vwap_extended,
            "regime_filter": args.fade_regime_filter,
            "entry_after_min": args.entry_after_min,
            "entry_end_hour": args.entry_end_hour,
        }
    elif strategy_id == "overnight_momentum":
        return cls(symbols,
                   min_return_pct=args.min_return_pct,
                   stop_pct=args.overnight_stop_pct,
                   direction=args.overnight_direction,
                   regime_filter=args.overnight_regime_filter,
                   entry_hour=args.itm_entry_hour,
                   entry_minute=args.itm_entry_minute,
                   exit_after_min=args.exit_after_min), {
            "min_return_pct": args.min_return_pct,
            "stop_pct": args.overnight_stop_pct,
            "direction": args.overnight_direction,
            "regime_filter": args.overnight_regime_filter,
            "entry_hour": args.itm_entry_hour,
            "entry_minute": args.itm_entry_minute,
            "exit_after_min": args.exit_after_min,
        }
    elif strategy_id == "allweather":
        return cls(symbols,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour,
                   overnight_min_return=args.min_return_pct,
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_entry_hour=args.itm_entry_hour,
                   overnight_entry_minute=args.itm_entry_minute,
                   overnight_exit_after_min=args.exit_after_min,
                   bull_regime=args.bull_regime), {
            "rs_threshold": args.rs_threshold,
            "rs_stop_pct": args.stop_pct,
            "rs_target_pct": args.profit_target_pct,
            "spy_trend_days": args.spy_trend_days,
            "rs_entry_after_min": args.entry_after_min,
            "rs_entry_end_hour": args.entry_end_hour,
            "overnight_min_return": args.min_return_pct,
            "overnight_stop_pct": args.overnight_stop_pct,
            "overnight_entry_hour": args.itm_entry_hour,
            "overnight_entry_minute": args.itm_entry_minute,
            "overnight_exit_after_min": args.exit_after_min,
            "bull_regime": args.bull_regime,
        }
    elif strategy_id == "allweather_v3":
        return cls(symbols,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour,
                   overnight_top_k=getattr(args, 'top_k', 3),
                   overnight_bottom_k=getattr(args, 'bottom_k', 3),
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_exit_after_min=args.exit_after_min,
                   overnight_entry_hour=args.itm_entry_hour,
                   overnight_entry_minute=args.itm_entry_minute,
                   overnight_min_move=args.momentum_threshold), {
            "rs_threshold": args.rs_threshold,
            "rs_stop_pct": args.stop_pct,
            "rs_target_pct": args.profit_target_pct,
            "spy_trend_days": args.spy_trend_days,
            "overnight_top_k": getattr(args, 'top_k', 3),
            "overnight_bottom_k": getattr(args, 'bottom_k', 3),
            "overnight_stop_pct": args.overnight_stop_pct,
            "overnight_exit_after_min": args.exit_after_min,
            "overnight_min_move": args.momentum_threshold,
        }
    elif strategy_id == "allweather_v5":
        return cls(symbols,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour,
                   overnight_top_k=getattr(args, 'top_k', 3),
                   overnight_bottom_k=getattr(args, 'bottom_k', 3),
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_min_move=args.momentum_threshold,
                   overnight_entry_hour=args.itm_entry_hour,
                   overnight_entry_minute=args.itm_entry_minute,
                   overnight_exit_after_min=args.exit_after_min,
                   global_signal_symbol=getattr(args, 'global_signal', 'VGK'),
                   tier2_top_k=getattr(args, 'tier2_top_k', 1),
                   tier2_bottom_k=getattr(args, 'tier2_bottom_k', 1),
                   fear_symbol=getattr(args, 'fear_symbol', 'UVXY'),
                   fear_threshold=getattr(args, 'fear_threshold', 3.0),
                   selloff_threshold=getattr(args, 'selloff_threshold', 1.0),
                   tier3_top_k=getattr(args, 'tier3_top_k', 1),
                   tier3_bottom_k=getattr(args, 'tier3_bottom_k', 1),
                   dow_boost_days=getattr(args, 'dow_boost_days', 'TUE,WED,THU'),
                   dow_extra_k=getattr(args, 'dow_extra_k', 1)), {
            "rs_threshold": args.rs_threshold,
            "spy_trend_days": args.spy_trend_days,
            "overnight_top_k": getattr(args, 'top_k', 3),
            "overnight_bottom_k": getattr(args, 'bottom_k', 3),
            "overnight_stop_pct": args.overnight_stop_pct,
            "global_signal": getattr(args, 'global_signal', 'VGK'),
            "fear_symbol": getattr(args, 'fear_symbol', 'UVXY'),
            "fear_threshold": getattr(args, 'fear_threshold', 3.0),
            "selloff_threshold": getattr(args, 'selloff_threshold', 1.0),
            "dow_boost_days": getattr(args, 'dow_boost_days', 'TUE,WED,THU'),
            "dow_extra_k": getattr(args, 'dow_extra_k', 1),
        }
    elif strategy_id == "allweather_global":
        return cls(symbols,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour,
                   overnight_top_k=getattr(args, 'top_k', 3),
                   overnight_bottom_k=getattr(args, 'bottom_k', 3),
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_min_move=args.momentum_threshold,
                   overnight_entry_hour=args.itm_entry_hour,
                   overnight_entry_minute=args.itm_entry_minute,
                   overnight_exit_after_min=args.exit_after_min,
                   global_signal_symbol=getattr(args, 'global_signal', 'VGK'),
                   global_min_return=getattr(args, 'global_min_return', 0.3),
                   tier2_top_k=getattr(args, 'tier2_top_k', 2),
                   tier2_bottom_k=getattr(args, 'tier2_bottom_k', 2)), {
            "rs_threshold": args.rs_threshold,
            "spy_trend_days": args.spy_trend_days,
            "overnight_top_k": getattr(args, 'top_k', 3),
            "overnight_bottom_k": getattr(args, 'bottom_k', 3),
            "overnight_stop_pct": args.overnight_stop_pct,
            "overnight_exit_after_min": args.exit_after_min,
            "global_signal_symbol": getattr(args, 'global_signal', 'VGK'),
            "global_min_return": getattr(args, 'global_min_return', 0.3),
            "tier2_top_k": getattr(args, 'tier2_top_k', 2),
            "tier2_bottom_k": getattr(args, 'tier2_bottom_k', 2),
        }
    elif strategy_id == "allweather_v4":
        return cls(symbols,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour,
                   overnight_top_k=getattr(args, 'top_k', 3),
                   overnight_bottom_k=getattr(args, 'bottom_k', 3),
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_min_move=args.momentum_threshold,
                   overnight_entry_hour=args.itm_entry_hour,
                   overnight_entry_minute=args.itm_entry_minute,
                   sma_period=getattr(args, 'sma_period', 10),
                   tier2_top_k=getattr(args, 'tier2_top_k', 1),
                   tier2_bottom_k=getattr(args, 'tier2_bottom_k', 1),
                   exit_win_min=getattr(args, 'exit_win_min', 15),
                   exit_loss_min=getattr(args, 'exit_loss_min', 5)), {
            "rs_threshold": args.rs_threshold,
            "spy_trend_days": args.spy_trend_days,
            "overnight_top_k": getattr(args, 'top_k', 3),
            "overnight_bottom_k": getattr(args, 'bottom_k', 3),
            "overnight_stop_pct": args.overnight_stop_pct,
            "overnight_min_move": args.momentum_threshold,
            "sma_period": getattr(args, 'sma_period', 10),
            "tier2_top_k": getattr(args, 'tier2_top_k', 1),
            "tier2_bottom_k": getattr(args, 'tier2_bottom_k', 1),
            "exit_win_min": getattr(args, 'exit_win_min', 15),
            "exit_loss_min": getattr(args, 'exit_loss_min', 5),
        }
    elif strategy_id == "allweather_v2":
        return cls(symbols,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour,
                   sma_period=getattr(args, 'sma_period', 10),
                   overnight_top_k=getattr(args, 'top_k', 5),
                   overnight_min_rs=getattr(args, 'min_return_pct', 0.0),
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_exit_after_min=args.exit_after_min,
                   overnight_entry_hour=args.itm_entry_hour,
                   overnight_entry_minute=args.itm_entry_minute,
                   require_vwap_bull=getattr(args, 'overnight_regime_filter', False)), {
            "rs_threshold": args.rs_threshold,
            "rs_stop_pct": args.stop_pct,
            "rs_target_pct": args.profit_target_pct,
            "spy_trend_days": args.spy_trend_days,
            "sma_period": getattr(args, 'sma_period', 10),
            "overnight_top_k": getattr(args, 'top_k', 5),
            "overnight_min_rs": getattr(args, 'min_return_pct', 0.0),
            "overnight_stop_pct": args.overnight_stop_pct,
            "overnight_exit_after_min": args.exit_after_min,
            "require_vwap_bull": getattr(args, 'overnight_regime_filter', False),
        }
    elif strategy_id == "cross_sectional_revert":
        return cls(symbols,
                   top_k=getattr(args, 'top_k', 3),
                   bottom_k=getattr(args, 'bottom_k', 3),
                   min_move_pct=args.momentum_threshold,
                   stop_pct=args.stop_pct,
                   profit_target_pct=args.profit_target_pct,
                   entry_hour=args.itm_entry_hour,
                   entry_minute=args.itm_entry_minute), {
            "top_k": getattr(args, 'top_k', 3),
            "bottom_k": getattr(args, 'bottom_k', 3),
            "min_move_pct": args.momentum_threshold,
            "stop_pct": args.stop_pct,
            "profit_target_pct": args.profit_target_pct,
            "entry_hour": args.itm_entry_hour,
            "entry_minute": args.itm_entry_minute,
        }
    elif strategy_id == "volume_momentum":
        return cls(symbols,
                   momentum_threshold=args.momentum_threshold,
                   stop_pct=args.itm_stop_pct,
                   profit_target_pct=args.profit_target_pct,
                   direction=args.itm_direction,
                   rvol_min=getattr(args, 'rvol_min', 1.5),
                   entry_hour=args.itm_entry_hour,
                   entry_minute=args.itm_entry_minute), {
            "momentum_threshold": args.momentum_threshold,
            "stop_pct": args.itm_stop_pct,
            "profit_target_pct": args.profit_target_pct,
            "direction": args.itm_direction,
            "rvol_min": getattr(args, 'rvol_min', 1.5),
            "entry_hour": args.itm_entry_hour,
            "entry_minute": args.itm_entry_minute,
        }
    elif strategy_id == "exhaustion_fade":
        return cls(symbols,
                   extreme_pct=getattr(args, 'extreme_pct', 2.0),
                   vol_mult=args.vol_mult,
                   stop_pct=args.stop_pct,
                   target_pct=args.fade_target_pct,
                   direction=args.fade_direction,
                   entry_after_min=args.entry_after_min,
                   entry_end_hour=args.entry_end_hour), {
            "extreme_pct": getattr(args, 'extreme_pct', 2.0),
            "vol_mult": args.vol_mult,
            "stop_pct": args.stop_pct,
            "target_pct": args.fade_target_pct,
            "direction": args.fade_direction,
            "entry_after_min": args.entry_after_min,
            "entry_end_hour": args.entry_end_hour,
        }
    elif strategy_id == "allweather_v12":
        v12_entry_h = getattr(args, 'itm_entry_hour', 15)
        v12_entry_m = getattr(args, 'itm_entry_minute', 30)
        if v12_entry_h == 10 and v12_entry_m == 0:
            v12_entry_h, v12_entry_m = 15, 30
        return cls(symbols,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour,
                   rs_close_hour=getattr(args, 'rs_close_hour', 15),
                   rs_close_minute=getattr(args, 'rs_close_minute', 35),
                   use_sector_rs=True,
                   overnight_top_k=getattr(args, 'top_k', 4),
                   overnight_bottom_k=getattr(args, 'bottom_k', 4),
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_min_move=args.momentum_threshold,
                   overnight_entry_hour=v12_entry_h,
                   overnight_entry_minute=v12_entry_m,
                   overnight_exit_after_min=args.exit_after_min,
                   global_signal_symbol=getattr(args, 'global_signal', 'VGK'),
                   global_min_return=getattr(args, 'global_min_return', 0.0),
                   tier2_top_k=getattr(args, 'tier2_top_k', 2),
                   tier2_bottom_k=getattr(args, 'tier2_bottom_k', 2)), {
            "rs_threshold": args.rs_threshold,
            "spy_trend_days": args.spy_trend_days,
            "use_sector_rs": True,
            "rs_close_minute": getattr(args, 'rs_close_minute', 35),
            "exit_after_min": args.exit_after_min,
            "overnight_top_k": getattr(args, 'top_k', 4),
            "overnight_bottom_k": getattr(args, 'bottom_k', 4),
        }
    elif strategy_id == "allweather_v11":
        v11_entry_h = getattr(args, 'itm_entry_hour', 15)
        v11_entry_m = getattr(args, 'itm_entry_minute', 30)
        if v11_entry_h == 10 and v11_entry_m == 0:
            v11_entry_h, v11_entry_m = 15, 30
        gap_on = not getattr(args, 'no_gap_filter', False)
        breadth_on = not getattr(args, 'no_breadth_filter', False)
        return cls(symbols,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour,
                   rs_close_hour=getattr(args, 'rs_close_hour', 15),
                   rs_close_minute=getattr(args, 'rs_close_minute', 35),
                   overnight_top_k=getattr(args, 'top_k', 4),
                   overnight_bottom_k=getattr(args, 'bottom_k', 4),
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_min_move=args.momentum_threshold,
                   overnight_entry_hour=v11_entry_h,
                   overnight_entry_minute=v11_entry_m,
                   overnight_exit_after_min=args.exit_after_min,
                   global_signal_symbol=getattr(args, 'global_signal', 'VGK'),
                   global_min_return=getattr(args, 'global_min_return', 0.0),
                   tier2_top_k=getattr(args, 'tier2_top_k', 2),
                   tier2_bottom_k=getattr(args, 'tier2_bottom_k', 2),
                   gap_filter=gap_on,
                   gap_fade_pct=getattr(args, 'gap_fade_pct', 2.0),
                   use_daily_ema=getattr(args, 'use_daily_ema', False),
                   daily_ema_period=getattr(args, 'daily_ema_period', 20),
                   breadth_filter=breadth_on,
                   breadth_min_pct=getattr(args, 'breadth_min_pct', 45.0),
                   use_overnight_beta=getattr(args, 'use_overnight_beta', True)), {
            "rs_threshold": args.rs_threshold,
            "spy_trend_days": args.spy_trend_days,
            "overnight_top_k": getattr(args, 'top_k', 4),
            "overnight_bottom_k": getattr(args, 'bottom_k', 4),
            "rs_close_minute": getattr(args, 'rs_close_minute', 35),
            "exit_after_min": args.exit_after_min,
            "gap_filter": gap_on,
            "gap_fade_pct": getattr(args, 'gap_fade_pct', 2.0),
            "use_daily_ema": getattr(args, 'use_daily_ema', False),
            "breadth_filter": breadth_on,
            "breadth_min_pct": getattr(args, 'breadth_min_pct', 45.0),
            "use_overnight_beta": getattr(args, 'use_overnight_beta', True),
        }
    elif strategy_id == "high_conviction":
        hc_entry_h = getattr(args, 'itm_entry_hour', 15)
        hc_entry_m = getattr(args, 'itm_entry_minute', 30)
        if hc_entry_h == 10 and hc_entry_m == 0:
            hc_entry_h, hc_entry_m = 15, 30
        return cls(symbols,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=max(args.entry_after_min, 30),
                   rs_entry_end_hour=args.entry_end_hour,
                   rs_close_hour=getattr(args, 'rs_close_hour', 15),
                   rs_close_minute=getattr(args, 'rs_close_minute', 35),
                   require_stock_below_vwap=True,
                   rs_rvol_min=getattr(args, 'rvol_min', 1.5),
                   spy_min_drop_pct=0.2,
                   overnight_top_k=getattr(args, 'top_k', 5),
                   overnight_bottom_k=getattr(args, 'bottom_k', 3),
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_min_move=args.momentum_threshold,
                   overnight_entry_hour=hc_entry_h,
                   overnight_entry_minute=hc_entry_m,
                   overnight_exit_after_min=args.exit_after_min,
                   spy_min_rise_pct=0.1,
                   on_rvol_min=getattr(args, 'rvol_min', 1.0),
                   require_5d_momentum=True,
                   global_signal_symbol=getattr(args, 'global_signal', 'VGK'),
                   global_min_return=getattr(args, 'global_min_return', 0.0),
                   tier2_top_k=getattr(args, 'tier2_top_k', 2),
                   tier2_bottom_k=getattr(args, 'tier2_bottom_k', 2)), {
            "rs_threshold": args.rs_threshold,
            "rs_stop_pct": args.stop_pct,
            "rs_target_pct": args.profit_target_pct,
            "rs_rvol_min": getattr(args, 'rvol_min', 1.5),
            "on_rvol_min": getattr(args, 'rvol_min', 1.0),
            "require_stock_vwap": True,
            "require_5d_momentum": True,
            "exit_after_min": args.exit_after_min,
        }
    elif strategy_id == "cross_momentum":
        cm_entry_h = getattr(args, 'itm_entry_hour', 15)
        cm_entry_m = getattr(args, 'itm_entry_minute', 30)
        if cm_entry_h == 10 and cm_entry_m == 0:
            cm_entry_h, cm_entry_m = 15, 30
        return cls(symbols,
                   momentum_days=getattr(args, 'spy_trend_days', 5),
                   long_k=getattr(args, 'top_k', 5),
                   short_k=getattr(args, 'bottom_k', 5),
                   overnight_stop_pct=args.overnight_stop_pct,
                   entry_hour=cm_entry_h,
                   entry_minute=cm_entry_m,
                   exit_after_min=args.exit_after_min,
                   use_intraday_rs=True,
                   rs_weight=0.3), {
            "momentum_days": getattr(args, 'spy_trend_days', 5),
            "long_k": getattr(args, 'top_k', 5),
            "short_k": getattr(args, 'bottom_k', 5),
            "exit_after_min": args.exit_after_min,
        }
    elif strategy_id == "boosted_v10":
        bv_entry_h = getattr(args, 'itm_entry_hour', 15)
        bv_entry_m = getattr(args, 'itm_entry_minute', 30)
        if bv_entry_h == 10 and bv_entry_m == 0:
            bv_entry_h, bv_entry_m = 15, 30
        return cls(symbols,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour,
                   rs_close_hour=getattr(args, 'rs_close_hour', 15),
                   rs_close_minute=getattr(args, 'rs_close_minute', 35),
                   overnight_top_k=getattr(args, 'top_k', 4),
                   overnight_bottom_k=getattr(args, 'bottom_k', 4),
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_min_move=args.momentum_threshold,
                   overnight_entry_hour=bv_entry_h,
                   overnight_entry_minute=bv_entry_m,
                   overnight_exit_after_min=args.exit_after_min,
                   global_signal_symbol=getattr(args, 'global_signal', 'VGK'),
                   global_min_return=getattr(args, 'global_min_return', 0.0),
                   tier2_top_k=getattr(args, 'tier2_top_k', 2),
                   tier2_bottom_k=getattr(args, 'tier2_bottom_k', 2)), {
            "rs_threshold": args.rs_threshold,
            "rs_stop_pct": args.stop_pct,
            "rs_target_pct": args.profit_target_pct,
            "exit_after_min": args.exit_after_min,
            "boost_type": "rvol+range+mom+overnight",
        }
    elif strategy_id == "modular":
        mod_entry_h = getattr(args, 'itm_entry_hour', 15)
        mod_entry_m = getattr(args, 'itm_entry_minute', 30)
        if mod_entry_h == 10 and mod_entry_m == 0:
            mod_entry_h, mod_entry_m = 15, 30
        sel_type = getattr(args, 'selector', 'composite')
        return cls(symbols,
                   selector_type=sel_type,
                   select_top_n=getattr(args, 'top_k', 12),
                   select_after_min=30,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=max(args.entry_after_min, 30),
                   rs_entry_end_hour=args.entry_end_hour,
                   rs_close_hour=getattr(args, 'rs_close_hour', 15),
                   rs_close_minute=getattr(args, 'rs_close_minute', 35),
                   overnight_top_k=4,
                   overnight_bottom_k=4,
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_min_move=args.momentum_threshold,
                   overnight_entry_hour=mod_entry_h,
                   overnight_entry_minute=mod_entry_m,
                   overnight_exit_after_min=args.exit_after_min,
                   global_signal_symbol=getattr(args, 'global_signal', 'VGK')), {
            "selector": sel_type,
            "select_top_n": getattr(args, 'top_k', 12),
            "rs_stop_pct": args.stop_pct,
            "rs_target_pct": args.profit_target_pct,
            "exit_after_min": args.exit_after_min,
        }
    elif strategy_id == "gapper_momentum":
        return cls(symbols,
                   min_gap_pct=args.min_gap_pct,
                   max_gap_pct=args.max_gap_pct,
                   confirm_after_min=args.entry_after_min if args.entry_after_min != 15 else 30,
                   max_positions=getattr(args, 'top_k', 6),
                   stop_buffer_pct=getattr(args, 'stop_buffer_pct', 0.2),
                   target_mult=getattr(args, 'breakout_rr', 2.0),
                   max_stop_pct=getattr(args, 'max_stop_pct_pdl', 3.0),
                   exit_hour=15, exit_minute=25,
                   entry_end_hour=args.entry_end_hour,
                   direction=getattr(args, 'gap_direction', 'both'),
                   use_spy_filter=not args.no_regime_filter), {
            "min_gap_pct": args.min_gap_pct,
            "max_gap_pct": args.max_gap_pct,
            "max_positions": getattr(args, 'top_k', 6),
            "target_mult": getattr(args, 'breakout_rr', 2.0),
            "direction": getattr(args, 'gap_direction', 'both'),
            "use_spy_filter": not args.no_regime_filter,
        }
    elif strategy_id == "dynamic_select":
        ds_entry_h = getattr(args, 'itm_entry_hour', 15)
        ds_entry_m = getattr(args, 'itm_entry_minute', 30)
        if ds_entry_h == 10 and ds_entry_m == 0:
            ds_entry_h, ds_entry_m = 15, 30
        return cls(symbols,
                   selection_after_min=30,
                   min_rvol=getattr(args, 'rvol_min', 1.0),
                   max_selected=getattr(args, 'top_k', 10),
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=max(args.entry_after_min, 30),
                   rs_entry_end_hour=args.entry_end_hour,
                   rs_close_hour=getattr(args, 'rs_close_hour', 15),
                   rs_close_minute=getattr(args, 'rs_close_minute', 35),
                   overnight_top_k=getattr(args, 'top_k', 4),
                   overnight_bottom_k=getattr(args, 'bottom_k', 4),
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_min_move=args.momentum_threshold,
                   overnight_entry_hour=ds_entry_h,
                   overnight_entry_minute=ds_entry_m,
                   overnight_exit_after_min=args.exit_after_min,
                   global_signal_symbol=getattr(args, 'global_signal', 'VGK'),
                   global_min_return=getattr(args, 'global_min_return', 0.0),
                   tier2_top_k=getattr(args, 'tier2_top_k', 2),
                   tier2_bottom_k=getattr(args, 'tier2_bottom_k', 2)), {
            "min_rvol": getattr(args, 'rvol_min', 1.0),
            "max_selected": getattr(args, 'top_k', 10),
            "rs_threshold": args.rs_threshold,
            "rs_stop_pct": args.stop_pct,
            "rs_target_pct": args.profit_target_pct,
            "overnight_exit_after_min": args.exit_after_min,
        }
    elif strategy_id == "trend_regime":
        tr_entry_h = getattr(args, 'itm_entry_hour', 15)
        tr_entry_m = getattr(args, 'itm_entry_minute', 30)
        if tr_entry_h == 10 and tr_entry_m == 0:
            tr_entry_h, tr_entry_m = 15, 30
        return cls(symbols,
                   sma_period=getattr(args, 'sma_bull_period', 200),
                   buffer_pct=0.0,
                   confirm_days=getattr(args, 'spy_trend_days', 3),
                   bull_top_k=getattr(args, 'top_k', 4),
                   bull_bottom_k=getattr(args, 'bottom_k', 4),
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_min_move=args.momentum_threshold,
                   overnight_entry_hour=tr_entry_h,
                   overnight_entry_minute=tr_entry_m,
                   overnight_exit_after_min=args.exit_after_min,
                   bear_rs_enabled=True,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour,
                   rs_close_hour=getattr(args, 'rs_close_hour', 15),
                   rs_close_minute=getattr(args, 'rs_close_minute', 35),
                   global_signal_symbol=getattr(args, 'global_signal', 'VGK'),
                   global_min_return=getattr(args, 'global_min_return', 0.0),
                   tier2_top_k=getattr(args, 'tier2_top_k', 2),
                   tier2_bottom_k=getattr(args, 'tier2_bottom_k', 2)), {
            "sma_period": getattr(args, 'sma_bull_period', 200),
            "confirm_days": getattr(args, 'spy_trend_days', 3),
            "bull_top_k": getattr(args, 'top_k', 4),
            "bull_bottom_k": getattr(args, 'bottom_k', 4),
            "bear_rs_enabled": True,
            "rs_threshold": args.rs_threshold,
            "rs_stop_pct": args.stop_pct,
            "rs_target_pct": args.profit_target_pct,
            "overnight_exit_after_min": args.exit_after_min,
        }
    elif strategy_id == "gap_context":
        return cls(symbols,
                   min_gap_pct=args.min_gap_pct if args.min_gap_pct != 0.3 else 0.3,
                   check_after_min=args.entry_after_min if args.entry_after_min != 15 else 30,
                   entry_end_hour=args.entry_end_hour,
                   stop_buffer_pct=getattr(args, 'stop_buffer_pct', 0.15),
                   target_mult=getattr(args, 'breakout_rr', 2.0),
                   max_stop_pct=getattr(args, 'max_stop_pct_pdl', 1.5),
                   mode=getattr(args, 'pdl_mode', 'all'),
                   require_spy_alignment=not args.no_regime_filter), {
            "min_gap_pct": args.min_gap_pct if args.min_gap_pct != 0.3 else 0.3,
            "check_after_min": args.entry_after_min if args.entry_after_min != 15 else 30,
            "target_mult": getattr(args, 'breakout_rr', 2.0),
            "mode": getattr(args, 'pdl_mode', 'all'),
            "require_spy_alignment": not args.no_regime_filter,
        }
    elif strategy_id == "closing_momentum":
        cm_entry_h = getattr(args, 'itm_entry_hour', 15)
        cm_entry_m = getattr(args, 'itm_entry_minute', 30)
        if cm_entry_h == 10 and cm_entry_m == 0:
            cm_entry_h, cm_entry_m = 15, 30
        return cls(symbols,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour,
                   rs_close_hour=getattr(args, 'rs_close_hour', 15),
                   rs_close_minute=getattr(args, 'rs_close_minute', 35),
                   close_lookback_min=15,
                   overnight_top_k=getattr(args, 'top_k', 4),
                   overnight_bottom_k=getattr(args, 'bottom_k', 4),
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_min_close_move=0.1,
                   overnight_entry_hour=cm_entry_h,
                   overnight_entry_minute=cm_entry_m,
                   overnight_exit_after_min=args.exit_after_min,
                   global_signal_symbol=getattr(args, 'global_signal', 'VGK'),
                   global_min_return=getattr(args, 'global_min_return', 0.0),
                   tier2_top_k=getattr(args, 'tier2_top_k', 2),
                   tier2_bottom_k=getattr(args, 'tier2_bottom_k', 2)), {
            "close_lookback_min": 15,
            "overnight_top_k": getattr(args, 'top_k', 4),
            "overnight_bottom_k": getattr(args, 'bottom_k', 4),
            "rs_threshold": args.rs_threshold,
            "rs_target_pct": args.profit_target_pct,
            "exit_after_min": args.exit_after_min,
        }
    elif strategy_id == "spy_reversion":
        return cls(symbols,
                   dip_threshold=getattr(args, 'momentum_threshold', 0.5),
                   check_after_min=args.entry_after_min if args.entry_after_min != 15 else 60,
                   check_end_hour=args.entry_end_hour,
                   stop_mult=getattr(args, 'stop_mult', 1.5),
                   trade_spy=True,
                   trade_qqq=True,
                   trade_stocks=False,
                   direction="long_only",
                   require_below_vwap=not args.no_regime_filter), {
            "dip_threshold": getattr(args, 'momentum_threshold', 0.5),
            "check_after_min": args.entry_after_min if args.entry_after_min != 15 else 60,
            "direction": "long_only",
            "require_below_vwap": not args.no_regime_filter,
        }
    elif strategy_id == "prior_day_levels":
        return cls(symbols,
                   entry_after_min=args.entry_after_min,
                   entry_end_hour=args.entry_end_hour,
                   approach_pct=getattr(args, 'approach_pct', 0.1),
                   breakout_confirm_pct=getattr(args, 'breakout_confirm_pct', 0.05),
                   breakout_rr=getattr(args, 'breakout_rr', 1.5),
                   rejection_fail_pct=getattr(args, 'rejection_fail_pct', 0.15),
                   bounce_confirm_pct=getattr(args, 'bounce_confirm_pct', 0.15),
                   stop_pct=args.stop_pct,
                   max_stop_pct=getattr(args, 'max_stop_pct_pdl', 1.5),
                   mode=getattr(args, 'pdl_mode', 'all'),
                   regime_filter=not args.no_regime_filter), {
            "mode": getattr(args, 'pdl_mode', 'all'),
            "approach_pct": getattr(args, 'approach_pct', 0.1),
            "breakout_confirm_pct": getattr(args, 'breakout_confirm_pct', 0.05),
            "breakout_rr": getattr(args, 'breakout_rr', 1.5),
            "rejection_fail_pct": getattr(args, 'rejection_fail_pct', 0.15),
            "stop_pct": args.stop_pct,
            "regime_filter": not args.no_regime_filter,
        }
    elif strategy_id == "allweather_v10":
        v10_entry_h = getattr(args, 'itm_entry_hour', 15)
        v10_entry_m = getattr(args, 'itm_entry_minute', 30)
        if v10_entry_h == 10 and v10_entry_m == 0:
            v10_entry_h, v10_entry_m = 15, 30
        return cls(symbols,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour,
                   rs_close_hour=getattr(args, 'rs_close_hour', 15),
                   rs_close_minute=getattr(args, 'rs_close_minute', 35),
                   overnight_top_k=getattr(args, 'top_k', 4),
                   overnight_bottom_k=getattr(args, 'bottom_k', 4),
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_min_move=args.momentum_threshold,
                   overnight_entry_hour=v10_entry_h,
                   overnight_entry_minute=v10_entry_m,
                   overnight_exit_after_min=args.exit_after_min,
                   global_signal_symbol=getattr(args, 'global_signal', 'VGK'),
                   global_min_return=getattr(args, 'global_min_return', 0.0),
                   tier2_top_k=getattr(args, 'tier2_top_k', 2),
                   tier2_bottom_k=getattr(args, 'tier2_bottom_k', 2)), {
            "rs_threshold": args.rs_threshold,
            "spy_trend_days": args.spy_trend_days,
            "rs_close_hour": getattr(args, 'rs_close_hour', 15),
            "rs_close_minute": getattr(args, 'rs_close_minute', 35),
            "overnight_top_k": getattr(args, 'top_k', 4),
            "overnight_bottom_k": getattr(args, 'bottom_k', 4),
            "overnight_stop_pct": args.overnight_stop_pct,
            "global_signal": getattr(args, 'global_signal', 'VGK'),
            "tier2_top_k": getattr(args, 'tier2_top_k', 2),
            "tier2_bottom_k": getattr(args, 'tier2_bottom_k', 2),
        }
    elif strategy_id == "allweather_v9":
        v9_entry_h = getattr(args, 'itm_entry_hour', 15)
        v9_entry_m = getattr(args, 'itm_entry_minute', 30)
        if v9_entry_h == 10 and v9_entry_m == 0:
            v9_entry_h, v9_entry_m = 15, 30
        return cls(symbols,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour,
                   tom_top_k=getattr(args, 'tom_top_k', 5),
                   tom_bottom_k=getattr(args, 'tom_bottom_k', 5),
                   base_top_k=getattr(args, 'base_top_k', 1),
                   base_bottom_k=getattr(args, 'base_bottom_k', 1),
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_min_move=args.momentum_threshold,
                   overnight_entry_hour=v9_entry_h,
                   overnight_entry_minute=v9_entry_m,
                   overnight_exit_after_min=args.exit_after_min,
                   global_signal_symbol=getattr(args, 'global_signal', 'VGK'),
                   global_min_return=getattr(args, 'global_min_return', 0.0),
                   prefer_high_beta_tom=getattr(args, 'prefer_high_beta_tom', True)), {
            "rs_threshold": args.rs_threshold,
            "spy_trend_days": args.spy_trend_days,
            "tom_top_k": getattr(args, 'tom_top_k', 5),
            "tom_bottom_k": getattr(args, 'tom_bottom_k', 5),
            "base_top_k": getattr(args, 'base_top_k', 1),
            "base_bottom_k": getattr(args, 'base_bottom_k', 1),
            "overnight_stop_pct": args.overnight_stop_pct,
            "global_signal": getattr(args, 'global_signal', 'VGK'),
        }
    elif strategy_id == "allweather_v8":
        v8_entry_h = getattr(args, 'itm_entry_hour', 15)
        v8_entry_m = getattr(args, 'itm_entry_minute', 30)
        if v8_entry_h == 10 and v8_entry_m == 0:
            v8_entry_h, v8_entry_m = 15, 30
        return cls(symbols,
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour,
                   overnight_top_k=getattr(args, 'top_k', 3),
                   overnight_bottom_k=getattr(args, 'bottom_k', 3),
                   overnight_stop_pct=args.overnight_stop_pct,
                   overnight_min_move=args.momentum_threshold,
                   overnight_entry_hour=v8_entry_h,
                   overnight_entry_minute=v8_entry_m,
                   loser_exit_min=getattr(args, 'loser_exit_min', 15),
                   winner_hold_until_hour=getattr(args, 'winner_hold_hour', 15),
                   winner_hold_until_min=getattr(args, 'winner_hold_min', 25),
                   multiday_extend=getattr(args, 'multiday_extend', False),
                   max_extend_days=getattr(args, 'max_extend_days', 3),
                   extend_stop_pct=getattr(args, 'extend_stop_pct', 3.0),
                   global_signal_symbol=getattr(args, 'global_signal', 'VGK'),
                   tier2_top_k=getattr(args, 'tier2_top_k', 1),
                   tier2_bottom_k=getattr(args, 'tier2_bottom_k', 1)), {
            "rs_threshold": args.rs_threshold,
            "spy_trend_days": args.spy_trend_days,
            "overnight_top_k": getattr(args, 'top_k', 3),
            "overnight_bottom_k": getattr(args, 'bottom_k', 3),
            "overnight_stop_pct": args.overnight_stop_pct,
            "loser_exit_min": getattr(args, 'loser_exit_min', 15),
            "winner_hold_hour": getattr(args, 'winner_hold_hour', 15),
            "winner_hold_min": getattr(args, 'winner_hold_min', 25),
            "multiday_extend": getattr(args, 'multiday_extend', False),
            "max_extend_days": getattr(args, 'max_extend_days', 3),
            "global_signal": getattr(args, 'global_signal', 'VGK'),
        }
    elif strategy_id == "allweather_v7":
        v7_entry_h = getattr(args, 'itm_entry_hour', 15)
        v7_entry_m = getattr(args, 'itm_entry_minute', 30)
        if v7_entry_h == 10 and v7_entry_m == 0:
            v7_entry_h, v7_entry_m = 15, 30
        return cls(symbols,
                   sma_period=getattr(args, 'sma_bull_period', 10),
                   spy_trend_days=args.spy_trend_days,
                   long_max_positions=getattr(args, 'long_max_positions', 8),
                   rebalance_daily=getattr(args, 'rebalance_daily', True),
                   catastrophe_stop_pct=getattr(args, 'catastrophe_stop_pct', 15.0),
                   entry_hour=v7_entry_h,
                   entry_minute=v7_entry_m,
                   exit_morning_min=getattr(args, 'exit_morning_min', 15),
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour), {
            "sma_period": getattr(args, 'sma_bull_period', 10),
            "spy_trend_days": args.spy_trend_days,
            "long_max_positions": getattr(args, 'long_max_positions', 8),
            "catastrophe_stop_pct": getattr(args, 'catastrophe_stop_pct', 15.0),
            "rs_threshold": args.rs_threshold,
        }
    elif strategy_id == "allweather_v6":
        # v6 entry defaults to 15:30, not the ITM default of 10:00
        v6_entry_h = getattr(args, 'itm_entry_hour', 15)
        v6_entry_m = getattr(args, 'itm_entry_minute', 30)
        # If user didn't explicitly set entry time, use 15:30 for v6
        if v6_entry_h == 10 and v6_entry_m == 0:
            v6_entry_h, v6_entry_m = 15, 30
        return cls(symbols,
                   sma_period=getattr(args, 'sma_bull_period', 5),
                   long_top_k=getattr(args, 'long_top_k', 3),
                   long_bottom_k=getattr(args, 'long_bottom_k', 3),
                   trail_stop_pct=getattr(args, 'trail_stop_pct', 3.0),
                   max_hold_days=getattr(args, 'max_hold_days', 15),
                   min_rs_entry=getattr(args, 'min_rs_entry', 0.3),
                   entry_hour=v6_entry_h,
                   entry_minute=v6_entry_m,
                   exit_morning_min=getattr(args, 'exit_morning_min', 15),
                   rs_threshold=args.rs_threshold,
                   rs_stop_pct=args.stop_pct,
                   rs_target_pct=args.profit_target_pct,
                   spy_trend_days=args.spy_trend_days,
                   rs_entry_after_min=args.entry_after_min,
                   rs_entry_end_hour=args.entry_end_hour), {
            "sma_period": getattr(args, 'sma_bull_period', 5),
            "long_top_k": getattr(args, 'long_top_k', 3),
            "long_bottom_k": getattr(args, 'long_bottom_k', 3),
            "trail_stop_pct": getattr(args, 'trail_stop_pct', 3.0),
            "max_hold_days": getattr(args, 'max_hold_days', 15),
            "min_rs_entry": getattr(args, 'min_rs_entry', 0.3),
            "exit_morning_min": getattr(args, 'exit_morning_min', 15),
            "rs_threshold": args.rs_threshold,
            "spy_trend_days": args.spy_trend_days,
        }
    return cls(symbols), {}


def write_report(slug: str, data: dict) -> Path:
    path = ROOT / "experiments" / "reports" / f"{slug}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)
    return path


def write_run_note(slug: str, data: dict) -> Path:
    """Create a pre-filled markdown run note. Claude fills in qualitative sections.
    Does NOT overwrite an existing note so that manual edits are preserved."""
    path = ROOT / "experiments" / "runs" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path  # preserve manually-edited notes
    m = data.get("metrics", {})
    x = data.get("extended_metrics", {})
    meta = data.get("metadata", {})
    rules = data.get("rules", [])

    lines = [
        f"# Run {slug}",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d')}",
        f"**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising",
        "",
        "---",
        "",
        "## Hypothesis",
        "",
        "> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_",
        "",
        "## Strategy Rules",
        "",
    ]
    for rule in rules:
        lines.append(f"- {rule}")
    lines += [
        "",
        "## Backtest Configuration",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Symbols | {', '.join(meta.get('symbols', []))} |",
        f"| Date range | {meta.get('start','')[:10]} → {meta.get('end','')[:10]} |",
        f"| Interval | {meta.get('interval','')} |",
        f"| Leverage | {meta.get('leverage', 1.0)}× |",
        f"| Data source | {meta.get('data_source','')} |",
        f"| Initial cash | ${meta.get('initial_cash', 100000):,.0f} |",
    ]
    params = meta.get("params", {})
    for k, v in params.items():
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "## Backtest Results",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total return | {m.get('total_return_pct', '')}% |",
        f"| Monthly return | {m.get('monthly_return_pct', '')}% |",
        f"| Sharpe ratio | {m.get('sharpe_ratio', '')} |",
        f"| Max drawdown | {m.get('max_drawdown_pct', '')}% |",
        f"| Fills | {m.get('fills', '')} |",
        f"| Round trips | {x.get('round_trips', '')} |",
        f"| Win rate | {x.get('win_rate_pct', '')}% |",
        f"| Profit factor | {x.get('profit_factor', '')} |",
        f"| Expectancy | ${x.get('expectancy', '')} |",
        f"| Max consec losses | {x.get('max_consecutive_losses', '')} |",
        f"| Final equity | ${m.get('final_equity', ''):,.2f} |",
        "",
        "## Evaluation",
        "",
        "Score against candidate criteria:",
        "",
        f"- [ ] Total return positive",
        f"- [ ] Monthly return ≥ 5% (target)",
        f"- [ ] Sharpe ≥ 0.5 (daily annualised)",
        f"- [ ] Max drawdown ≤ 25%",
        f"- [ ] Win rate ≥ 40%",
        f"- [ ] Profit factor ≥ 1.5",
        f"- [ ] Round trips ≥ 15",
        f"- [ ] All trades intraday (no overnight holds)",
        f"- [ ] Tested on ≥ 2 symbols",
        "",
        "Observations:",
        "",
        "> _Fill in: What worked, what didn't, surprising findings._",
        "",
        "## Decision",
        "",
        "**[ ] Reject** — reason:  ",
        "**[ ] Revise** — what to change:  ",
        "**[ ] Mark as promising** — justification:  ",
        "",
        "## Next Step",
        "",
        "> _Fill in: What to test next._",
    ]

    path.write_text("\n".join(lines))
    return path


def update_status(slug: str, strategy_label: str, m: dict, status: str) -> None:
    path = ROOT / "experiments" / "STATUS.md"
    content = f"""# Experiment Status

> Auto-updated by run_experiment.py after each run. Edit the Decision section manually.

## Current Run

- **Slug:** {slug}
- **Strategy:** {strategy_label}
- **Status:** {status}
- **Total return:** {m.get('total_return_pct', '?')}%
- **Monthly return:** {m.get('monthly_return_pct', '?')}%
- **Sharpe:** {m.get('sharpe_ratio', '?')}
- **Max drawdown:** {m.get('max_drawdown_pct', '?')}%

## Next Action

> Fill in after evaluating the run note.
"""
    path.write_text(content)


HIST_START = "2025-01-02"   # historical validation window (full 2025; 01-02 = first trading day)
HIST_END   = "2025-12-31"


def main() -> None:
    args = build_arg_parser().parse_args()

    symbols = list(args.symbols) if args.symbols else list(DEFAULT_UNIVERSE)

    # Auto-assign slug if not provided
    if args.slug is None:
        n = next_run_number()
        args.slug = f"{n:03d}_{args.strategy}"

    print(f"\n{'='*50}")
    print(f"  Experiment: {args.slug}")
    print(f"  Strategy:   {args.strategy}")
    print(f"  Symbols:    {' '.join(symbols)}")
    print(f"  Window:     {args.start} → {args.end}")
    print(f"  Interval:   {args.interval}")
    print(f"{'='*50}\n")

    config = Config()
    config.risk.max_position_pct = args.max_position_pct
    if args.data_source == "alpaca":
        try:
            config.alpaca.validate()
        except ValueError as e:
            print(f"ERROR: {e}")
            sys.exit(1)

    strategy, params = make_strategy(args.strategy, symbols, args)
    engine = BacktestEngine(config, leverage=args.leverage, eod_flatten=not args.no_eod_flatten)

    hist_strategy, _ = make_strategy(args.strategy, symbols, args)   # fresh instance for historical
    hist_engine = BacktestEngine(config, leverage=args.leverage, eod_flatten=not args.no_eod_flatten)

    # ── Phase 1: load both data windows in parallel (I/O bound) ─────────────
    logger.info("── Phase 1/3: loading data for both windows in parallel ──")
    t0 = time.time()
    primary_start = datetime.fromisoformat(args.start)
    primary_end   = datetime.fromisoformat(args.end)
    hist_start    = datetime.fromisoformat(HIST_START)
    hist_end      = datetime.fromisoformat(HIST_END)

    with ThreadPoolExecutor(max_workers=2) as pool:
        primary_dfs_fut = pool.submit(
            engine.load_data, symbols, primary_start, primary_end,
            args.data_source, args.interval)
        hist_dfs_fut = pool.submit(
            hist_engine.load_data, symbols, hist_start, hist_end,
            args.data_source, args.interval)
        primary_dfs = primary_dfs_fut.result()
        hist_dfs    = hist_dfs_fut.result()
    logger.info("── Phase 1/3 done in %.1fs ──", time.time() - t0)

    # ── Phase 2: run both bar loops in parallel processes (true CPU parallelism) ──
    logger.info("── Phase 2/3: running primary + historical bar loops (multiprocessing) ──")
    t0 = time.time()

    ctx = mp.get_context("fork")   # fork: child inherits DataFrames via copy-on-write
    q_primary = ctx.Queue()
    q_hist    = ctx.Queue()

    def _primary_worker():
        try:
            r = engine.run(strategy=strategy, symbols=symbols,
                           start=primary_start, end=primary_end,
                           data_source=args.data_source, interval=args.interval,
                           params=params, symbol_dfs=primary_dfs)
            q_primary.put({"ok": True, "data": r.to_dict(slug=args.slug, status=args.status)})
        except Exception as e:
            q_primary.put({"ok": False, "error": str(e), "traceback": _tb.format_exc()})

    def _hist_worker():
        try:
            r = hist_engine.run(strategy=hist_strategy, symbols=symbols,
                                start=hist_start, end=hist_end,
                                data_source=args.data_source, interval=args.interval,
                                params=params, symbol_dfs=hist_dfs)
            q_hist.put({"ok": True, "data": {
                "metrics":            r.metrics(),
                "extended_metrics":   r.extended_metrics(),
                "per_symbol_metrics": r.per_symbol_metrics(),
                "calendar":           r.calendar(),
                "buy_and_hold":       r.metadata.get("buy_and_hold", {}),
            }})
        except Exception as e:
            q_hist.put({"ok": False, "error": str(e), "traceback": _tb.format_exc()})

    def _get_or_die(q, proc, label):
        """Poll queue with timeout; raise immediately if worker process died."""
        while True:
            try:
                return q.get(timeout=3)
            except _queue.Empty:
                if not proc.is_alive():
                    raise RuntimeError(
                        f"{label} worker (pid {proc.pid}) exited with code "
                        f"{proc.exitcode} before returning a result"
                    )

    p1 = ctx.Process(target=_primary_worker)
    p2 = ctx.Process(target=_hist_worker)
    p1.start()
    p2.start()
    primary_msg = _get_or_die(q_primary, p1, "primary")
    hist_msg    = _get_or_die(q_hist,    p2, "historical")
    p1.join()
    p2.join()
    logger.info("── Phase 2/3 done in %.1fs ──", time.time() - t0)

    if not primary_msg["ok"]:
        logger.error("Primary backtest crashed:\n%s", primary_msg["traceback"])
        sys.exit(1)
    if not hist_msg["ok"]:
        logger.error("Historical backtest crashed:\n%s", hist_msg["traceback"])
        sys.exit(1)

    # ── Phase 3: write report (metrics already computed in child processes) ───
    logger.info("── Phase 3/3: writing report ──")
    t0 = time.time()
    data     = primary_msg["data"]
    hist_raw = hist_msg["data"]
    m = data["metrics"]
    x = data["extended_metrics"]
    data["historical"] = {
        "window":             f"{HIST_START} / {HIST_END}",
        "metrics":            hist_raw["metrics"],
        "extended_metrics":   hist_raw["extended_metrics"],
        "per_symbol_metrics": hist_raw["per_symbol_metrics"],
        "calendar":           hist_raw["calendar"],
        "buy_and_hold":       hist_raw["buy_and_hold"],
        # transactions omitted — a full year is too large to store in the report
    }
    hm = data["historical"]["metrics"]
    hx = data["historical"]["extended_metrics"]

    report_path = write_report(args.slug, data)
    note_path = write_run_note(args.slug, data)
    update_status(
        args.slug,
        data["metadata"].get("strategy_label", args.strategy),
        m,
        args.status,
    )
    logger.info("── Phase 3/3 done in %.1fs ──", time.time() - t0)

    # Print summary
    print(f"\n{'='*50}")
    print(f"  Results: {args.slug}  [primary]")
    print(f"{'='*50}")
    print(f"  Total return:    {m.get('total_return_pct', '?'):>8}%")
    print(f"  Monthly return:  {m.get('monthly_return_pct', '?'):>8}%")
    print(f"  Sharpe:          {m.get('sharpe_ratio', '?'):>8}")
    print(f"  Max drawdown:    {m.get('max_drawdown_pct', '?'):>8}%")
    print(f"  Fills:           {m.get('fills', '?'):>8}")
    print(f"  Round trips:     {x.get('round_trips', '?'):>8}")
    print(f"  Win rate:        {str(x.get('win_rate_pct', '?')):>7}%")
    print(f"  Profit factor:   {x.get('profit_factor', '?'):>8}")
    print(f"  Expectancy:      ${x.get('expectancy', '?'):>7}")
    print(f"{'='*50}")
    print(f"  Historical 2025: {args.slug}")
    print(f"{'='*50}")
    print(f"  Total return:    {hm.get('total_return_pct', '?'):>8}%")
    print(f"  Monthly return:  {hm.get('monthly_return_pct', '?'):>8}%")
    print(f"  Sharpe:          {hm.get('sharpe_ratio', '?'):>8}")
    print(f"  Max drawdown:    {hm.get('max_drawdown_pct', '?'):>8}%")
    print(f"  Win rate:        {str(hx.get('win_rate_pct', '?')):>7}%")
    print(f"  Profit factor:   {hx.get('profit_factor', '?'):>8}")
    print(f"{'='*50}")

    print(f"\n  Report saved: {report_path.relative_to(ROOT)}")
    print(f"  Run note:     {note_path.relative_to(ROOT)}")
    print(f"  STATUS.md updated.")
    print(f"\n  Next: fill in hypothesis + decision in {note_path.name}")
    print(f"        then update --status and re-run to persist the decision.\n")


if __name__ == "__main__":
    main()
