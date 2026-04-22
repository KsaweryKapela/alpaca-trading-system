# Run 049_rs_1d_filter

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

033 (5-day trend filter) improved 2025 from -8.58% to +0.19% but cut 2026 monthly return from 1.65% to 0.85%. The 5-day lookback is too blunt — it blocks valid bear-day signals within the 2026 downtrend on short-term bounces. A 1-day filter (only short when today SPY opened lower than yesterday) is less aggressive: it blocks upside gap days (bull continuation) while preserving most bear signals.

## Strategy Rules

- Track each stock's % return from its own day open
- Compute Relative Strength (RS) = stock_return% - SPY_return%
- SHORT when RS < -1.0% (underperforming SPY — weak stock in weak market)
- LONG when RS > +1.0% (outperforming SPY — strong stock in strong market)
- Stop loss: 1.0% from entry
- Profit target: 2.0% from entry
- Direction: short_only
- SPY VWAP regime filter — only short on bearish sessions, only long on bullish
- SPY multi-day trend filter: only short when SPY < close 1 days ago
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
| spy_trend_days | 1 |
| entry_after_min | 15 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 4.09% |
| Monthly return | 1.01% |
| Sharpe ratio | 2.21 |
| Max drawdown | -3.08% |
| Fills | 646 |
| Round trips | 323 |
| Win rate | 45.8% |
| Profit factor | 1.34 |
| Expectancy | $12.66 |
| Max consec losses | 15 |
| Final equity | $104,087.90 |

## Evaluation

Score against candidate criteria:

- [x] Total return positive (+4.09%)
- [ ] Monthly return ≥ 5% (1.01%)
- [x] Sharpe ≥ 0.5 (2.21)
- [x] Max drawdown ≤ 25% (-3.08%)
- [x] Win rate ≥ 40% (45.8%)
- [ ] Profit factor ≥ 1.5 (1.34)
- [x] Round trips ≥ 15 (323)
- [x] All trades intraday
- [x] Tested on ≥ 2 symbols (17)

Observations:

1-day filter (SPY < yesterday's close) is between the 5-day filter and unfiltered: 2026 Sharpe 2.21 (vs 1.72 for 5d, 3.15 unfiltered), 2025 loss -6.18% (vs +0.19% for 5d, -8.58% unfiltered). The filter progression is intuitive — tighter filters cost more 2026 performance but help more in 2025. The 1-day filter is too weak to meaningfully protect against 2025 bull losses (still -6.18%), while also costing significant 2026 edge. Neither filter variant solves the cross-regime problem: we need a fundamentally different bull-market strategy, not better filtering of the short one. PF 1.34 is below the 1.5 threshold — this variant isn't better than 031 on any individual criteria.

## Decision

**[x] Reject** — The filter sweep (1d, 5d, 20d) is exhausted. Multi-day trend filters on the RS short degrade 2026 performance without adequately protecting 2025. The cross-regime problem requires a dedicated bull-sleeve strategy, not better filters on the bear sleeve. Closing this line of investigation.

## Next Step

050: RS long with delayed entry at 10:30 ET (entry_after_min=60). Hypothesis: RS long fails at 9:45 because we enter at the spike top. At 10:30, stocks still outperforming by 1%+ have survived the morning volatility → genuine trend days.