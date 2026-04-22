# Run 081_fade_short

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Track each stock's % return from day open + per-stock VWAP
- SHORT when stock return > +1.0% from open (overextended spike)
- LONG when stock return < -1.0% from open (oversold fade)
- Stock must be beyond VWAP in spike direction
- Stop loss: 1.0% from entry
- Profit target: 1.5% from entry (fade toward VWAP)
- Direction: short_only
- No regime filter
- Entry window: 15 min after open → 12:00 ET
- One trade per symbol per day
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
| spike_pct | 1.0 |
| stop_pct | 1.0 |
| target_pct | 1.5 |
| direction | short_only |
| require_vwap_extended | True |
| regime_filter | False |
| entry_after_min | 15 |
| entry_end_hour | 12 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -6.66% |
| Monthly return | -1.7% |
| Sharpe ratio | -3.95 |
| Max drawdown | -9.12% |
| Fills | 862 |
| Round trips | 431 |
| Win rate | 41.1% |
| Profit factor | 0.73 |
| Expectancy | $-15.45 |
| Max consec losses | 14 |
| Final equity | $93,339.68 |

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