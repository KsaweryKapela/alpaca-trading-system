# Run 045_vwap_qqq_long

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
- Direction: long_only
- Entry window: 9:45 ET → 12:00 ET
- One trade per symbol per day
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 5m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| stop_pct | 0.5 |
| profit_target_pct | 0.0 |
| direction | long_only |
| spy_min_move_pct | 0.1 |
| rs_confirm_pct | 0.0 |
| entry_end_hour | 12 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -0.48% |
| Monthly return | -0.12% |
| Sharpe ratio | -2.34 |
| Max drawdown | -0.8% |
| Fills | 52 |
| Round trips | 26 |
| Win rate | 34.6% |
| Profit factor | 0.54 |
| Expectancy | $-18.39 |
| Max consec losses | 4 |
| Final equity | $99,521.96 |

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