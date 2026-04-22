# Run 046_vwap_qqq_1m

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Track each stock's intraday VWAP (cumulative typical price × volume)
- Bullish session (SPY > VWAP AND SPY up >0.1% from open):
-   LONG entry: stock price crosses FROM BELOW to ABOVE its own VWAP
- Bearish session (SPY < VWAP AND SPY down >0.1% from open):
-   SHORT entry: stock price crosses FROM ABOVE to BELOW its own VWAP
- Stop loss: 0.5% from VWAP at entry
- Profit target: 1.0% from entry
- Direction: long_only
- Entry window: 9:45 ET → 12:00 ET
- One trade per symbol per day
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| stop_pct | 0.5 |
| profit_target_pct | 1.0 |
| direction | long_only |
| spy_min_move_pct | 0.1 |
| rs_confirm_pct | 0.0 |
| entry_end_hour | 12 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -0.12% |
| Monthly return | -0.03% |
| Sharpe ratio | -0.95 |
| Max drawdown | -0.33% |
| Fills | 54 |
| Round trips | 27 |
| Win rate | 40.7% |
| Profit factor | 0.8 |
| Expectancy | $-4.52 |
| Max consec losses | 5 |
| Final equity | $99,877.84 |

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