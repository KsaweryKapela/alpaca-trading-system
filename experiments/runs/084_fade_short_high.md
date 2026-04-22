# Run 084_fade_short_high

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Track each stock's % return from day open + per-stock VWAP
- SHORT when stock return > +1.5% from open (overextended spike)
- LONG when stock return < -1.5% from open (oversold fade)
- Stock must be beyond VWAP in spike direction
- Stop loss: 1.0% from entry
- Profit target: 2.0% from entry (fade toward VWAP)
- Direction: short_only
- No regime filter
- Entry window: 15 min after open → 14:00 ET
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
| spike_pct | 1.5 |
| stop_pct | 1.0 |
| target_pct | 2.0 |
| direction | short_only |
| require_vwap_extended | True |
| regime_filter | False |
| entry_after_min | 15 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -6.85% |
| Monthly return | -1.75% |
| Sharpe ratio | -4.89 |
| Max drawdown | -9.06% |
| Fills | 676 |
| Round trips | 338 |
| Win rate | 38.8% |
| Profit factor | 0.67 |
| Expectancy | $-20.26 |
| Max consec losses | 10 |
| Final equity | $93,151.51 |

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