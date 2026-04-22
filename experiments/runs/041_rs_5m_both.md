# Run 041_rs_5m_both

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
- Stop loss: 1.5% from entry
- Profit target: 3.0% from entry
- Direction: both
- SPY VWAP regime filter — only short on bearish sessions, only long on bullish
- Entry window: 15 min after open → 14:00 ET
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
| rs_threshold | 1.0 |
| stop_pct | 1.5 |
| profit_target_pct | 3.0 |
| direction | both |
| regime_filter | True |
| spy_decline_pct | 0.0 |
| spy_trend_days | 0 |
| entry_after_min | 15 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 1.52% |
| Monthly return | 0.41% |
| Sharpe ratio | 0.66 |
| Max drawdown | -6.41% |
| Fills | 1403 |
| Round trips | 698 |
| Win rate | 44.3% |
| Profit factor | 1.03 |
| Expectancy | $2.15 |
| Max consec losses | 9 |
| Final equity | $101,519.93 |

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