# Run 044_vwap_cross_5m

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Track each stock's intraday VWAP (cumulative typical price × volume)
- Bullish session (SPY > VWAP AND SPY up >0.2% from open):
-   LONG entry: stock price crosses FROM BELOW to ABOVE its own VWAP
- Bearish session (SPY < VWAP AND SPY down >0.2% from open):
-   SHORT entry: stock price crosses FROM ABOVE to BELOW its own VWAP
- Stop loss: 0.5% from VWAP at entry
- Profit target: 1.0% from entry
- Direction: both
- Entry window: 9:45 ET → 14:00 ET
- One trade per symbol per day
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | QQQ, SPY, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 5m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| stop_pct | 0.5 |
| profit_target_pct | 1.0 |
| direction | both |
| spy_min_move_pct | 0.2 |
| rs_confirm_pct | 0.0 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -3.07% |
| Monthly return | -0.76% |
| Sharpe ratio | -2.36 |
| Max drawdown | -4.02% |
| Fills | 1414 |
| Round trips | 707 |
| Win rate | 40.0% |
| Profit factor | 0.88 |
| Expectancy | $-4.35 |
| Max consec losses | 10 |
| Final equity | $96,927.79 |

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