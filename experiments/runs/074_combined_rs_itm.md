# Run 074_combined_rs_itm

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BEAR SLEEVE (RS Short) ===
- Active on: bearish SPY sessions (below VWAP) + SPY < close 3 days ago
- SHORT when stock RS < -1.0% vs SPY
- Stop: 1.0% | Target: 2.0%
- Entry window: 15 min after open → 14:00 ET
- === BULL SLEEVE (Intraday Momentum Long) ===
- Active on: bullish SPY sessions (above VWAP)
- LONG at 10:00 ET when return > +0.3% from open
- Stop: 1.5% | Hold to EOD
- One trade per sleeve per symbol per day
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 3.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| rs_threshold | 1.0 |
| rs_stop_pct | 1.0 |
| rs_profit_target_pct | 2.0 |
| spy_trend_days | 3 |
| rs_entry_after_min | 15 |
| rs_entry_end_hour | 14 |
| momentum_threshold | 0.3 |
| itm_stop_pct | 1.5 |
| itm_entry_hour | 10 |
| itm_entry_minute | 0 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 9.61% |
| Monthly return | 2.33% |
| Sharpe ratio | 3.83 |
| Max drawdown | -3.78% |
| Fills | 970 |
| Round trips | 485 |
| Win rate | 48.9% |
| Profit factor | 1.46 |
| Expectancy | $19.82 |
| Max consec losses | 12 |
| Final equity | $109,611.31 |

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