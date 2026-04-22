# Run 007_orb_spy_short

**Date:** 2026-04-10
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Opening range: first 15 minutes establish the range
- Direction: short_only
- Regime filter: SPY below its daily VWAP (bearish macro)
- SHORT entry: breakdown below range_low AND SPY < SPY_VWAP
- Stop loss: 1.0% above entry
- Exit: EOD flatten (no profit target)
- One trade per asset per day — no re-entry
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | QQQ, SPY, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| range_minutes | 15 |
| stop_pct | 1.0 |
| profit_target_pct | 0.0 |
| direction | short_only |
| regime_filter | True |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 1.5% |
| Monthly return | 0.38% |
| Sharpe ratio | 0.14 |
| Max drawdown | -5.26% |
| Fills | 1426 |
| Round trips | 713 |
| Win rate | 45.2% |
| Profit factor | 1.07 |
| Expectancy | $2.1 |
| Max consec losses | 9 |
| Final equity | $101,495.81 |

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