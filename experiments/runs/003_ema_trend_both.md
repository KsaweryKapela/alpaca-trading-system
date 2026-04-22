# Run 003_ema_trend_both

**Date:** 2026-04-10
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Trend filter: EMA9 vs EMA21 on 1m bars (continuous)
- Trade LONG on bullish EMA pullback AND SHORT on bearish EMA pullback
- LONG entry: EMA9 > EMA21 AND close crosses up through EMA9 (pullback bounce)
- SHORT entry: EMA9 < EMA21 AND close crosses down through EMA9 (pullback rejection)
- Stop loss: 0.3% from entry
- Profit target: 2.0× stop distance (0.60% from entry)
- No new entries before 9:45 ET (warm-up) or after 14:00 ET
- One trade per asset per day — no re-entry
- EOD flatten at 15:55 ET by engine

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | QQQ, SPY, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| fast_period | 9 |
| slow_period | 21 |
| stop_pct | 0.3 |
| profit_mult | 2.0 |
| entry_end_hour | 14 |
| direction | both |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -6.05% |
| Monthly return | -1.54% |
| Sharpe ratio | -7.76 |
| Max drawdown | -6.18% |
| Fills | 2242 |
| Round trips | 1121 |
| Win rate | 38.3% |
| Profit factor | 0.7 |
| Expectancy | $-5.4 |
| Max consec losses | 16 |
| Final equity | $93,948.91 |

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