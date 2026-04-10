# Run 005_vwap_mom

**Date:** 2026-04-10
**Status:** [x] Rejected

---

## Hypothesis

VWAP reversion has 58% WR but inverted payoff (tiny wins, big losses). Maybe Jan-Apr
2026 is a momentum regime — trade WITH deviations from VWAP. If price breaks above
VWAP by 0.3%, ride it upward; if below, ride downward. Fixed 2:1 target, 1:1 stop.

## Backtest Configuration

| Field | Value |
|---|---|
| entry_dev_pct | 0.3 |
| profit_target_mult | 2.0 |
| stop_mult | 1.0 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -2.93% |
| Monthly return | -0.92% |
| Sharpe ratio | -7.11 |
| Max drawdown | -3.15% |
| Win rate | 36.5% |
| Profit factor | 0.66 |
| Expectancy | $-9.31 |
| Round trips | 315 |

## Evaluation

- [ ] All major metrics — FAIL

Observations:

- WR dropped to 36.5% — momentum is wrong 63% of the time.
- This confirms reversion is directionally correct (58% WR). VWAP momentum is the
  inverse signal and unsurprisingly performs inversely.
- Payoff slightly better (PF 0.66, W/L ≈ 1.14) but 37% WR with 1:1 R:R is not enough.
- VWAP family fully explored. Problem isn't direction — it's payoff structure.
  Bar-delayed fills mean the 0.3% reversion target is smaller than execution noise.

## Decision

**[x] Reject** — Pivot to an entirely different signal type.

## Next Step

Gap Fill strategy. Overnight gaps on large-caps fill ~65% intraday. Natural hard target
(prev close), symmetric payoff, entry at gap size acts as stop reference.
Run 006_gap_fill.
