# Run 019_orb_quality_filters

**Date:** 2026-04-10
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Opening range: first 5 minutes establish the range
- Direction: short_only
- Macro regime filter: SPY below its daily VWAP
- SPY intraday decline filter: SPY must be down >0.3% from day open at entry
- Stock VWAP filter: no stock VWAP filter
- Gap filter: no gap filter
- Min range width filter: ORB range width must be >0.6% of range_low
- SHORT entry: breakdown below range_low (all active filters must pass)
- Stop loss: 1.0% above entry
- Exit: EOD flatten
- One trade per asset per day — no re-entry
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | QQQ, SPY, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 2.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| range_minutes | 5 |
| stop_pct | 1.0 |
| profit_target_pct | 0.0 |
| direction | short_only |
| regime_filter | True |
| stock_vwap_filter | False |
| gap_filter_pct | 0.0 |
| max_trades_per_day | 1 |
| reentry_cooldown | 5 |
| spy_decline_pct | 0.3 |
| min_range_pct | 0.6 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -2.59% |
| Monthly return | -0.65% |
| Sharpe ratio | -1.79 |
| Max drawdown | -6.56% |
| Fills | 644 |
| Round trips | 322 |
| Win rate | 41.6% |
| Profit factor | 0.81 |
| Expectancy | $-8.04 |
| Max consec losses | 7 |
| Final equity | $97,410.43 |

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