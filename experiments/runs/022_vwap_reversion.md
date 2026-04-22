# Run 022_vwap_reversion

**Date:** 2026-04-10
**Status:** [ ] In Progress  [x] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

VWAP Reversion fades intraday deviations from VWAP. When price dips 0.3% below VWAP it's "oversold" intraday and we buy expecting a snap-back; when it rises 0.3% above VWAP we short expecting a return to fair value. Works best in range-bound, low-trend days. Jan–Apr 2026 is a sustained downtrend — the hypothesis here is that even in a trending environment, intraday mean reversion around VWAP still occurs.

## Strategy Rules

- Calculate running VWAP from market open each day
- Go LONG when price falls 0.3% below VWAP (oversold intraday)
- Exit LONG when price returns to VWAP
- Go SHORT when price rises 0.3% above VWAP (overbought intraday)
- Exit SHORT when price returns to VWAP
- Stop loss: 0.4% from entry — applied immediately on next bar
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
| stop_pct | 0.4 |
| entry_end_hour | 14 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -7.44% |
| Monthly return | -1.91% |
| Sharpe ratio | -8.5 |
| Max drawdown | -7.44% |
| Fills | 2236 |
| Round trips | 1118 |
| Win rate | 50.6% |
| Profit factor | 0.61 |
| Expectancy | $-6.65 |
| Max consec losses | 8 |
| Final equity | $92,562.58 |

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

- Win rate is 50.6% — above 50%, meaning more than half of trades are winners. But PF is 0.61, which means losses are ~1.6× the size of wins. Classic mean reversion failure mode in a trending market.
- Why losses are bigger: in a downtrend, when price dips 0.3% below VWAP, it keeps falling (trend continuation, not mean reversion). The stop at 0.4% is hit frequently. Meanwhile, when price briefly rips above VWAP (short signal), it does revert — winning shorts. But the long side bleeds.
- Direction asymmetry: short VWAP deviations (price too far above → revert down) worked in this downtrend. Long deviations (price too far below → snap back) did not work. Short-only VWAP reversion might be worth testing.
- Historical 2025 is worse: -24.13%, Sharpe -9.99. Mean reversion is fundamentally the wrong regime assumption for both 2025 and 2026.
- Key lesson: VWAP Reversion requires a ranging/low-trend day. It cannot be applied blindly across all days. A regime filter (identify low-ATR or sideways days) would be required.

## Decision

**[x] Reject** — VWAP Reversion fails in a trending market. Win rate is deceptive (50.6%), but loss size > win size due to trend continuation. Requires ranging market conditions to work; Jan–Apr 2026 is firmly trending. Not worth revising without a proper ranging-day regime filter.

## Next Step

Test VWAP Momentum (trades WITH the VWAP deviation — momentum, not reversion). This should work better in a trending environment since we'd be riding breakouts from VWAP. Also test Gap Fill (023) for the gap-fade edge.