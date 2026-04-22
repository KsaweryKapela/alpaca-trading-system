# Run 213_sr_base

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- LONG when SPY drops >0.5% from open
- Check window: 60min after open → 14:00
- Stop: 1.0× dip below entry
- Exit: 15:25 ET
- Require SPY below VWAP for long entry
- Trade: SPY, QQQ

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-30 |
| Interval | 1m |
| Leverage | 3.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| dip_threshold | 0.5 |
| check_after_min | 60 |
| direction | long_only |
| require_below_vwap | True |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -1.11% |
| Monthly return | -0.28% |
| Sharpe ratio | -1.16 |
| Max drawdown | -2.35% |
| Fills | 108 |
| Round trips | 54 |
| Win rate | 53.7% |
| Profit factor | 0.71 |
| Expectancy | $-20.53 |
| Max consec losses | 4 |
| Final equity | $98,891.51 |

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