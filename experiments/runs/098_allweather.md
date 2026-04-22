# Run 098_allweather

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BEAR SLEEVE (RS Short, Intraday) ===
- Active when: SPY below VWAP + SPY < close 3 days ago
- SHORT when RS < -1.0% vs SPY
- Stop: 1.0% | Target: 2.0%
- Entry: 15 min after open → 14:00 ET
- Exit: by stop/target or 15:55 (must be flat before overnight sleeve)
- === BULL SLEEVE (Overnight Long, Swing) ===
- Active when: SPY above VWAP at 15:30 ET
- LONG when stock return > +0.5% on bullish session
- Hold overnight → exit 5 min after next day open
- Stop: 2.0%
- === TIMING ===
- Bear sleeve: 9:45 → 15:55 (intraday, exits before close)
- Bull sleeve: 15:30 → next day 9:35 (overnight only)

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
| rs_target_pct | 2.0 |
| spy_trend_days | 3 |
| rs_entry_after_min | 15 |
| rs_entry_end_hour | 14 |
| overnight_min_return | 0.5 |
| overnight_stop_pct | 2.0 |
| overnight_entry_hour | 15 |
| overnight_entry_minute | 30 |
| overnight_exit_after_min | 5 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 9.99% |
| Monthly return | 2.43% |
| Sharpe ratio | 3.97 |
| Max drawdown | -3.56% |
| Fills | 842 |
| Round trips | 419 |
| Win rate | 51.8% |
| Profit factor | 1.67 |
| Expectancy | $23.77 |
| Max consec losses | 10 |
| Final equity | $109,989.63 |

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