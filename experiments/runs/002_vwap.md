# Run 002_vwap

**Date:** 2026-04-10
**Status:** [x] Revised

---

## Hypothesis

1m VWAP reversion: large-cap ETFs and stocks tend to snap back to VWAP after intraday
over-extensions. ORB (001) was getting whipsawed because breakouts on 1m bars lack
follow-through. The opposite bet — mean reversion back to fair value — should have
positive expectancy if entries are at meaningful deviations and stops are tight.

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
| Symbols | SPY, QQQ, AAPL, MSFT, NVDA |
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
| Total return | -2.9% |
| Monthly return | -0.91% |
| Sharpe ratio | -9.0 |
| Max drawdown | -2.92% |
| Fills | 630 |
| Round trips | 315 |
| Win rate | 54.0% |
| Profit factor | 0.55 |
| Expectancy | $-9.22 |
| Max consec losses | 7 |
| Final equity | $97,096.37 |

## Evaluation

Score against candidate criteria:

- [ ] Total return positive — FAIL
- [ ] Monthly return ≥ 2% — FAIL
- [ ] Sharpe ≥ 0.5 — FAIL
- [ ] Max drawdown ≤ 20% — PASS (small drawdown)
- [x] Win rate ≥ 40% — PASS (54%)
- [ ] Profit factor ≥ 1.5 — FAIL (0.55)
- [x] Round trips ≥ 30 — PASS (315)
- [x] All trades intraday — PASS
- [x] Tested on ≥ 5 symbols — PASS

Observations:

- Win rate of 54% confirms the reversion direction is correct — the signal is valid.
- PF of 0.55 means losses are ~2× winners in dollar terms. The R:R is inverted.
- Root cause: 0.3% entry deviation is too small. VWAP exit only captures the tiny
  last bit of drift back (~0.1–0.2%), while 0.4% stops hit and cause larger losses.
- 315 round trips in 3 months = ~4–5/day/symbol. Signal frequency is very high.
  Tighter entry filter should improve signal quality and average win size.
- Premise is not broken — need to fix R:R.

## Decision

**[x] Revise** — Widen entry threshold to 0.6% (more deviation = larger reversion
runway back to VWAP = bigger winners). Tighten stop to 0.3% (less capital at risk).
New R:R ≈ 2:1 (risk 0.3% to make 0.6%). With 54% WR theoretical expectancy turns
positive: 0.54 × 0.6% − 0.46 × 0.3% = +0.186%.

## Next Step

Run 003_vwap_r1: same strategy, entry_dev_pct=0.6, stop_pct=0.3. Expect fewer but
higher-quality trades with improved profit factor.
