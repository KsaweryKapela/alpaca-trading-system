#!/usr/bin/env python3
"""Experiment runner — Claude uses this to run strategy experiments.

Usage:
  .venv/bin/python run_experiment.py \\
    --strategy orb \\
    --slug 001_orb \\
    [--symbols SPY QQQ AAPL MSFT NVDA]  # default: full DEFAULT_UNIVERSE \\
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
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent

sys.path.insert(0, str(ROOT))
from trading.config import Config, EVAL_START, EVAL_END, DEFAULT_UNIVERSE
from trading.engine.backtest import BacktestEngine
from trading.strategy import STRATEGIES


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
    p.add_argument("--symbols", nargs="+", default=None,
                   help="Asset symbols to test (default: full DEFAULT_UNIVERSE from config)")
    p.add_argument("--slug", default=None, help="Run slug (auto-assigned if omitted)")
    p.add_argument("--start", default=EVAL_START, help="Start date YYYY-MM-DD")
    p.add_argument("--end", default=EVAL_END, help="End date YYYY-MM-DD")
    p.add_argument("--leverage", type=float, default=1.0)
    p.add_argument("--interval", default="1m", help="Bar interval (default 1m)")
    p.add_argument("--data-source", default="alpaca", choices=["alpaca", "yfinance"])
    p.add_argument("--status", default="in_progress",
                   choices=["in_progress", "rejected", "promising", "revised"],
                   help="Initial status to write into the report")

    # ORB params
    p.add_argument("--range-minutes", type=int, default=15)
    p.add_argument("--stop-pct", type=float, default=0.5)

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

    return p


def make_strategy(strategy_id: str, symbols, args):
    cls = STRATEGIES[strategy_id]
    if strategy_id == "orb":
        return cls(symbols, range_minutes=args.range_minutes, stop_pct=args.stop_pct), {
            "range_minutes": args.range_minutes,
            "stop_pct": args.stop_pct,
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


def main() -> None:
    args = build_arg_parser().parse_args()

    # Default symbols to full universe if not specified
    if args.symbols is None:
        args.symbols = list(DEFAULT_UNIVERSE)

    # Auto-assign slug if not provided
    if args.slug is None:
        n = next_run_number()
        args.slug = f"{n:03d}_{args.strategy}"

    print(f"\n{'='*50}")
    print(f"  Experiment: {args.slug}")
    print(f"  Strategy:   {args.strategy}")
    print(f"  Symbols:    {' '.join(args.symbols)}")
    print(f"  Window:     {args.start} → {args.end}")
    print(f"  Interval:   {args.interval}")
    print(f"{'='*50}\n")

    config = Config()
    if args.data_source == "alpaca":
        try:
            config.alpaca.validate()
        except ValueError as e:
            print(f"ERROR: {e}")
            sys.exit(1)

    strategy, params = make_strategy(args.strategy, args.symbols, args)
    engine = BacktestEngine(config, leverage=args.leverage, eod_flatten=True)

    result = engine.run(
        strategy=strategy,
        symbols=args.symbols,
        start=datetime.fromisoformat(args.start),
        end=datetime.fromisoformat(args.end),
        data_source=args.data_source,
        interval=args.interval,
        params=params,
    )

    data = result.to_dict(slug=args.slug, status=args.status)
    m = data["metrics"]
    x = data["extended_metrics"]

    # Print summary
    print(f"\n{'='*50}")
    print(f"  Results: {args.slug}")
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

    report_path = write_report(args.slug, data)
    note_path = write_run_note(args.slug, data)
    update_status(
        args.slug,
        data["metadata"].get("strategy_label", args.strategy),
        m,
        args.status,
    )

    print(f"\n  Report saved: {report_path.relative_to(ROOT)}")
    print(f"  Run note:     {note_path.relative_to(ROOT)}")
    print(f"  STATUS.md updated.")
    print(f"\n  Next: fill in hypothesis + decision in {note_path.name}")
    print(f"        then update --status and re-run to persist the decision.\n")


if __name__ == "__main__":
    main()
