# Run 198_v11_gap_only

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BEAR SLEEVE (RS Short — delayed close) ===
- RS < -1.0% | Close at 15:35
- === BULL SLEEVE (Overnight — enhanced signals) ===
- T1: 4+4 | T2: 2+2
- Exit 20min after open
- Gap filter: skip stocks gapped >2.0% (exhausted)
- Stock personality: prefer high overnight-gap stocks

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
| rs_close_minute | 35 |
| exit_after_min | 20 |
| gap_filter | True |
| gap_fade_pct | 2.0 |
| use_daily_ema | False |
| breadth_filter | False |
| breadth_min_pct | 45.0 |
| use_overnight_beta | True |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 9.52% |
| Monthly return | 2.32% |
| Sharpe ratio | 3.34 |
| Max drawdown | -3.02% |
| Fills | 776 |
| Round trips | 388 |
| Win rate | 50.0% |
| Profit factor | 1.62 |
| Expectancy | $24.54 |
| Max consec losses | 12 |
| Final equity | $109,519.87 |

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