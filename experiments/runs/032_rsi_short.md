# Run 032_rsi_short

**Date:** 2026-04-11
**Status:** [ ] In Progress  [x] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

When intraday RSI hits extreme overbought levels (>70) on 1m bars, a stock has had a disproportionate run of up bars vs down bars. In a bearish session (SPY below VWAP), this local overbought spike is likely a temporary recovery rally that will exhaust and reverse. Short the spike, exit when RSI returns to neutral (50). SPY VWAP regime filter ensures this only fires on genuinely bearish days — in 2025 bull market (SPY mostly above VWAP), the filter should block nearly all trades → near-flat 2025 → acceptable cross-regime profile.

**Why it fails**: Fatal R:R asymmetry. The RSI-based exit (RSI drops from 70 to 50) only captures a small % move — perhaps 0.3-0.7% from entry. But the stop is 1.5%. With WR 46.6%, average win is ~0.4% and average loss is ~0.8% → PF ≈ 0.62. This is not viable regardless of regime. The signal idea has merit (overbought in downtrend) but the exit mechanism is wrong.

## Strategy Rules

- Intraday RSI(14) — state resets every session at open
- SHORT entry when RSI > 70.0 (overbought spike)
- LONG entry when RSI < 25.0 (oversold flush)
- Exit SHORT when RSI drops below 50.0 (momentum exhausted)
- Exit LONG when RSI rises above 45.0
- Stop loss: 1.5% from entry
- Direction: short_only
- SPY VWAP regime filter — only short on bearish sessions, only long on bullish sessions
- No new entries after 13:00 ET
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
| rsi_period | 14 |
| overbought | 70.0 |
| oversold | 25.0 |
| exit_short_rsi | 50.0 |
| exit_long_rsi | 45.0 |
| stop_pct | 1.5 |
| direction | short_only |
| regime_filter | True |
| entry_end_hour | 13 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -1.23% |
| Monthly return | -0.31% |
| Sharpe ratio | -3.6 |
| Max drawdown | -1.24% |
| Fills | 528 |
| Round trips | 264 |
| Win rate | 46.6% |
| Profit factor | 0.62 |
| Expectancy | $-4.67 |
| Max consec losses | 13 |
| Final equity | $98,766.27 |

## Evaluation

Score against candidate criteria:

- [ ] Total return positive — FAILED (-1.23%)
- [ ] Monthly return ≥ 5% (target) — FAILED
- [ ] Sharpe ≥ 0.5 — FAILED (-3.6)
- [x] Max drawdown ≤ 25% — -1.24% (controlled)
- [x] Win rate ≥ 40% — 46.6%
- [ ] Profit factor ≥ 1.5 — 0.62 (terrible)
- [x] Round trips ≥ 15 — 264
- [x] All trades intraday (no overnight holds)
- [x] Tested on ≥ 2 symbols

Observations:

- **Fails 2026 primary (-1.23%, Sharpe -3.6)**: Even in 2026 downtrend, the strategy loses. RSI > 70 overbought is not a reliable short signal at 1m resolution in this dataset.
- **R:R catastrophe (PF 0.62)**: With stop=1.5% and RSI-based exit (capture when RSI returns to 50), average win is ~0.4% while average loss is ~0.65% (due to position sizing and slippage). Fundamental design flaw: exit mechanism doesn't guarantee favorable R:R.
- **Regime filter partially works in 2025**: In January 2025, equity was nearly flat (small drift from $100k). By June, equity reached $96.8k. By year end, -8.07%. Some 2025 sessions DO trigger shorts (SPY intraday dips below VWAP), and those shorts lose in the bull market. But the fill rate is much lower (~7 fills/day in 2025 vs 15 in 2026) — confirming the filter blocks most 2025 trades.
- **1m RSI is too noisy**: RSI > 70 on 14×1m bars = 14 minutes of relative strength. This is not a meaningful overbought signal — it's just 2-3 consecutive up bars in a row. More bars (30-60 min resolution) would make RSI more predictive.
- **Key insight for future**: If RSI overbought (5-min bars) is used as the ENTRY condition, combined with a % profit target (2×R, not RSI exit), it might work. The RSI gives direction bias; the % target gives the R:R structure. This was not tested due to the run limit.
- **Cross-regime profile**: 2025 -8.07% is still bad. While the filter reduces damage, the occasional 2025 bearish sessions that DO fire cause losses that compound to -8% over the year.

## Historical 2025 Results

| Metric | Value |
|---|---|
| Total return | -8.07% |
| Monthly return | -0.70% |
| Sharpe ratio | -5.8 |
| Max drawdown | -8.35% |
| Win rate | 45.6% |
| Profit factor | 0.45 |

## Decision

**[x] Reject** — RSI intraday short fails in both regimes. The fatal issue is the RSI-based exit mechanism which captures insufficient profit per win vs the stop loss size. Fix needed: use % profit target (2R) instead of RSI exit. Also: RSI at 1m resolution is too noisy; 5m RSI would be more reliable. These fixes could make RSI overbought shorts viable, but require a new experiment.

## Next Step

Next session: Test RSI overbought shorts with fixed % profit target (2R: stop 1%, TP 2%) instead of RSI exit. Use rsi_period=14 on 1m bars with entry only when RSI > 70 AND price is below SPY VWAP. The R:R fix is the critical change. Alternatively, port strategy to 5m bars where RSI has more predictive value.