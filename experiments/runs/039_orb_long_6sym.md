# Run 039_orb_long_6sym

**Date:** 2026-04-11
**Status:** [ ] In Progress  [x] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

014 (ORB short 6 symbols) achieved Sharpe 2.87. The bull counterpart: ORB long on the same class of high-volatility symbols (NVDA, TSLA, COIN, AMD, PLTR, RIVN). On bullish sessions (SPY above VWAP), these volatile stocks should continue upward after breaking above their 15-min opening range. SPY VWAP regime filter blocks longs on bearish sessions → near-flat in 2026.

## Strategy Rules

- Opening range: first 15 minutes establish the range
- Direction: long_only
- Macro regime filter: SPY below its daily VWAP
- SPY intraday decline filter: no SPY intraday decline filter
- Stock VWAP filter: no stock VWAP filter
- Gap filter: no gap filter
- Min range width filter: no min range width filter
- SHORT entry: breakdown below range_low (all active filters must pass)
- LONG entry: breakout above range_high (when direction allows)
- Stop loss: 0.5% from entry
- Exit: 1.0% profit target
- One trade per asset per day — no re-entry
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, NVDA, TSLA, COIN, AMD, PLTR, RIVN |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| range_minutes | 15 |
| stop_pct | 0.5 |
| profit_target_pct | 1.0 |
| direction | long_only |
| regime_filter | True |
| stock_vwap_filter | False |
| gap_filter_pct | 0.0 |
| max_trades_per_day | 1 |
| reentry_cooldown | 5 |
| spy_decline_pct | 0.0 |
| min_range_pct | 0.0 |
| auto_direction | False |
| spy_gap_threshold | 0.0 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -2.0% |
| Monthly return | -0.5% |
| Sharpe ratio | -3.38 |
| Max drawdown | -2.57% |
| Fills | 574 |
| Round trips | 287 |
| Win rate | 35.5% |
| Profit factor | 0.72 |
| Expectancy | $-6.98 |
| Max consec losses | 10 |
| Final equity | $97,997.27 |

## Evaluation

Score against candidate criteria:

- [ ] Total return positive (-2.0% — negative)
- [ ] Monthly return ≥ 5% (-0.5%)
- [ ] Sharpe ≥ 0.5 (-3.38 — negative)
- [x] Max drawdown ≤ 25% (-2.57%)
- [ ] Win rate ≥ 40% (35.5%)
- [ ] Profit factor ≥ 1.5 (0.72)
- [x] Round trips ≥ 15 (287)
- [x] All trades intraday
- [x] Tested on ≥ 2 symbols

Observations:

Fails in both markets. 2026: -2.0% despite most sessions blocked by regime filter. 2025: -6.84% despite the bull market. The issue: ORB long on volatile stocks at 0.5% stop is too tight — TSLA, COIN, NVDA regularly oscillate 1-2% within a single 1m bar. Buying above the ORB high = buying at a local morning peak → immediate pullback → stop hit. The 0.5% stop doesn't allow enough room for natural oscillation. Additionally, regime filter fires (SPY above VWAP) but individual stocks can still move against the ORB breakout direction. 35.5% win rate suggests ~2/3 of breakouts fail.

## Decision

**[x] Reject** — ORB long at 1m is broken by the same mechanism as 1m EMA longs: tight stops get hit by natural 1m price oscillation. Also, buying ORB high on volatile stocks = entering at the top of a 9:30-9:45 spike.

## Next Step

040: Switch to 5m bars. At 5m resolution, the RS signal should be cleaner and entry/exit timing more robust. Start with RS short-only at 5m to confirm 2026 performance holds, then test RS long at 5m to explore the bull-market hypothesis.