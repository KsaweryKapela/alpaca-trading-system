# Run 105_xs_revert

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- At 10:00 ET: rank all stocks by return from open
- SHORT top 3 performers (morning winners → expect reversal)
- LONG bottom 3 performers (morning losers → expect reversal)
- Min move: stock must be >0.3% from open to qualify
- Stop: 1.5% from entry
- Market-neutral: 3 shorts + 3 longs
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
| top_k | 3 |
| bottom_k | 3 |
| min_move_pct | 0.3 |
| stop_pct | 1.5 |
| profit_target_pct | 0.0 |
| entry_hour | 10 |
| entry_minute | 0 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -6.09% |
| Monthly return | -1.56% |
| Sharpe ratio | -4.33 |
| Max drawdown | -6.8% |
| Fills | 714 |
| Round trips | 357 |
| Win rate | 39.8% |
| Profit factor | 0.71 |
| Expectancy | $-17.06 |
| Max consec losses | 9 |
| Final equity | $93,910.59 |

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