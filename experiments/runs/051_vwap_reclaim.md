# Run 051_vwap_reclaim

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Track each stock's intraday VWAP (cumulative typical price × volume)
- Bullish session: SPY above VWAP AND SPY up >0.3% from open
- State machine per symbol:
-   Phase 1: stock crosses above VWAP (after 9:45 warmup) → mark was_above_vwap
-   Phase 2: stock crosses back below VWAP → mark had_pullback (shakeout)
-   Phase 3: stock reclaims VWAP (crosses from below → above) → ENTRY
- Entry only after pullback confirmed (not the initial rise above VWAP)
- Stop loss: 0.75% below entry
- Profit target: 1.5% above entry
- Entry window: 9:45 ET → 14:00 ET
- One trade per symbol per day
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2025-01-01 → 2025-12-31 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| stop_pct | 0.75 |
| profit_target_pct | 1.5 |
| spy_min_move_pct | 0.3 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -2.04% |
| Monthly return | -0.17% |
| Sharpe ratio | -0.8 |
| Max drawdown | -3.94% |
| Fills | 2034 |
| Round trips | 1017 |
| Win rate | 41.5% |
| Profit factor | 0.89 |
| Expectancy | $-2.0 |
| Max consec losses | 12 |
| Final equity | $97,961.59 |

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