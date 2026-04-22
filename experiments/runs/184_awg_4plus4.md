# Run 184_awg_4plus4

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BEAR SLEEVE (RS Short) ===
- RS < -1.0% on bearish sessions (VWAP + 3d trend)
- === BULL SLEEVE (Global-Signal Overnight) ===
- Tier 1 (SPY > VWAP): 4 winners + 4 dip buys
- Tier 2 (SPY < VWAP BUT VGK > +0.0%): 2+2
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
| overnight_top_k | 4 |
| overnight_bottom_k | 4 |
| overnight_stop_pct | 2.0 |
| overnight_exit_after_min | 15 |
| global_signal_symbol | VGK |
| global_min_return | 0.0 |
| tier2_top_k | 2 |
| tier2_bottom_k | 2 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 7.38% |
| Monthly return | 1.83% |
| Sharpe ratio | 2.54 |
| Max drawdown | -4.21% |
| Fills | 768 |
| Round trips | 384 |
| Win rate | 47.7% |
| Profit factor | 1.39 |
| Expectancy | $19.21 |
| Max consec losses | 10 |
| Final equity | $107,377.74 |

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