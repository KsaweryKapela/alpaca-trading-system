# Run 059_gap_go_delayed

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Track previous session's closing price for each symbol
- Gap-up: today_open > prev_close × (1 + 0.5/100)
- Skip gaps > 3.0% (earnings/news blowups)
- At 9:45 ET: if price still above 50% of gap → gap is held
- Session filter: SPY above VWAP AND up >0.3% from open
- Entry: LONG on gap hold confirmation at 9:45
- Stop: 1.0% below entry
- Target: 2.0% above entry
- Entry window: 9:45 → 12:00 ET (one trade/day)
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| min_gap_pct | 0.5 |
| max_gap_pct | 3.0 |
| gap_hold_ratio | 0.5 |
| stop_pct | 1.0 |
| profit_target_pct | 2.0 |
| spy_min_move_pct | 0.3 |
| entry_after_min | 60 |
| entry_end_hour | 12 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -0.58% |
| Monthly return | -0.14% |
| Sharpe ratio | -0.82 |
| Max drawdown | -2.19% |
| Fills | 224 |
| Round trips | 112 |
| Win rate | 38.4% |
| Profit factor | 0.82 |
| Expectancy | $-5.19 |
| Max consec losses | 6 |
| Final equity | $99,418.55 |

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