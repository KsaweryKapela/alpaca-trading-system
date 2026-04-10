# Run 008_gap_fill_r2

**Date:** 2026-04-10
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Track yesterday's close for each symbol
- Entry on first bar of day when gap [0.7%–2.0%]
- Gap UP (open > prev_close + 0.7%): go SHORT — bet on gap fill
- Gap DOWN (open < prev_close − 0.7%): go LONG — bet on gap fill
- Profit target: yesterday's close (full gap fill)
- Stop loss: 0.5× gap size beyond entry (gap extension)
- Profit target: 100% of gap fill (partial if < 100%)
- Direction filter: both (up_only=short only, down_only=long only)
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
| min_gap_pct | 0.7 |
| max_gap_pct | 2.0 |
| stop_mult | 0.5 |
| fill_target_pct | 1.0 |
| direction | both |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -1.15% |
| Monthly return | -0.36% |
| Sharpe ratio | -2.72 |
| Max drawdown | -1.41% |
| Fills | 206 |
| Round trips | 103 |
| Win rate | 43.7% |
| Profit factor | 0.69 |
| Expectancy | $-11.21 |
| Max consec losses | 8 |
| Final equity | $98,845.32 |

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