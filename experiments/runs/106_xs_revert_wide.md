# Run 106_xs_revert_wide

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- At 10:00 ET: rank all stocks by return from open
- SHORT top 5 performers (morning winners → expect reversal)
- LONG bottom 5 performers (morning losers → expect reversal)
- Min move: stock must be >0.5% from open to qualify
- Stop: 2.0% from entry
- Market-neutral: 5 shorts + 5 longs
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
| top_k | 5 |
| bottom_k | 5 |
| min_move_pct | 0.5 |
| stop_pct | 2.0 |
| profit_target_pct | 0.0 |
| entry_hour | 10 |
| entry_minute | 0 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -8.39% |
| Monthly return | -2.16% |
| Sharpe ratio | -3.99 |
| Max drawdown | -9.49% |
| Fills | 928 |
| Round trips | 464 |
| Win rate | 43.3% |
| Profit factor | 0.69 |
| Expectancy | $-18.09 |
| Max consec losses | 9 |
| Final equity | $91,607.85 |

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