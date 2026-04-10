# Run 003_vwap_r1

**Date:** 2026-04-10
**Status:** [x] Revised

---

## Hypothesis

Revision of 002: keep VWAP reversion premise but fix R:R. Entry at 0.6% deviation
gives more room to VWAP target (bigger winners). Tighter stop at 0.3% (less risk).
Expected R:R ≈ 2:1. With the 54% WR from 002 this should turn profitable.

## Strategy Rules

- Calculate running VWAP from market open each day
- Go LONG when price falls 0.6% below VWAP
- Exit LONG when price returns to VWAP
- Go SHORT when price rises 0.6% above VWAP
- Exit SHORT when price returns to VWAP
- Stop loss: 0.3% from entry
- No new entries after 14:00 ET
- One trade per asset per day — no re-entry
- All positions closed by 15:55 ET (EOD flatten by engine)

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, AAPL, MSFT, NVDA |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| entry_dev_pct | 0.6 |
| stop_pct | 0.3 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -1.52% |
| Monthly return | -0.48% |
| Sharpe ratio | -4.61 |
| Max drawdown | -1.52% |
| Fills | 468 |
| Round trips | 234 |
| Win rate | 42.7% |
| Profit factor | 0.72 |
| Expectancy | $-6.48 |
| Max consec losses | 8 |
| Final equity | $98,483.56 |

## Evaluation

- [ ] Total return positive — FAIL
- [ ] Monthly return ≥ 2% — FAIL
- [ ] Sharpe ≥ 0.5 — FAIL
- [x] Max drawdown ≤ 20% — PASS
- [ ] Win rate ≥ 40% — BORDERLINE (42.7%)
- [ ] Profit factor ≥ 1.5 — FAIL (0.72)
- [x] Round trips ≥ 30 — PASS (234)
- [x] All trades intraday — PASS
- [x] Tested on ≥ 5 symbols — PASS

Observations:

- Win rate DROPPED from 54% to 42.7% with wider entry. This is the key finding.
- At 0.6% from VWAP, the market is often in a momentum continuation — not reverting.
- The R:R assumption was correct (PF improved 0.55→0.72) but the WR assumption failed:
  wider deviation entries don't catch better reversions, they catch momentum moves.
- Optimal signal appears to be tight entry (0.3%) but the stop is eating the profit.

## Decision

**[x] Revise** — Test the pure hypothesis: does VWAP reversion at 0.3% work at all
if we remove the hard stop? Run with stop_pct=2.0 (effectively no stop, EOD flatten
only). If WR returns to 54%+ and expectancy turns positive, the stop placement is the
only problem to solve.

## Next Step

Run 004_vwap_nostop: entry_dev_pct=0.3, stop_pct=2.0. Isolate signal quality from
stop-placement noise.
