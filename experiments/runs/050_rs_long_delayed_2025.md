# Run 050_rs_long_delayed_2025

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Track each stock's % return from its own day open
- Compute Relative Strength (RS) = stock_return% - SPY_return%
- SHORT when RS < -1.0% (underperforming SPY — weak stock in weak market)
- LONG when RS > +1.0% (outperforming SPY — strong stock in strong market)
- Stop loss: 1.0% from entry
- Profit target: 2.0% from entry
- Direction: long_only
- SPY VWAP regime filter — only short on bearish sessions, only long on bullish
- Entry window: 60 min after open → 14:00 ET
- One trade per symbol per day
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2025-01-01 → 2025-12-31 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| rs_threshold | 1.0 |
| stop_pct | 1.0 |
| profit_target_pct | 2.0 |
| direction | long_only |
| regime_filter | True |
| spy_decline_pct | 0.0 |
| spy_trend_days | 0 |
| entry_after_min | 60 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -9.33% |
| Monthly return | -0.81% |
| Sharpe ratio | -3.04 |
| Max drawdown | -9.94% |
| Fills | 2362 |
| Round trips | 1181 |
| Win rate | 38.4% |
| Profit factor | 0.69 |
| Expectancy | $-7.9 |
| Max consec losses | 9 |
| Final equity | $90,674.57 |

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