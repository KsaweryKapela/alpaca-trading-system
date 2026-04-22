# Run 117_aw2_vwap_top8

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BEAR SLEEVE (RS Short, Intraday) ===
- SPY below VWAP + SPY < close 3 days ago → RS SHORT
- RS < -1.0% vs SPY | Stop 1.0% | TP 2.0%
- === BULL SLEEVE (Overnight Long, SMA trend) ===
- SPY above 10-day SMA → overnight long allowed
- At 15:30: rank stocks by session RS
- Buy top 8 with RS > -999.0%
- Hold overnight, exit 5 min after next open
- Stop: 2.0%

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 3.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| rs_threshold | 1.0 |
| rs_stop_pct | 1.0 |
| rs_target_pct | 2.0 |
| spy_trend_days | 3 |
| sma_period | 10 |
| overnight_top_k | 8 |
| overnight_min_rs | -999.0 |
| overnight_stop_pct | 2.0 |
| overnight_exit_after_min | 5 |
| require_vwap_bull | True |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 3.97% |
| Monthly return | 0.98% |
| Sharpe ratio | 1.45 |
| Max drawdown | -4.71% |
| Fills | 734 |
| Round trips | 365 |
| Win rate | 48.8% |
| Profit factor | 1.29 |
| Expectancy | $10.63 |
| Max consec losses | 13 |
| Final equity | $103,974.21 |

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