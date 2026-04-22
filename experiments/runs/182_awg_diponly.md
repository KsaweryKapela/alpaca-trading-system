# Run 182_awg_diponly

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BEAR SLEEVE (RS Short) ===
- RS < -1.0% on bearish sessions (VWAP + 3d trend)
- === BULL SLEEVE (Global-Signal Overnight) ===
- Tier 1 (SPY > VWAP): 0 winners + 5 dip buys
- Tier 2 (SPY < VWAP BUT VGK > +0.0%): 0+2
- Global signal: VGK session return (Europe/International)
- Overnight stop: 2.0% | Exit 15min

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP, VGK |
| Date range | 2026-01-01 → 2026-04-30 |
| Interval | 1m |
| Leverage | 5.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| rs_threshold | 1.0 |
| spy_trend_days | 3 |
| overnight_top_k | 0 |
| overnight_bottom_k | 5 |
| overnight_stop_pct | 2.0 |
| overnight_exit_after_min | 15 |
| global_signal_symbol | VGK |
| global_min_return | 0.0 |
| tier2_top_k | 0 |
| tier2_bottom_k | 2 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 7.89% |
| Monthly return | 1.95% |
| Sharpe ratio | 3.11 |
| Max drawdown | -3.58% |
| Fills | 696 |
| Round trips | 348 |
| Win rate | 50.9% |
| Profit factor | 1.51 |
| Expectancy | $22.66 |
| Max consec losses | 9 |
| Final equity | $107,887.31 |

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