# Run 035_ema_long_regime

**Date:** 2026-04-11
**Status:** [ ] In Progress  [x] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

EMA pullback entries (close crosses back above EMA9 within EMA9>EMA21 uptrend) capture the "consolidate and resume" pattern in trending stocks. Using the SPY VWAP regime filter (long only on bullish sessions) should focus entries on genuine up-trending environments. If this works in 2025 (bull +23%), it becomes the bull complement to 031's bear-market RS shorts.

## Strategy Rules

- Trend filter: EMA9 vs EMA21 on 1m bars (continuous)
- Trade LONG pullbacks only (EMA9 > EMA21 required)
- LONG entry: EMA9 > EMA21 AND close crosses up through EMA9 (pullback bounce)
- SHORT entry: EMA9 < EMA21 AND close crosses down through EMA9 (pullback rejection)
- Stop loss: 0.3% from entry
- Profit target: 2.0× stop distance (0.60% from entry)
- No new entries before 9:45 ET (warm-up) or after 14:00 ET
- One trade per asset per day — no re-entry
- EOD flatten at 15:55 ET by engine

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | QQQ, SPY, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| fast_period | 9 |
| slow_period | 21 |
| stop_pct | 0.3 |
| profit_mult | 2.0 |
| entry_end_hour | 14 |
| direction | long_only |
| regime_filter | True |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -6.83% |
| Monthly return | -1.75% |
| Sharpe ratio | -8.1 |
| Max drawdown | -7.06% |
| Fills | 2030 |
| Round trips | 1015 |
| Win rate | 33.0% |
| Profit factor | 0.58 |
| Expectancy | $-6.73 |
| Max consec losses | 16 |
| Final equity | $93,166.63 |

## Evaluation

Score against candidate criteria:

- [ ] Total return positive (-6.83% — negative)
- [ ] Monthly return ≥ 5% (-1.75%)
- [ ] Sharpe ≥ 0.5 (-8.1 — deeply negative)
- [x] Max drawdown ≤ 25% (-7.06%)
- [ ] Win rate ≥ 40% (33.0% — well below)
- [ ] Profit factor ≥ 1.5 (0.58)
- [x] Round trips ≥ 15 (1015 — way too many)
- [x] All trades intraday
- [x] Tested on ≥ 2 symbols

Observations:

Catastrophic failure in both regimes. 1015 round trips in 3 months means ~11 trades/day — nearly the maximum for 17 symbols × 1/day. The EMA pullback condition at 1m fires on almost every symbol every session. Even on bullish sessions (SPY above VWAP), 67% of entries are losers. Root cause: the 0.3% stop is smaller than typical 1m candle ranges for high-volatility stocks. A pullback to EMA9 and a 1m close above it does not predict a profitable 0.3% move; the stock can immediately reverse and hit the stop within 1-2 bars. The signal is too noisy at 1m — EMA9 crosses at minute frequency are essentially random. **2025 performance is also terrible (-18.4%, Sharpe -6.85)**, disproving the hypothesis that EMA longs work in bull markets at 1m. The signal quality is the same regardless of regime. The regime filter (SPY VWAP) was irrelevant — sessions with SPY above VWAP in a bull market still have individual stocks oscillating around their EMAs at 1m.

**Note on stop width**: 0.3% stop was chosen because it was the default, but for a 1m EMA pullback entry the natural price movement from the touch point is much less than 0.3% on high-volatility stocks. Widening to 1% would reduce noise but make individual losses larger, likely just as bad.

## Decision

**[x] Reject** — EMA trend pullback is fundamentally broken at 1m resolution due to signal noise. Too many trades, win rate 33%, PF 0.58. Not worth revising — the 1m timeframe for EMA crossovers is inherently too noisy regardless of stop width or regime filter. Abandon EMA trend strategy for this framework.

## Next Step

036: RS short-only with 20-day SPY trend filter — test if a longer lookback is more surgical. The 5-day filter (033) blocked too many valid 2026 signals while fixing 2025. A 20-day filter (SPY must be below its close 20 trading days ago) approximates "SPY below its one-month average" — this should fire more consistently in a sustained bear market without blocking multi-week rally windows.