# Run 052_vwap_reclaim_std

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [x] Revised  [ ] Promising

---

## Hypothesis

All prior long attempts (RS long, ORB long, EMA trend) entered at or near the morning momentum spike top. New approach: enter at the BOTTOM of a retracement. In bullish sessions, stocks above VWAP that pull back to VWAP and reclaim it represent the "institutional reload" — strong hands accumulated at open, shook out weak longs at VWAP, then resumed the uptrend. Entry = bottom of pullback, not top of spike. Stop=1%, target=2% (2R). SPY must be up >0.5% from open to confirm genuine bull session.

## Strategy Rules

- Track each stock's intraday VWAP (cumulative typical price × volume)
- Bullish session: SPY above VWAP AND SPY up >0.5% from open
- State machine per symbol:
-   Phase 1: stock crosses above VWAP (after 9:45 warmup) → mark was_above_vwap
-   Phase 2: stock crosses back below VWAP → mark had_pullback (shakeout)
-   Phase 3: stock reclaims VWAP (crosses from below → above) → ENTRY
- Entry only after pullback confirmed (not the initial rise above VWAP)
- Stop loss: 1.0% below entry
- Profit target: 2.0% above entry
- Entry window: 9:45 ET → 13:00 ET
- One trade per symbol per day
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| stop_pct | 1.0 |
| profit_target_pct | 2.0 |
| spy_min_move_pct | 0.5 |
| entry_end_hour | 13 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 1.34% |
| Monthly return | 0.34% |
| Sharpe ratio | 2.16 |
| Max drawdown | -0.9% |
| Fills | 318 |
| Round trips | 159 |
| Win rate | 47.8% |
| Profit factor | 1.52 |
| Expectancy | $8.45 |
| Max consec losses | 4 |
| Final equity | $101,344.07 |

## Evaluation

Score against candidate criteria:

- [x] Total return positive (+1.34%)
- [ ] Monthly return ≥ 5% (0.34% — too low)
- [x] Sharpe ≥ 0.5 (2.16)
- [x] Max drawdown ≤ 25% (-0.9%)
- [x] Win rate ≥ 40% (47.8%)
- [x] Profit factor ≥ 1.5 (1.52)
- [x] Round trips ≥ 15 (159)
- [x] All trades intraday
- [x] Tested on ≥ 2 symbols (17)
- [~] **2025: -3.77%** (losing in bull market — cross-regime problem unresolved)

Observations:

**Split personality**: The strategy HAS genuine edge in 2026 (Sharpe 2.16, PF 1.52, WR 47.8%, max consec losses only 4) but LOSES in 2025 (-3.77%, PF 0.62, Sharpe -2.07). This is paradoxical — a bullish-session-only strategy should work better in a bull year. Root cause hypothesis: In 2026's bear market, the rare bullish sessions are HIGH CONVICTION up days where VWAP reclaims have strong follow-through. In 2025's bull market, SPY up >0.5% from open is a near-daily occurrence → too many signals with lower individual quality. 2025 has 432 round trips (vs 159 in 2026) — the strategy fires >2.7× more often in 2025 but each signal is weaker. The 0.5% SPY threshold is too low for 2025's persistent bullishness.

Fix: raise SPY threshold to 1.0%. This should:
- 2026: keep the strong conviction bull days (they're often >1% anyway)
- 2025: reduce trade count dramatically, filtering out routine sessions

## Decision

**[x] Revise** — SPY filter too loose for 2025. The edge exists (proven by 2026 quality) but 0.5% threshold creates noise in bull years. Try spy_min_move_pct=1.0 in 053.

## Next Step

053: Same VWAP reclaim, spy_min_move_pct=1.0. Only enter when SPY is up >1% from open — strong directional conviction. Should reduce 2025 trade count significantly.