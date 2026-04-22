# Run 033_rs_trend_filter

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [x] Revised  [ ] Promising

---

## Hypothesis

031 (RS short 2×) achieves Sharpe 3.15 in the 2026 bear market but loses -8.58% in 2025. The VWAP intraday filter blocks individual bearish sessions but not sustained bull-market weeks. Adding a multi-day trend gate (only short when SPY < its close 5 trading days ago) should naturally skip 2025 bull runs while preserving 2026 bear signals — in a downtrend, SPY will usually sit below its recent close.

## Strategy Rules

- Track each stock's % return from its own day open
- Compute Relative Strength (RS) = stock_return% - SPY_return%
- SHORT when RS < -1.0% (underperforming SPY — weak stock in weak market)
- LONG when RS > +1.0% (outperforming SPY — strong stock in strong market)
- Stop loss: 1.0% from entry
- Profit target: 2.0% from entry
- Direction: short_only
- SPY VWAP regime filter — only short on bearish sessions, only long on bullish
- SPY multi-day trend filter: only short when SPY < close 5 days ago
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
| spy_trend_days | 5 |
| entry_after_min | 15 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 3.44% |
| Monthly return | 0.85% |
| Sharpe ratio | 1.72 |
| Max drawdown | -4.14% |
| Fills | 608 |
| Round trips | 304 |
| Win rate | 43.8% |
| Profit factor | 1.33 |
| Expectancy | $11.31 |
| Max consec losses | 13 |
| Final equity | $103,437.64 |

## Evaluation

Score against candidate criteria:

- [x] Total return positive (+3.44%)
- [ ] Monthly return ≥ 5% (0.85% — well below target)
- [x] Sharpe ≥ 0.5 (1.72)
- [x] Max drawdown ≤ 25% (-4.14%)
- [x] Win rate ≥ 40% (43.8%)
- [ ] Profit factor ≥ 1.5 (1.33 — below target)
- [x] Round trips ≥ 15 (304)
- [x] All trades intraday
- [x] Tested on ≥ 2 symbols (17)

Observations:

The 5-day trend filter successfully neutralised the 2025 bull-market problem: from -8.58% to nearly flat (+0.19%). But it came at a steep cost — 2026 monthly return dropped from 1.65% to 0.85%, Sharpe from 3.15 to 1.72, and PF from above 1.5 to 1.33. The filter is over-blocking: in Jan-Apr 2026 the market is broadly declining but with frequent bounce days where SPY > its 5-day-ago close. Those bounce days still have stocks showing relative weakness vs SPY intraday (VWAP confirms bearish session) but the 5-day filter refuses entry. Net effect: filter blocks too many valid signals within the confirmed 2026 downtrend. The VWAP intraday filter already handles day-level regime — the additional multi-day gate creates redundancy that costs more than it saves.

## Decision

**[ ] Reject** — not rejected; the cross-regime improvement is real  
**[x] Revise** — direction: the multi-day trend filter concept is correct but 5 days is too tight. Either try a longer lookback (20-day SMA filter) or accept that the regime gate should come from a higher-level switch (SPY weekly trend) rather than a rolling N-day comparison at the daily bar level.

## Next Step

034: RSI overbought short with % profit target (2R: 1% stop, 2% TP). This addresses a completely different failure mode — R:R on RSI exits. If RSI-based exits can be replaced with a fixed % target, the strategy might work in any regime (overbought spikes happen in bull AND bear markets).