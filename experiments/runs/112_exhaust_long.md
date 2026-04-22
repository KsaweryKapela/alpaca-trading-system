# Run 112_exhaust_long

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Track per-stock VWAP and cumulative volume vs 10-day average
- LONG FADE when: return < -1.5% AND volume > 1.5× avg (exhaustion selloff)
- SHORT FADE when: return > +1.5% AND volume > 1.5× avg (exhaustion rally)
- Stop: 1.5% beyond extreme | Target: 1.5% fade
- Direction: long_only
- Entry window: 30 min after open → 15:00 ET
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
| extreme_pct | 1.5 |
| vol_mult | 1.5 |
| stop_pct | 1.5 |
| target_pct | 1.5 |
| direction | long_only |
| entry_after_min | 30 |
| entry_end_hour | 15 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -3.5% |
| Monthly return | -0.88% |
| Sharpe ratio | -2.47 |
| Max drawdown | -5.03% |
| Fills | 348 |
| Round trips | 174 |
| Win rate | 44.8% |
| Profit factor | 0.71 |
| Expectancy | $-20.1 |
| Max consec losses | 7 |
| Final equity | $96,502.30 |

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