# Run 228_gc_all

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Min gap: 0.3%
- Check gap behavior at 9:30+30min
- GAP-UP + HOLD (above prior close) → LONG
- GAP-UP + FAIL (below prior close) → SHORT
- GAP-DOWN + RECOVER (above prior close) → LONG
- GAP-DOWN + CONTINUE (below prior close) → SHORT
- Stop: prior close ± 0.1% | Target: 2.0× stop
- Mode: all
- Require SPY VWAP alignment

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-30 |
| Interval | 1m |
| Leverage | 3.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| min_gap_pct | 0.3 |
| check_after_min | 30 |
| target_mult | 2.0 |
| mode | all |
| require_spy_alignment | True |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -0.95% |
| Monthly return | -0.21% |
| Sharpe ratio | -0.28 |
| Max drawdown | -8.12% |
| Fills | 1306 |
| Round trips | 653 |
| Win rate | 40.4% |
| Profit factor | 0.97 |
| Expectancy | $-1.45 |
| Max consec losses | 15 |
| Final equity | $99,051.61 |

## Evaluation

Score against candidate criteria:

- [ ] Total return positive
- [ ] Monthly return ≥ 5% (target)
- [ ] Sharpe ≥ 0.5 (daily annualised)
- [ ] Max drawdown ≤ 25%
- [ ] Win rate ≥ 40%
- [ ] Profit factor ≥ 1.5
- [ ] Round trips ≥ 15
- [ ] All trades intraday (no overnight holds)
- [ ] Tested on ≥ 2 symbols

Observations:

> _Fill in: What worked, what didn't, surprising findings._

## Decision

**[ ] Reject** — reason:  
**[ ] Revise** — what to change:  
**[ ] Mark as promising** — justification:  

## Next Step

> _Fill in: What to test next._