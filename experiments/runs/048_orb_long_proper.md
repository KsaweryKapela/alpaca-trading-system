# Run 048_orb_long_proper

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

039 (ORB long, stop=0.5%) failed with win rate 35.5% — stop too tight for volatile stocks. This run widens stops to 1.5% (stop) and 3% (target), preserving 2R ratio but giving natural price oscillation room. On bullish sessions (regime_filter=True), volatile high-beta stocks (NVDA, TSLA, COIN, AMD, PLTR, RIVN) should break above their opening range and trend. Entry cut-off at 10:00 ET to avoid late entries on weakening momentum.

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
- Stop loss: 1.5% from entry
- Exit: 3.0% profit target
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
| stop_pct | 1.5 |
| profit_target_pct | 3.0 |
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
| Total return | -2.83% |
| Monthly return | -0.71% |
| Sharpe ratio | -2.06 |
| Max drawdown | -4.35% |
| Fills | 574 |
| Round trips | 287 |
| Win rate | 39.7% |
| Profit factor | 0.74 |
| Expectancy | $-9.86 |
| Max consec losses | 8 |
| Final equity | $97,171.37 |

## Evaluation

Score against candidate criteria:

- [ ] Total return positive (-2.83% — negative)
- [ ] Monthly return ≥ 5% (-0.71%)
- [ ] Sharpe ≥ 0.5 (-2.06 — negative)
- [x] Max drawdown ≤ 25% (-4.35%)
- [ ] Win rate ≥ 40% (39.7%)
- [ ] Profit factor ≥ 1.5 (0.74)
- [x] Round trips ≥ 15 (287)
- [x] All trades intraday
- [x] Tested on ≥ 2 symbols (7)

Observations:

Wider stops (1.5%) made no difference — win rate 39.7% (up from 35.5% in 039 but still below 40%). Even 3% profit targets don't save the R:R when more than 60% of trades lose. The root cause is not stop width — it's entry timing. ORB long enters on the breakout of the opening range high (set at 9:30-9:45), which is already the highest point of the morning spike. Entry = buying the 15-minute spike high. In 2025 bull market (-2.71%, -0.23%/mo), even a year of 23% SPY gains couldn't rescue this entry timing. This pattern fails because opening range breakouts on 1m bars = late entries at exhaustion points.

## Decision

**[x] Reject** — ORB long is fundamentally broken at 1m, confirmed across two experiments (039, 048). The problem is not stop width, leverage, or symbol selection — it's that buying ORB highs at 9:45 = entering at the top of the morning volatility spike. Moving to a delayed-entry approach for the bull sleeve.

## Next Step

050: RS long with entry_after_min=60 (10:30 ET). If a stock is still outperforming SPY by 1%+ at 10:30, the morning spike has been absorbed and the trend is real.