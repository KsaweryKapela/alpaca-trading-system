# Run 166_v6_base

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BULL SLEEVE (Multi-Day Trend Rider) ===
- Regime: SPY > 5-day SMA
- Entry: top 3 winners + bottom 3 dip buys at 10:00
- Hold multi-day, trail stop 3.0%, max 15 days
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
| trail_stop_pct | 3.0 |
| max_hold_days | 15 |
| min_rs_entry | 0.3 |
| exit_morning_min | 15 |
| rs_threshold | 1.0 |
| spy_trend_days | 3 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -0.78% |
| Monthly return | -0.19% |
| Sharpe ratio | -0.62 |
| Max drawdown | -2.84% |
| Fills | 249 |
| Round trips | 124 |
| Win rate | 37.9% |
| Profit factor | 0.83 |
| Expectancy | $-9.91 |
| Max consec losses | 7 |
| Final equity | $99,219.41 |

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