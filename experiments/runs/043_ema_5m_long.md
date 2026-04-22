# Run 043_ema_5m_long

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Trend filter: EMA9 vs EMA21 on 1m bars (continuous)
- Trade LONG pullbacks only (EMA9 > EMA21 required)
- LONG entry: EMA9 > EMA21 AND close crosses up through EMA9 (pullback bounce)
- SHORT entry: EMA9 < EMA21 AND close crosses down through EMA9 (pullback rejection)
- Stop loss: 0.5% from entry
- Profit target: 2.0× stop distance (1.00% from entry)
- No new entries before 9:45 ET (warm-up) or after 14:00 ET
- One trade per asset per day — no re-entry
- EOD flatten at 15:55 ET by engine

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | QQQ, SPY, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 5m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| fast_period | 9 |
| slow_period | 21 |
| stop_pct | 0.5 |
| profit_mult | 2.0 |
| entry_end_hour | 14 |
| direction | long_only |
| regime_filter | True |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -8.35% |
| Monthly return | -2.14% |
| Sharpe ratio | -5.57 |
| Max drawdown | -10.08% |
| Fills | 1170 |
| Round trips | 581 |
| Win rate | 31.7% |
| Profit factor | 0.6 |
| Expectancy | $-14.53 |
| Max consec losses | 13 |
| Final equity | $91,645.89 |

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