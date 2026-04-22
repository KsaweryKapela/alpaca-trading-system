# Run 170_v7_sized

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BULL MODE (SPY > SMA) ===
- Regime: SPY > 10-day SMA
- Hold up to 8 diversified longs
- NO trail stops — exit ONLY on regime change or 15.0% catastrophe
- Rebalance daily at 15:30
- === BEAR MODE (SPY < VWAP + trend) ===
- RS < -1.0% | Stop 1.0% | Target 2.0%
- === TRANSITIONS ===
- Bull→Bear: exit all longs next morning
- Bear→Bull: enter diversified longs at 15:30

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | QQQ, SPY, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-30 |
| Interval | 1m |
| Leverage | 5.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| sma_period | 10 |
| spy_trend_days | 3 |
| long_max_positions | 8 |
| catastrophe_stop_pct | 15.0 |
| rs_threshold | 1.0 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -5.18% |
| Monthly return | -1.3% |
| Sharpe ratio | -2.82 |
| Max drawdown | -8.24% |
| Fills | 148 |
| Round trips | 70 |
| Win rate | 40.0% |
| Profit factor | 0.24 |
| Expectancy | $-99.33 |
| Max consec losses | 5 |
| Final equity | $94,818.04 |

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