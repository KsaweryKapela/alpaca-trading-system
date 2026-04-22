# Run 011_orb_momentum_symbols

**Date:** 2026-04-10
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Opening range: first 5 minutes establish the range
- Direction: short_only
- Macro regime filter: SPY below its daily VWAP
- Stock VWAP filter: no stock VWAP filter
- Gap filter: no gap filter
- SHORT entry: breakdown below range_low (all active filters must pass)
- Stop loss: 1.0% above entry
- Exit: EOD flatten
- One trade per asset per day — no re-entry
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | QQQ, PLTR, TSLA, COIN, AMD, SHOP, BA, JPM |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| range_minutes | 5 |
| stop_pct | 1.0 |
| profit_target_pct | 0.0 |
| direction | short_only |
| regime_filter | True |
| stock_vwap_filter | False |
| gap_filter_pct | 0.0 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 4.38% |
| Monthly return | 1.08% |
| Sharpe ratio | 2.14 |
| Max drawdown | -3.99% |
| Fills | 786 |
| Round trips | 393 |
| Win rate | 43.8% |
| Profit factor | 1.39 |
| Expectancy | $11.14 |
| Max consec losses | 9 |
| Final equity | $104,376.93 |

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