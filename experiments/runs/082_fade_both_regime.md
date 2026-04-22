# Run 082_fade_both_regime

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
- Direction: both
- SPY VWAP regime filter active
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
| direction | both |
| require_vwap_extended | True |
| regime_filter | True |
| entry_after_min | 15 |
| entry_end_hour | 12 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -18.47% |
| Monthly return | -4.92% |
| Sharpe ratio | -7.2 |
| Max drawdown | -20.15% |
| Fills | 1588 |
| Round trips | 794 |
| Win rate | 38.8% |
| Profit factor | 0.58 |
| Expectancy | $-23.26 |
| Max consec losses | 9 |
| Final equity | $81,532.52 |

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