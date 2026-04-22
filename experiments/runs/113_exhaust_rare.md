# Run 113_exhaust_rare

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Track per-stock VWAP and cumulative volume vs 10-day average
- LONG FADE when: return < -3.0% AND volume > 2.0× avg (exhaustion selloff)
- SHORT FADE when: return > +3.0% AND volume > 2.0× avg (exhaustion rally)
- Stop: 2.0% beyond extreme | Target: 2.0% fade
- Direction: both
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
| extreme_pct | 3.0 |
| vol_mult | 2.0 |
| stop_pct | 2.0 |
| target_pct | 2.0 |
| direction | both |
| entry_after_min | 30 |
| entry_end_hour | 15 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -0.89% |
| Monthly return | -0.21% |
| Sharpe ratio | -0.65 |
| Max drawdown | -4.32% |
| Fills | 194 |
| Round trips | 97 |
| Win rate | 44.3% |
| Profit factor | 0.91 |
| Expectancy | $-9.17 |
| Max consec losses | 6 |
| Final equity | $99,110.33 |

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