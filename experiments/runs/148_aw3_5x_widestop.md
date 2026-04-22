# Run 148_aw3_5x_widestop

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BEAR SLEEVE ===
- RS SHORT: SPY below VWAP + 3d trend filter
- RS < -1.0% | Stop 1.0% | TP 2.0%
- === BULL SLEEVE A (Overnight Momentum) ===
- At 15:30: buy top 3 by RS (winners)
- === BULL SLEEVE B (Overnight Reversal) ===
- At 15:30: buy bottom 3 by RS (dip buys)
- Overnight stop: 3.0% | Exit 15min after next open
- All overnight requires SPY above VWAP at entry

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 5.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| rs_threshold | 1.0 |
| rs_stop_pct | 1.0 |
| rs_target_pct | 2.0 |
| spy_trend_days | 3 |
| overnight_top_k | 3 |
| overnight_bottom_k | 3 |
| overnight_stop_pct | 3.0 |
| overnight_exit_after_min | 15 |
| overnight_min_move | 0.3 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 10.11% |
| Monthly return | 2.46% |
| Sharpe ratio | 3.32 |
| Max drawdown | -3.64% |
| Fills | 674 |
| Round trips | 336 |
| Win rate | 51.2% |
| Profit factor | 1.71 |
| Expectancy | $29.77 |
| Max consec losses | 12 |
| Final equity | $110,111.41 |

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