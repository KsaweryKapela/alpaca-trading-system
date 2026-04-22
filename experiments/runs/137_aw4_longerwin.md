# Run 137_aw4_longerwin

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BEAR SLEEVE (RS Short) ===
- RS < -1.0% on bearish sessions (VWAP + 3d trend)
- === BULL SLEEVE (Tiered Overnight) ===
- Tier 1 (SPY > VWAP): top 3 + bottom 3 positions
- Tier 2 (SPY < VWAP but > 10-SMA): top 2 + bottom 2
- Adaptive exit: winners hold 30min, losers exit 5min
- Overnight stop: 2.0%

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 5.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| rs_threshold | 1.0 |
| spy_trend_days | 3 |
| overnight_top_k | 3 |
| overnight_bottom_k | 3 |
| overnight_stop_pct | 2.0 |
| overnight_min_move | 0.3 |
| sma_period | 10 |
| tier2_top_k | 2 |
| tier2_bottom_k | 2 |
| exit_win_min | 30 |
| exit_loss_min | 5 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 2.45% |
| Monthly return | 0.62% |
| Sharpe ratio | 0.49 |
| Max drawdown | -6.88% |
| Fills | 782 |
| Round trips | 390 |
| Win rate | 44.4% |
| Profit factor | 1.15 |
| Expectancy | $6.02 |
| Max consec losses | 15 |
| Final equity | $102,450.71 |

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