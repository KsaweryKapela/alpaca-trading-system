# Run 050_rs_long_delayed

**Date:** 2026-04-11
**Status:** [ ] In Progress  [x] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

RS long fails at 9:45 (047) because entering at the first moment a stock is +1%>SPY = buying the morning spike top. The delayed entry hypothesis: if the stock is STILL outperforming SPY by 1%+ at 10:30 AM (60 minutes after open), the morning spike has settled and the outperformance is a genuine trend signal. Two hours of relative strength = institutional momentum, not noise.

## Strategy Rules

- Track each stock's % return from its own day open
- Compute Relative Strength (RS) = stock_return% - SPY_return%
- SHORT when RS < -1.0% (underperforming SPY — weak stock in weak market)
- LONG when RS > +1.0% (outperforming SPY — strong stock in strong market)
- Stop loss: 1.0% from entry
- Profit target: 2.0% from entry
- Direction: long_only
- SPY VWAP regime filter — only short on bearish sessions, only long on bullish
- Entry window: 60 min after open → 14:00 ET
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
| rs_threshold | 1.0 |
| stop_pct | 1.0 |
| profit_target_pct | 2.0 |
| direction | long_only |
| regime_filter | True |
| spy_decline_pct | 0.0 |
| spy_trend_days | 0 |
| entry_after_min | 60 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -2.33% |
| Monthly return | -0.59% |
| Sharpe ratio | -2.81 |
| Max drawdown | -3.59% |
| Fills | 652 |
| Round trips | 326 |
| Win rate | 37.7% |
| Profit factor | 0.72 |
| Expectancy | $-7.14 |
| Max consec losses | 12 |
| Final equity | $97,673.60 |

## Evaluation

Score against candidate criteria:

- [ ] Total return positive (-2.33% — negative)
- [ ] Monthly return ≥ 5% (-0.59%)
- [ ] Sharpe ≥ 0.5 (-2.81 — negative)
- [x] Max drawdown ≤ 25% (-3.59%)
- [ ] Win rate ≥ 40% (37.7%)
- [ ] Profit factor ≥ 1.5 (0.72)
- [x] Round trips ≥ 15 (326)
- [x] All trades intraday
- [x] Tested on ≥ 2 symbols (17)

Observations:

Delayed entry (10:30) made zero difference. Win rate 37.7% vs 38% at 9:45. PF 0.72 vs 0.78. The hypothesis that "spike settles by 10:30" is wrong — or rather, the RS long signal is not a spike entry at all. Stocks that are still +1%>SPY at 10:30 have been outperforming for 60 minutes already — they're not spikes, they're genuine trend days. But they still have 37.7% win rate. Why? Because by 10:30, the easy money is already made. The stock has run for an hour. Entering at +1% RS at 10:30 = entering at the end of the first leg, where the natural pause/consolidation hits the 1% stop. The RS long signal measures where the stock HAS BEEN, not where it IS GOING. Fundamentally different from RS short: weak stocks continue weakening because sellers systematically distribute. Strong stocks front-load their buyers and then pause/consolidate. 

Cross-regime: 2025 (bull year) also -9.33% — RS long loses in bull market too. This is conclusive: the RS long concept has no edge at any entry time on 1m bars.

## Decision

**[x] Reject** — RS long is dead regardless of entry timing. The asymmetry is structural: RS short has persistent seller momentum (distribution programs), RS long has already-completed buyer momentum (front-loaded at open). Closing the RS long direction entirely. Moving to bull-sleeve H2: VWAP reclaim after pullback — a different entry mechanic that enters at the BOTTOM of a retracement, not at the TOP of a move.

## Next Step

051: VWAP reclaim strategy. On bullish sessions (SPY above VWAP), enter LONG when a stock: (1) was above VWAP at open, (2) dipped below VWAP (tested support), (3) crosses back above VWAP (confirmed reclaim). Entry = institutional reload at VWAP support, not spike top.