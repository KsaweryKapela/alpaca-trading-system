# Run 047_rs_long_only

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

RS short-only achieves Sharpe 3.15 in 2026 (bear). The logical counterpart: RS long-only (buy stocks outperforming SPY by 1%+) on bullish sessions (SPY above VWAP). If weak stocks keep weakening in bear markets, strong stocks should keep strengthening in bull markets. Entry at 9:45 AM when RS > +1%.

## Strategy Rules

- Track each stock's % return from its own day open
- Compute Relative Strength (RS) = stock_return% - SPY_return%
- SHORT when RS < -1.0% (underperforming SPY — weak stock in weak market)
- LONG when RS > +1.0% (outperforming SPY — strong stock in strong market)
- Stop loss: 1.0% from entry
- Profit target: 2.0% from entry
- Direction: long_only
- SPY VWAP regime filter — only short on bearish sessions, only long on bullish
- Entry window: 15 min after open → 14:00 ET
- One trade per symbol per day
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | QQQ, SPY, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| rs_threshold | 1.0 |
| stop_pct | 1.0 |
| profit_target_pct | 2.0 |
| direction | long_only |
| regime_filter | True |
| spy_decline_pct | 0.0 |
| spy_trend_days | 0 |
| entry_after_min | 15 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -2.49% |
| Monthly return | -0.62% |
| Sharpe ratio | -2.02 |
| Max drawdown | -3.4% |
| Fills | 732 |
| Round trips | 366 |
| Win rate | 38.0% |
| Profit factor | 0.78 |
| Expectancy | $-6.81 |
| Max consec losses | 10 |
| Final equity | $97,508.73 |

## Evaluation

Score against candidate criteria:

- [ ] Total return positive (-2.49% — negative)
- [ ] Monthly return ≥ 5% (-0.62%)
- [ ] Sharpe ≥ 0.5 (-2.02 — negative)
- [x] Max drawdown ≤ 25% (-3.4%)
- [ ] Win rate ≥ 40% (38.0%)
- [ ] Profit factor ≥ 1.5 (0.78)
- [x] Round trips ≥ 15 (366)
- [x] All trades intraday
- [x] Tested on ≥ 2 symbols (17)

Observations:

RS long is structurally broken at 1m. Win rate 38% (worse than random for a 2R strategy), PF 0.78. The mechanism is clear: entering when a stock is already +1% above SPY = buying at the local morning spike top. Institutional sellers absorb the move and price mean-reverts into the stop. Even in 2025's strong bull market, RS long loses -3.43% — the bull market provides no tailwind because we're always buying the peak. This is the same failure mode as ORB long: entering at the top of the 9:30-9:45 momentum candle.

## Decision

**[x] Reject** — RS long at 1m with 9:45 entry is definitively broken. The issue is entry timing, not the RS concept itself. A delayed entry (e.g., at 10:30 after the spike settles) may still work — testing in 050.

## Next Step

050: RS long with delayed entry (entry_after_min=60, i.e. 10:30 ET). If still +1% above SPY at 10:30, it's likely a genuine trend day, not a spike reversal. This is the bull-sleeve H1 test.