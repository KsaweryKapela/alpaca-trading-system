# Run 109_volmom_long

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Track relative volume (RVOL) = today's morning volume / 10-day avg
- At 10:00 ET with RVOL > 1.5×:
-   LONG if return > +0.3% AND above VWAP
-   SHORT if return < -0.3% AND below VWAP
- Require price on correct side of VWAP
- Stop: 1.5% | Direction: long_only
- One trade per symbol per day | EOD flatten 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 3.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| momentum_threshold | 0.3 |
| stop_pct | 1.5 |
| profit_target_pct | 0.0 |
| direction | long_only |
| rvol_min | 1.5 |
| entry_hour | 10 |
| entry_minute | 0 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -1.24% |
| Monthly return | -0.31% |
| Sharpe ratio | -1.67 |
| Max drawdown | -2.56% |
| Fills | 94 |
| Round trips | 47 |
| Win rate | 51.1% |
| Profit factor | 0.69 |
| Expectancy | $-26.42 |
| Max consec losses | 3 |
| Final equity | $98,758.41 |

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