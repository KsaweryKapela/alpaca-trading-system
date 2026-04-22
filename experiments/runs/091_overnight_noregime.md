# Run 091_overnight_noregime

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- At 15:30 ET: evaluate each stock's session return
- LONG when return > +0.3% and SPY bullish → hold overnight
- SHORT when return < -0.3% and SPY bearish → hold overnight
- Exit: 5 min after next day open
- Stop: 3.0% from entry
- Direction: long_only
- No regime filter
- Positions held overnight — NO EOD flatten

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 3.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| min_return_pct | 0.3 |
| stop_pct | 3.0 |
| direction | long_only |
| regime_filter | False |
| entry_hour | 15 |
| entry_minute | 30 |
| exit_after_min | 5 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -1.36% |
| Monthly return | -0.34% |
| Sharpe ratio | -0.91 |
| Max drawdown | -3.17% |
| Fills | 500 |
| Round trips | 248 |
| Win rate | 45.6% |
| Profit factor | 0.86 |
| Expectancy | $-5.59 |
| Max consec losses | 6 |
| Final equity | $98,639.32 |

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