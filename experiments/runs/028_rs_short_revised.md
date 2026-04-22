# Run 028_rs_short_revised

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [x] Revised  [ ] Promising

---

## Hypothesis

Revision of run 024 (RS both directions, threshold 0.5%). Key changes: (1) short-only to eliminate longs that failed in 2025, (2) raise RS threshold to 1.0% to filter weak signals, (3) add 2% profit target (2R) to lock in gains, (4) delay entry to 9:45 (15 min) so relative momentum is confirmed rather than reacting to the first bar's noise.

Hypothesis: stocks underperforming SPY by 1%+ at 9:45 in a bearish SPY session have confirmed directional momentum — the 15-min warm-up period filters out opening auction noise. The 1:2 R:R (1% stop / 2% target) provides enough edge even at a 40% win rate.

## Strategy Rules

- Track each stock's % return from its own day open
- Compute Relative Strength (RS) = stock_return% - SPY_return%
- SHORT when RS < -1.0% (underperforming SPY — weak stock in weak market)
- LONG when RS > +1.0% (outperforming SPY — strong stock in strong market)
- Stop loss: 1.0% from entry
- Profit target: 2.0% from entry
- Direction: short_only
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
| direction | short_only |
| regime_filter | True |
| entry_after_min | 15 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 4.01% |
| Monthly return | 0.99% |
| Sharpe ratio | 2.91 |
| Max drawdown | -1.9% |
| Fills | 830 |
| Round trips | 415 |
| Win rate | 47.7% |
| Profit factor | 1.39 |
| Expectancy | $9.66 |
| Max consec losses | 16 |
| Final equity | $104,008.46 |

## Evaluation

Score against candidate criteria:

- [x] Total return positive (+4.01%)
- [ ] Monthly return ≥ 5% (target) — 0.99% actual
- [x] Sharpe ≥ 0.5 — **2.91** (outstanding)
- [x] Max drawdown ≤ 25% — only -1.9%
- [x] Win rate ≥ 40% — 47.7%
- [ ] Profit factor ≥ 1.5 — 1.39 actual
- [x] Round trips ≥ 15 — 415
- [x] All trades intraday (no overnight holds)
- [x] Tested on ≥ 2 symbols

Observations:

- **2026 Sharpe 2.91 is exceptional**: Matches 014's Sharpe 2.87 (our previous best). Very consistent returns with only -1.9% drawdown — the tightest DD of any experiment so far.
- **Win rate improved to 47.7%**: The 1% threshold filters noise. Raising threshold from 0.5% to 1.0% increased win rate by ~7pp vs 024 (40.7% → 47.7%). Higher RS threshold = higher quality signals.
- **PF 1.39 still below 1.5 target**: The 2:1 R:R (1% stop / 2% TP) should produce PF > 1.5 at 47.7% WR. But with 16 consecutive losses max, there are streaky periods where the market structure changes and the signal breaks down temporarily.
- **Monthly return too low (0.99%)**: 415 round trips in 69 trading days = 6 trades/day. The trade count is limited by the 1% RS threshold (higher threshold → fewer setups). Need more trades OR bigger winners.
- **2025 failure (-5.66%, Sharpe -1.12)**: Root cause: even with SPY VWAP regime filter, there are days in 2025 where SPY briefly trades below its VWAP (intraday pullbacks on otherwise bullish days). On those days, the strategy shorts stocks that lag SPY — but the bull market's upward pressure overcomes the short-term relative weakness, hitting the 1% stop before the 2% target.
- **The fix**: Require SPY to be not just below its VWAP but also **down X% from the day open** before allowing shorts. This would gate out most 2025 sessions (which are generally positive from open) while keeping all 2026 bearish days active.

## Historical 2025 Results

| Metric | Value |
|---|---|
| Total return | -5.66% |
| Monthly return | -0.48% |
| Sharpe ratio | -1.12 |
| Max drawdown | -10.3% |
| Win rate | 37.8% |
| Profit factor | 0.88 |

## Decision

**[x] Revise** — Add SPY absolute decline filter: only short when SPY is also down ≥0.3% from day open. This creates a two-layer bearish gate: (1) SPY below VWAP, AND (2) SPY down ≥0.3% from open. Layer 2 eliminates most 2025 intraday dips on otherwise bullish days. Also try increasing leverage to 2× to hit the 2%/month target if PF improves.

## Next Step

Run 029: RS short-only + SPY decline filter (spy_decline_pct=0.3). Keep all 028 params (threshold=1.0, stop=1.0%, TP=2.0%, entry_after_min=15). Add `spy_decline_pct` to RelativeStrengthStrategy to require SPY itself to be down ≥0.3% from open before any short fires.