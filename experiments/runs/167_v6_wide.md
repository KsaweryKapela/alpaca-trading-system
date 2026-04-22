# Run 167_v6_wide

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BULL SLEEVE (Multi-Day Trend Rider) ===
- Regime: SPY > 5-day SMA
- Entry: top 3 winners + bottom 3 dip buys at 15:30
- Hold multi-day, trail stop 5.0%, max 20 days
- Exit ALL when SPY < SMA (regime switch)
- === BEAR SLEEVE (RS Short, Intraday) ===
- RS < -1.0% on bearish sessions (VWAP + 3d trend)
- Stop 1.0% | Target 2.0% | Flatten by 15:25

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | QQQ, SPY, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-30 |
| Interval | 1m |
| Leverage | 5.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| sma_period | 5 |
| long_top_k | 3 |
| long_bottom_k | 3 |
| trail_stop_pct | 5.0 |
| max_hold_days | 20 |
| min_rs_entry | 0.2 |
| exit_morning_min | 15 |
| rs_threshold | 1.0 |
| spy_trend_days | 3 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 1.99% |
| Monthly return | 0.49% |
| Sharpe ratio | 2.13 |
| Max drawdown | -1.29% |
| Fills | 154 |
| Round trips | 76 |
| Win rate | 47.4% |
| Profit factor | 1.41 |
| Expectancy | $15.7 |
| Max consec losses | 4 |
| Final equity | $101,991.59 |

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