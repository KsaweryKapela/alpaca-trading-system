# Run 007_gap_fill_r1

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
- Profit target: 100% of gap fill (partial if < 100%)
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
| fill_target_pct | 1.0 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -0.91% |
| Monthly return | -0.28% |
| Sharpe ratio | -1.85 |
| Max drawdown | -1.3% |
| Fills | 316 |
| Round trips | 158 |
| Win rate | 46.2% |
| Profit factor | 0.81 |
| Expectancy | $-5.75 |
| Max consec losses | 8 |
| Final equity | $99,092.11 |

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