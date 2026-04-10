# Run 011_gap_partial

**Date:** 2026-04-10
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Track yesterday's close for each symbol
- Entry on first bar of day when gap [0.5%–2.0%]
- Gap UP (open > prev_close + 0.5%): go SHORT — bet on gap fill
- Gap DOWN (open < prev_close − 0.5%): go LONG — bet on gap fill
- Profit target: yesterday's close (full gap fill)
- Stop loss: 0.5× gap size beyond entry (gap extension)
- Profit target: 70% of gap fill (partial if < 100%)
- Direction filter: down_only (up_only=short only, down_only=long only)
- Skip gaps > 2.0% (earnings / news events)
- One trade per asset per day — first bar entry only
- All positions closed by 15:55 ET (EOD flatten by engine)

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, AAPL, MSFT, NVDA |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| min_gap_pct | 0.5 |
| max_gap_pct | 2.0 |
| stop_mult | 0.5 |
| fill_target_pct | 0.7 |
| direction | down_only |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -0.33% |
| Monthly return | -0.1% |
| Sharpe ratio | -1.06 |
| Max drawdown | -0.75% |
| Fills | 162 |
| Round trips | 81 |
| Win rate | 46.9% |
| Profit factor | 0.83 |
| Expectancy | $-4.13 |
| Max consec losses | 7 |
| Final equity | $99,665.47 |

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