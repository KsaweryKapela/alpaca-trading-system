# Run 171_v8_asym

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BEAR SLEEVE (RS Short) ===
- RS < -1.0% on bearish sessions (VWAP + 3d trend)
- === BULL SLEEVE (Overnight + Asymmetric Hold) ===
- T1 (SPY>VWAP): 3+3
- T2 (VGK>0): 1+1
- === ASYMMETRIC EXIT ===
- Losers: exit at 9:30+15min
- Winners: hold until 15:25

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
| overnight_top_k | 3 |
| overnight_bottom_k | 3 |
| overnight_stop_pct | 2.0 |
| loser_exit_min | 15 |
| winner_hold_hour | 15 |
| winner_hold_min | 25 |
| multiday_extend | False |
| max_extend_days | 3 |
| global_signal | VGK |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 1.18% |
| Monthly return | 0.3% |
| Sharpe ratio | -0.43 |
| Max drawdown | -1.93% |
| Fills | 230 |
| Round trips | 115 |
| Win rate | 41.7% |
| Profit factor | 1.43 |
| Expectancy | $10.25 |
| Max consec losses | 8 |
| Final equity | $101,178.36 |

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