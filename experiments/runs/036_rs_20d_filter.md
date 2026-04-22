# Run 036_rs_20d_filter

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [x] Revised  [ ] Promising

---

## Hypothesis

033 (5-day trend filter) fixed 2025 (-8.58% → +0.19%) but cost 2026 performance (1.65% → 0.85%/mo). Hypothesis: a 20-day lookback ("SPY below where it was 4 weeks ago") is more surgical — fires only during multi-week downtrends, not every 5-day dip. Should block more 2025 bull-market signals while preserving 2026 bear signals. But bootstrapping problem: on 2026-01-01 the deque is empty, so the filter only activates around Jan 29, 2026 (20 trading days in).

## Strategy Rules

- Track each stock's % return from its own day open
- Compute Relative Strength (RS) = stock_return% - SPY_return%
- SHORT when RS < -1.0% (underperforming SPY — weak stock in weak market)
- LONG when RS > +1.0% (outperforming SPY — strong stock in strong market)
- Stop loss: 1.0% from entry
- Profit target: 2.0% from entry
- Direction: short_only
- SPY VWAP regime filter — only short on bearish sessions, only long on bullish
- SPY multi-day trend filter: only short when SPY < close 20 days ago
- Entry window: 15 min after open → 14:00 ET
- One trade per symbol per day
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | QQQ, SPY, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 2.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| rs_threshold | 1.0 |
| stop_pct | 1.0 |
| profit_target_pct | 2.0 |
| direction | short_only |
| regime_filter | True |
| spy_decline_pct | 0.0 |
| spy_trend_days | 20 |
| entry_after_min | 15 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 3.01% |
| Monthly return | 0.75% |
| Sharpe ratio | 1.42 |
| Max drawdown | -3.36% |
| Fills | 824 |
| Round trips | 412 |
| Win rate | 45.4% |
| Profit factor | 1.21 |
| Expectancy | $7.31 |
| Max consec losses | 16 |
| Final equity | $103,009.73 |

## Evaluation

Score against candidate criteria:

- [x] Total return positive (+3.01%)
- [ ] Monthly return ≥ 5% (0.75%)
- [x] Sharpe ≥ 0.5 (1.42)
- [x] Max drawdown ≤ 25% (-3.36%)
- [x] Win rate ≥ 40% (45.4%)
- [ ] Profit factor ≥ 1.5 (1.21)
- [x] Round trips ≥ 15 (412)
- [x] All trades intraday
- [x] Tested on ≥ 2 symbols

Observations:

Worse than 033 (5-day filter) in both dimensions: 2026 monthly 0.75% vs 0.85%, Sharpe 1.42 vs 1.72; 2025 -2.35% vs +0.19%. The 20-day filter has a bootstrapping problem: on 2026-01-01, the SPY daily_closes deque starts empty. The filter only activates ~Jan 29, 2026 (20 days in), missing the best Jan bear signals. Meanwhile it has MORE trades than 033 (412 vs 304) — because the filter is inactive for the first 20 days, allowing unfiltered shorts. Those unfiltered early January shorts probably included some that the 5-day filter would have also passed AND some bad ones from the bull-bias month. In 2025, the 20-day filter fires on longer corrections (e.g., the 3-4 week SPY pull-back periods), and when those happen in 2025 the shorts lose because the bounce quickly resumes. Result: more trades but worse quality.

**Key learning**: Multi-day SPY trend filters are broken by the deque bootstrapping issue — the first N days of any backtest are filter-inactive. This makes them unreliable without pre-loading prior SPY closes.

## Decision

**[x] Revised** — abandon multi-day trend filter approach. The bootstrapping problem can't be fixed without loading pre-backtest SPY data. Focus instead on finding a different cross-regime approach.

## Next Step

037: Push 031 (best result) to 2.5× leverage to check if monthly return can reach 2%. Then 038: ORB long-only on 6 high-volatility symbols (NVDA, TSLA, COIN, AMD, PLTR, RIVN) as a potential bull-market complement.