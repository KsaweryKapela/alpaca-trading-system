# Run 108_volmom_both

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
- Stop: 1.5% | Direction: both
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
| direction | both |
| rvol_min | 1.5 |
| entry_hour | 10 |
| entry_minute | 0 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 0.11% |
| Monthly return | 0.04% |
| Sharpe ratio | 0.11 |
| Max drawdown | -3.25% |
| Fills | 226 |
| Round trips | 113 |
| Win rate | 48.7% |
| Profit factor | 1.01 |
| Expectancy | $1.0 |
| Max consec losses | 3 |
| Final equity | $100,112.77 |

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