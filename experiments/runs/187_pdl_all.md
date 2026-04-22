# Run 187_pdl_all

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Mode: all
- Entry: 30min after open → 14:00
- BREAKOUT: long when stock > PDH + 0.05% (bull regime)
- REJECTION: short when stock approaches PDH then falls 0.15% below (bear regime)
- BOUNCE: long when stock approaches PDL then rises 0.15% above (bull regime)
- Regime filter: ON

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-30 |
| Interval | 1m |
| Leverage | 3.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| mode | all |
| approach_pct | 0.1 |
| breakout_confirm_pct | 0.05 |
| breakout_rr | 1.5 |
| rejection_fail_pct | 0.15 |
| stop_pct | 0.8 |
| regime_filter | True |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -4.2% |
| Monthly return | -1.05% |
| Sharpe ratio | -2.66 |
| Max drawdown | -6.86% |
| Fills | 1158 |
| Round trips | 579 |
| Win rate | 34.9% |
| Profit factor | 0.74 |
| Expectancy | $-7.25 |
| Max consec losses | 11 |
| Final equity | $95,804.48 |

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