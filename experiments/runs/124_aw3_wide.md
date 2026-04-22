# Run 124_aw3_wide

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BEAR SLEEVE ===
- RS SHORT: SPY below VWAP + 3d trend filter
- RS < -1.0% | Stop 1.0% | TP 2.0%
- === BULL SLEEVE A (Overnight Momentum) ===
- At 15:30: buy top 5 by RS (winners)
- === BULL SLEEVE B (Overnight Reversal) ===
- At 15:30: buy bottom 5 by RS (dip buys)
- Overnight stop: 2.0% | Exit 5min after next open
- All overnight requires SPY above VWAP at entry

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 3.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| rs_threshold | 1.0 |
| rs_stop_pct | 1.0 |
| rs_target_pct | 2.0 |
| spy_trend_days | 3 |
| overnight_top_k | 5 |
| overnight_bottom_k | 5 |
| overnight_stop_pct | 2.0 |
| overnight_exit_after_min | 5 |
| overnight_min_move | 0.3 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 7.92% |
| Monthly return | 1.94% |
| Sharpe ratio | 3.1 |
| Max drawdown | -2.71% |
| Fills | 839 |
| Round trips | 417 |
| Win rate | 51.3% |
| Profit factor | 1.56 |
| Expectancy | $18.76 |
| Max consec losses | 9 |
| Final equity | $107,921.11 |

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