# Run 029_rs_spy_decline

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [x] Revised  [ ] Promising

---

## Hypothesis

Extension of 028: add a second layer of bearish confirmation — SPY must be down ≥0.3% from day open (not just below its intraday VWAP). This filters out the common 2025 pattern where SPY briefly dips below VWAP mid-session on an otherwise bullish day. Hypothesis: only short when the broader market is genuinely declining from open, not just intraday wavering around VWAP.

**Why it's the wrong fix**: Filtering more aggressively reduces 2025 losses but also reduces 2026 trade count and returns. The SPY decline filter blocks 2026 sessions where SPY hasn't fallen 0.3% by 9:45 yet (even on ultimately bearish days). The issue isn't about filtering — it's about direction: a short-only strategy fundamentally cannot generate positive returns in a bull market.

## Strategy Rules

- Track each stock's % return from its own day open
- Compute Relative Strength (RS) = stock_return% - SPY_return%
- SHORT when RS < -1.0% (underperforming SPY — weak stock in weak market)
- LONG when RS > +1.0% (outperforming SPY — strong stock in strong market)
- Stop loss: 1.0% from entry
- Profit target: 2.0% from entry
- Direction: short_only
- SPY VWAP regime filter — only short on bearish sessions, only long on bullish
- SPY decline filter: SPY must be ≥0.3% below day open for shorts
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
| spy_decline_pct | 0.3 |
| entry_after_min | 15 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 1.89% |
| Monthly return | 0.47% |
| Sharpe ratio | 1.89 |
| Max drawdown | -1.65% |
| Fills | 516 |
| Round trips | 258 |
| Win rate | 49.2% |
| Profit factor | 1.28 |
| Expectancy | $7.34 |
| Max consec losses | 7 |
| Final equity | $101,894.83 |

## Evaluation

Score against candidate criteria:

- [x] Total return positive (+1.89%)
- [ ] Monthly return ≥ 5% (target) — 0.47% actual
- [x] Sharpe ≥ 0.5 — 1.89 (good, but lower than 028's 2.91)
- [x] Max drawdown ≤ 25% — only -1.65%
- [x] Win rate ≥ 40% — 49.2%
- [ ] Profit factor ≥ 1.5 — 1.28 actual
- [x] Round trips ≥ 15 — 258
- [x] All trades intraday (no overnight holds)
- [x] Tested on ≥ 2 symbols

Observations:

- **Filter is a double-edged sword**: 2026 Sharpe dropped from 2.91 (028) to 1.89 — the 0.3% decline requirement skips many profitable 2026 sessions where SPY hasn't yet fallen 0.3% by 9:45 (but the day ultimately goes down). Trade count fell from 415 to 258 round trips.
- **2025 partially improved**: -5.66% → -3.24%. The filter blocked many 2025 intraday dip sessions, but not all — Q4 2025 saw genuine volatility that generated short signals even with the filter.
- **258 round trips**: Too few for the monthly return target. The filter restricts trade frequency too much — 029 makes less in 2026 than 028 while still losing in 2025.
- **Fundamental insight confirmed**: Adding more short-side filters is diminishing returns. The only real fix for 2025 is to ADD LONG SIGNALS in bullish conditions — not restrict short signals further.
- **Max consec losses only 7**: Excellent! The stricter filter means fewer runs of bad luck. But the reduced trade count means less absolute gain.
- **Net verdict vs 028**: 028 is strictly better in 2026 (2.91 vs 1.89 Sharpe, 0.99% vs 0.47% monthly). 029 is slightly better in 2025 (-3.24% vs -5.66%). The overall picture: 028 for bear market, neither is cross-regime.

## Historical 2025 Results

| Metric | Value |
|---|---|
| Total return | -3.24% |
| Monthly return | -0.27% |
| Sharpe ratio | -0.72 |
| Max drawdown | -6.8% |
| Win rate | 39.5% |
| Profit factor | 0.88 |

## Decision

**[x] Revise** — SPY decline filter approach is a dead end. The right fix is symmetric RS (both directions): long strong stocks when SPY is bullish (2025 sessions), short weak stocks when SPY is bearish (2026 sessions). The VWAP regime filter already handles this correctly — we just need to re-enable longs with the improved parameters.

## Next Step

Run 030: RS both directions, threshold=1.0%, stop=1.0%, TP=2.0%, entry_after_min=15, regime_filter=True. This tests whether RS longs (strong stocks vs SPY on bullish days) work with the improved entry parameters. If yes, this is the cross-regime strategy we've been searching for.