# Run 026_momentum_spike

**Date:** 2026-04-11
**Status:** [ ] In Progress  [x] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

Volume is the footprint of institutional participation. When a stock breaks its 10-bar rolling high/low on 2× its 20-bar average volume, this signals genuine institutional conviction rather than a noise breakout. The hypothesis is that high-volume breakouts have a higher probability of continuation because they represent real demand/supply imbalances, not random price fluctuation. SPY VWAP regime filter ensures we only go long in bullish sessions and short in bearish sessions, providing directional alignment.

**Why it fails here:** The 10-bar rolling high on 1m bars represents only a ~10 minute range. In a typical trading session, price breaks 10-minute highs/lows constantly. Even with 2× volume confirmation, this triggers far too frequently (1112 round trips = ~16/day across 19 symbols). The "breakout" is more often a mid-session push that immediately reverses, and the 1.5% stop is generous enough to create large losses when the reversal is sharp. The strategy conflates activity with conviction.

## Strategy Rules

- Rolling 20-bar average volume baseline
- Rolling 10-bar high/low breakout levels
- Enter LONG when volume > 2.0× avg AND price breaks 10-bar high
- Enter SHORT when volume > 2.0× avg AND price breaks 10-bar low
- Stop loss: 1.5% from entry
- Direction: both
- SPY VWAP regime filter active — only enter in SPY trend direction
- No new entries after 14:00 ET
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
| vol_window | 20 |
| vol_mult | 2.0 |
| breakout_window | 10 |
| stop_pct | 1.5 |
| direction | both |
| regime_filter | True |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -4.73% |
| Monthly return | -1.19% |
| Sharpe ratio | -2.2 |
| Max drawdown | -8.79% |
| Fills | 2224 |
| Round trips | 1112 |
| Win rate | 40.3% |
| Profit factor | 0.88 |
| Expectancy | $-4.25 |
| Max consec losses | 14 |
| Final equity | $95,273.74 |

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

- **Fails both regimes**: Primary 2026: -4.73%, Sharpe -2.2. Historical 2025: -26.04%, Sharpe -2.88, drawdown -28.46%. Worse in 2025 than 2026 — the bull market punishes short entries especially hard.
- **High volume ≠ continuation**: At 1m resolution, a 2× volume spike on a 10-bar breakout does not reliably predict continuation. Intraday volume spikes are often caused by: (a) large orders hitting at resistance/support that then reverse, (b) stop-hunt flushes that immediately snap back, (c) algorithmic rebalancing not related to directional conviction.
- **Breakout window too short (10 bars = 10 min)**: A 10-minute high/low is a trivially small range in high-volatility stocks (TSLA, COIN, NVDA). Meaningful breakout levels need to be wider — e.g., the 30-min ORB or session VWAP ± bands.
- **2025 drawdown -28.46%**: Catastrophic. In a trending bull market, the regime filter allows longs (when SPY VWAP is bullish), but longs on 1m breakouts in a bull market are often at local tops. The short entries that slip through in bear-ish SPY sessions get crushed when the bull resumes.
- **1112 round trips (1m session)**: Over-trading is a significant factor. More trades = more friction and more opportunities for the negative edge to compound.
- **SPY regime filter insufficient**: The filter directs trades by session direction but doesn't prevent intraday whipsaws. The fundamental signal quality is too low for the filter to rescue.

## Historical 2025 Results

| Metric | Value |
|---|---|
| Total return | -26.04% |
| Monthly return | -2.45% |
| Sharpe ratio | -2.88 |
| Max drawdown | -28.46% |
| Win rate | 41.9% |
| Profit factor | 0.80 |

## Decision

**[x] Reject** — Volume spike breakout fails in both regimes. The 10-bar breakout window is too short and generates excessive noise signals. 1112 round trips compounds the negative edge. Even with SPY VWAP filter, signal quality is fundamentally insufficient for profitable trading. The strategy concept (volume confirmation for breakouts) could work with much wider breakout windows (e.g., day range, ORB range) but that is effectively an ORB variant.

## Next Step

Run 027: ORB Auto-Direction — SPY gap determines daily direction (gap-down → short ORB, gap-up → long ORB). This is the critical cross-regime test. If it works in both 2025 and 2026, it becomes the base for optimization.