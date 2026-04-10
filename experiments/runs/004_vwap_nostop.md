# Run 004_vwap_nostop

**Date:** 2026-04-10
**Status:** [x] Rejected

---

## Hypothesis

Remove the hard stop from VWAP reversion to isolate signal quality. If WR stays ~54%+
and expectancy turns positive, the stop was the only problem. If it stays negative,
the signal has no exploitable edge in this market regime.

## Strategy Rules

- VWAP reversion, entry_dev_pct=0.3, stop effectively disabled (stop_pct=2.0)
- Exit only at VWAP target or EOD flatten

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, AAPL, MSFT, NVDA |
| entry_dev_pct | 0.3 |
| stop_pct | 2.0 (disabled) |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -2.81% |
| Monthly return | -0.88% |
| Sharpe ratio | -4.5 |
| Max drawdown | -2.83% |
| Win rate | 57.8% |
| Profit factor | 0.56 |
| Expectancy | $-8.91 |
| Round trips | 315 |

## Evaluation

- [ ] All major metrics — FAIL

Observations:

- WR improved to 57.8% without stop (was 54% with 0.4% stop) — direction is right.
- PF still 0.56. Even without stops, losses are large. Avg win ≈ 0.3% (back to VWAP),
  avg loss ≈ whatever the EOD flatten captures on a trending day.
- W/L ratio ≈ 0.41: losers are ~2.4× bigger than winners on average.
- This is structurally inverted: tiny capped wins (revert to VWAP = 0.3% gain), large
  uncapped losses (trending days run 1-2%+ without returning to VWAP before EOD).
- Conclusion: Jan-Apr 2026 is a MOMENTUM/TRENDING regime. VWAP reversion
  fundamentally mis-bets the regime. The 58% WR is actually evidence FOR momentum:
  58% of deviations continue further away from VWAP, not back to it.

## Decision

**[x] Reject** — VWAP reversion is exhausted. 3 variants, all negative. The
structural problem is regime mismatch: trending market, mean-reversion strategy.

## Next Step

Flip the bet: VWAP MOMENTUM. Trade WITH the deviation:
- Long when price > VWAP * (1 + dev%) — ride upward momentum
- Short when price < VWAP * (1 - dev%) — ride downward momentum
- Fixed profit target at 2× deviation (2:1 R:R), stop at 1× deviation
Run 005_vwap_mom.
