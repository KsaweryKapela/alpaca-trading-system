# Run 054_vwap_reclaim_rs

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Track each stock's intraday VWAP (cumulative typical price × volume)
- Bullish session: SPY above VWAP AND SPY up >0.5% from open
- State machine per symbol:
-   Phase 1: stock crosses above VWAP (after 9:45 warmup) → mark was_above_vwap
-   Phase 2: stock crosses back below VWAP → mark had_pullback (shakeout)
-   Phase 3: stock reclaims VWAP (crosses from below → above) → ENTRY
- Entry only after pullback confirmed (not the initial rise above VWAP)
- Stop loss: 1.0% below entry
- Profit target: 2.0% above entry
- Entry window: 9:45 ET → 13:00 ET
- One trade per symbol per day
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| stop_pct | 1.0 |
| profit_target_pct | 2.0 |
| spy_min_move_pct | 0.5 |
| rs_min_pct | 0.0 |
| entry_end_hour | 13 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 1.34% |
| Monthly return | 0.34% |
| Sharpe ratio | 2.16 |
| Max drawdown | -0.9% |
| Fills | 318 |
| Round trips | 159 |
| Win rate | 47.8% |
| Profit factor | 1.52 |
| Expectancy | $8.45 |
| Max consec losses | 4 |
| Final equity | $101,344.07 |

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