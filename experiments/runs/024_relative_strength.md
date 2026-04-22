# Run 024_relative_strength

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Track each stock's % return from its own day open
- Compute Relative Strength (RS) = stock_return% - SPY_return%
- SHORT when RS < -0.5% (underperforming SPY — weak stock in weak market)
- LONG when RS > +0.5% (outperforming SPY — strong stock in strong market)
- Stop loss: 1.0% from entry
- Direction: both
- SPY VWAP regime filter — only short on bearish sessions, only long on bullish
- Entry window: 5 min after open → 14:00 ET
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
| rs_threshold | 0.5 |
| stop_pct | 1.0 |
| direction | both |
| regime_filter | True |
| entry_after_min | 5 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 2.26% |
| Monthly return | 0.6% |
| Sharpe ratio | 0.92 |
| Max drawdown | -5.77% |
| Fills | 1952 |
| Round trips | 976 |
| Win rate | 40.7% |
| Profit factor | 1.07 |
| Expectancy | $2.32 |
| Max consec losses | 12 |
| Final equity | $102,263.13 |

## Evaluation

Score against candidate criteria:

- [ ] Total return positive
- [ ] Monthly return ≥ 5% (target)
- [ ] Sharpe ≥ 0.5 (daily annualised)
- [ ] Max drawdown ≤ 25%
- [ ] Win rate ≥ 40%
- [ ] Profit factor ≥ 1.5
- [ ] Round trips ≥ 15
- [ ] All trades intraday (no overnight holds)
- [ ] Tested on ≥ 2 symbols

Observations:

- **2026 primary works**: Sharpe 0.92, +2.26% — the first non-ORB strategy to clear the Sharpe 0.5 bar. In the downtrend, stocks lagging SPY (-0.5% RS) continue to underperform, making short signals profitable.
- **PF is weak (1.07)**: Win rate 40.7% with PF only 1.07 means average wins barely exceed average losses. The edge is real but thin. Monthly 0.6% is too low.
- **2025 fails (-4.2%, Sharpe -0.31)**: In 2025's bull environment, the strategy's longs (going long strong stocks vs SPY) aren't working well. Possible causes: (a) "strong" stocks at 9:35 may already be extended — bad entry timing; (b) 1% stop too tight for bull-market volatility; (c) the regime filter may not distinguish "trending up day" from "choppy up day" — range-bound bullish days don't have continuation momentum.
- **High fill count (976 RTs)**: Good sample. The strategy fires on many stocks each day.
- **Key insight**: RS momentum works better for shorts in a downtrend than for longs in a bull market. The asymmetry suggests short-only might be the reliable edge here.

## Decision

**[ ] Reject**  
**[x] Revise** — Short-only RS with tighter entry (RS threshold 1.0%), add 2R profit target (2% from entry since stop = 1%). Testing short-only should improve 2025 validation since we avoid long entries that caused losses. Also test with `entry_after_min=15` to ensure directional momentum has established before entry.

## Next Step

Run 028: RS short-only, RS threshold 1.0, stop 1.0%, TP 2.0%, entry_after_min=15. Hypothesis: shorting stocks that are significantly underperforming SPY (≥1%) at 9:45 in bearish SPY sessions captures confirmed downside momentum.