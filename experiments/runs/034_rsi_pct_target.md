# Run 034_rsi_pct_target

**Date:** 2026-04-11
**Status:** [ ] In Progress  [x] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

Run 032 (RSI overbought short, RSI-based exit) had PF 0.62 because exits at RSI=50 captured ~0.4% avg win vs 1.5% stop. Fix: replace the RSI exit with a fixed % profit target (2% TP, 1% stop = 2R ratio). At 40%+ win rate, 2R gives PF ~1.5+. SPY VWAP regime filter (default on) restricts shorts to bearish sessions, matching the bear-market environment.

## Strategy Rules

- Intraday RSI(14) — state resets every session at open
- SHORT entry when RSI > 70.0 (overbought spike)
- LONG entry when RSI < 25.0 (oversold flush)
- Exit SHORT when RSI drops below 55.0 (momentum exhausted)
- Exit LONG when RSI rises above 45.0
- Stop loss: 1.0% from entry
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
| exit_short_rsi | 55.0 |
| exit_long_rsi | 45.0 |
| stop_pct | 1.0 |
| profit_target_pct | 2.0 |
| direction | short_only |
| regime_filter | True |
| entry_end_hour | 13 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -0.41% |
| Monthly return | -0.1% |
| Sharpe ratio | -1.06 |
| Max drawdown | -1.74% |
| Fills | 528 |
| Round trips | 264 |
| Win rate | 46.2% |
| Profit factor | 0.93 |
| Expectancy | $-1.55 |
| Max consec losses | 6 |
| Final equity | $99,591.11 |

## Evaluation

Score against candidate criteria:

- [ ] Total return positive (-0.41% — negative)
- [ ] Monthly return ≥ 5% (-0.10%)
- [ ] Sharpe ≥ 0.5 (-1.06 — negative)
- [x] Max drawdown ≤ 25% (-1.74% small)
- [x] Win rate ≥ 40% (46.2%)
- [ ] Profit factor ≥ 1.5 (0.93 — below 1.0)
- [x] Round trips ≥ 15 (264)
- [x] All trades intraday
- [x] Tested on ≥ 2 symbols (17)

Observations:

The % profit target fix failed. Despite 46.2% win rate, PF is 0.93 — mathematically, with 2% TP and 1% stop, PF should be ~1.72. That it's only 0.93 reveals the avg win is ~1%, not 2%. Most winning trades are not reaching the 2% TP — they're being closed by EOD flatten at small profits, or positions are opened too late in the day to allow sufficient time for 2% move. The fundamental problem: RSI > 70 on 1m bars during a bearish session signals a brief counter-rally. These counter-rallies often reverse but by less than 2% before EOD, giving small gains. Meanwhile the stop at 1% is occasionally hit when the counter-rally continues. Net: the "2R" ratio doesn't materialize in practice because intraday TP is rarely reached. RSI overbought at 1m is a very noisy signal that doesn't produce consistent 2% reversals.

**2025 performance** (-7.16%, Sharpe -2.49) confirms this isn't regime-specific: the strategy just doesn't work at 1m resolution in either market. RSI overbought short must be abandoned at this timeframe.

## Decision

**[x] Reject** — RSI overbought short at 1m is fundamentally broken. The % profit target fix doesn't help because avg win stays at ~1% due to EOD closes before TP, while losses hit 1% stop regularly. No further revisions to this approach.

## Next Step

035: EMA trend pullback long-only with SPY VWAP regime filter. Tests whether intraday EMA pullback entries within a confirmed uptrend can capture bull-market gains (2025 +23% SPY). If near-flat in 2026 (regime filter blocks most entries) and profitable in 2025, this becomes the bull complement to 031 RS short.