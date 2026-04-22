# Run 164_aw5_dow_only

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BEAR SLEEVE ===
- RS SHORT on bearish sessions (VWAP + 3d trend)
- === BULL SLEEVE (Multi-Signal Overnight) ===
- T1 (SPY>VWAP): 3+3
- T2 (VGK>0): 1+1
- T3 (UVXY>+999.0% OR SPY<-999.0%): 0+0
- DoW boost (THU,WED,TUE): +1 extra positions
- Exit 15min after open

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP, VGK, UVXY |
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
| global_signal | VGK |
| fear_symbol | UVXY |
| fear_threshold | 999.0 |
| selloff_threshold | 999.0 |
| dow_boost_days | TUE,WED,THU |
| dow_extra_k | 1 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 9.39% |
| Monthly return | 2.29% |
| Sharpe ratio | 3.16 |
| Max drawdown | -3.71% |
| Fills | 745 |
| Round trips | 371 |
| Win rate | 48.0% |
| Profit factor | 1.63 |
| Expectancy | $25.04 |
| Max consec losses | 13 |
| Final equity | $109,393.00 |

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