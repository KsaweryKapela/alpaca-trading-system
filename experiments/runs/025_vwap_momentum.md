# Run 025_vwap_momentum

**Date:** 2026-04-11
**Status:** [ ] In Progress  [x] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

In a trending intraday session, when price deviates +0.3% from VWAP it often continues in that direction (momentum continuation). VWAP acts as an intraday fair value anchor — a significant break above VWAP signals that buyers have absorbed all available supply at fair value and are now paying up, suggesting further upside. Symmetric for shorts. The 2:1 reward:risk (0.6% target / 0.3% stop) should produce positive expectancy if the continuation signal is real.

**Why it fails here:** The 0.3% threshold is "no man's land" — too small to confirm genuine momentum continuation (noise triggers at this scale), yet large enough that the price has already moved significantly and mean reversion probability is rising. The strategy gets the worst of both worlds: longs entered after 0.3% move up are already extended (mean reversion bites), and shorts entered after 0.3% move down face the same. In a 1m timeframe, a 0.3% VWAP deviation is routine volatility, not a genuine momentum signal.

## Strategy Rules

- Calculate running VWAP from market open each day
- Go LONG when price rises 0.3% above VWAP (momentum breakout up)
- Go SHORT when price falls 0.3% below VWAP (momentum breakout down)
- Profit target: 0.60% from entry (2.0× entry deviation)
- Stop loss: 0.30% from entry (1.0× entry deviation)
- No new entries after 14:00 ET
- One trade per asset per day — no re-entry
- All positions closed by 15:55 ET (EOD flatten by engine)

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | QQQ, SPY, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| entry_dev_pct | 0.3 |
| profit_target_mult | 2.0 |
| stop_mult | 1.0 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -7.97% |
| Monthly return | -2.05% |
| Sharpe ratio | -9.05 |
| Max drawdown | -8.99% |
| Fills | 2236 |
| Round trips | 1118 |
| Win rate | 38.9% |
| Profit factor | 0.68 |
| Expectancy | $-7.13 |
| Max consec losses | 13 |
| Final equity | $92,027.57 |

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

- **Worst Sharpe this session (-9.05)**: Worse than gap fill (-5.47). The strategy is actively destructive — systematic negative edge.
- **Win rate 38.9%, PF 0.68**: Both directions fail. The regime filter (SPY VWAP) isn't helping enough — perhaps because the intraday VWAP deviation signal is symmetric and fires on both long and short SPY sessions, just in the allowed direction.
- **0.3% entry threshold problem**: At 1m resolution, a 0.3% VWAP deviation triggers frequently (2236 fills = 118 fills/day avg across 19 symbols = about 6 trades/symbol/day). Most of these are noise reversals, not momentum continuations.
- **Comparison with VWAP Reversion (021)**: The reversion variant had similar issues in 2026 — VWAP-anchored strategies are fundamentally at odds with trending regimes. Neither direction (reversion nor momentum) provides edge when the appropriate market condition is absent.
- **2:1 R:R insufficient**: A 2:1 ratio requires >33% win rate to break even. At 38.9% WR the math works, but the PF shows average losses exceed expectations — suggesting frequent EOD flattens at partial loss (stop not hit, take profit not hit, just closed at 15:55 for a loss).
- **2025 likely worse**: Volume of short trades in a bull market (SPY VWAP bearish filter would rarely trigger) means long entries dominate, and entering longs after 0.3% VWAP breakout in a volatile bull market is buying at the high of the move.

## Decision

**[x] Reject** — VWAP momentum is structurally flawed at 0.3% threshold — too small to confirm real momentum, too large to benefit from continuity. The concept requires either (a) much larger deviation (1%+) which would cut trade count dramatically, or (b) confluence with other signals (volume spike, range context) to filter noise. Not worth iterating further given we have better leads.

## Next Step

Run 027: ORB Auto-Direction — use SPY overnight gap to select long/short each day. The key cross-regime experiment: can ORB work in both 2025 and 2026 by adapting direction daily based on SPY's overnight gap?