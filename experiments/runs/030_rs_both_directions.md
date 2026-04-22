# Run 030_rs_both_directions

**Date:** 2026-04-11
**Status:** [ ] In Progress  [x] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

Since RS shorts work well in 2026 and RS longs theoretically should work symmetrically in bull markets, test both directions with the improved parameters (threshold=1%, TP=2%, entry_after_min=15). The SPY VWAP regime filter naturally gates: longs only when SPY is bullish (2025 sessions), shorts only when SPY is bearish (2026 sessions). Hypothesis: symmetric RS captures persistent intraday momentum in both directions.

**Why longs fail**: RS LONG = buying a stock that's already outperformed SPY by 1%+ from the 9:45 open. At 1m resolution, this is entering at a LOCAL TOP of the intraday move. The stock has already run its initial gap/momentum move — the remaining 2% to the profit target requires it to continue from an extended level, while the 1% stop is easily hit during normal consolidation. This is the wrong direction of momentum capture for 1m longs.

## Strategy Rules

- Track each stock's % return from its own day open
- Compute Relative Strength (RS) = stock_return% - SPY_return%
- SHORT when RS < -1.0% (underperforming SPY — weak stock in weak market)
- LONG when RS > +1.0% (outperforming SPY — strong stock in strong market)
- Stop loss: 1.0% from entry
- Profit target: 2.0% from entry
- Direction: both
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
| direction | both |
| regime_filter | True |
| spy_decline_pct | 0.0 |
| entry_after_min | 15 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 1.81% |
| Monthly return | 0.45% |
| Sharpe ratio | 1.42 |
| Max drawdown | -2.1% |
| Fills | 1476 |
| Round trips | 738 |
| Win rate | 44.2% |
| Profit factor | 1.09 |
| Expectancy | $2.45 |
| Max consec losses | 11 |
| Final equity | $101,806.54 |

## Evaluation

Score against candidate criteria:

- [x] Total return positive (+1.81%)
- [ ] Monthly return ≥ 5% (target) — 0.45% actual
- [x] Sharpe ≥ 0.5 — 1.42
- [x] Max drawdown ≤ 25% — -2.1%
- [x] Win rate ≥ 40% — 44.2%
- [ ] Profit factor ≥ 1.5 — 1.09 actual
- [x] Round trips ≥ 15 — high volume
- [x] All trades intraday (no overnight holds)
- [x] Tested on ≥ 2 symbols

Observations:

- **Adding longs hurts both regimes**: 2026 Sharpe dropped 2.91→1.42, 2025 worsened -5.66%→-9.66%. Longs damage the short-side signal quality by adding noise and capital drag.
- **2026 longs fire on brief recovery sessions**: In 2026's downtrend, days where SPY briefly rises above VWAP trigger long RS signals. But these are false bounces in a bear trend — they get sold, stopping out the longs immediately.
- **2025 longs worse than expected**: -9.66% vs -5.66% (028). Long RS signals buy stocks at their daily peak outperformance level (1%+ above SPY at 9:45). These stocks consolidate and the 1% stop gets hit frequently. In 2025 with ~20 long signals/day, this compounds into heavy losses.
- **Win rate 44.2%**: Shorts win at ~50%+ (confirmed by 028); longs win at much lower rates. The mixed WR confirms longs are the problem.
- **PF 1.09**: Near breakeven including longs. Strip longs out → PF returns to 1.39 (028 level). Longs add negative expected value.
- **RS LONG structural problem**: Momentum continuation requires entering EARLY in the move, not after 1%+ move has already happened. At 1m resolution, stocks that are already 1%+ above SPY are in consolidation territory, not continuation territory.

## Historical 2025 Results

| Metric | Value |
|---|---|
| Total return | -9.66% |
| Monthly return | -0.84% |
| Sharpe ratio | -1.80 |
| Max drawdown | -12.57% |
| Win rate | 38.6% |
| Profit factor | 0.88 |

## Decision

**[x] Reject** — RS longs are structurally unprofitable at 1m resolution with 1% entry threshold. Adding them damages the strong short-side performance. The cross-regime challenge requires a different approach than symmetric RS.

## Next Step

Run 031: RS short-only (028 base) with leverage 2× to push monthly returns above 2%. This is the final optimization of our proven 2026 edge. The cross-regime problem is acknowledged as unsolved in this series.