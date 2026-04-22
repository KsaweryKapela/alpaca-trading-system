# Run 236_gm_base

**Date:** 2026-04-13
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === GAPPER SCAN (every morning) ===
- Gap threshold: 1.5% - 15.0%
- Confirm at 9:30+30min
- Max positions: 6
- === ENTRY ===
- Gap-up confirmed (above open) → LONG
- Gap-down confirmed (below open) → SHORT
- Gap faded → SKIP
- Target: 2.0x stop | Max stop: 3.0%
- Direction: both

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP, AVGO, CRM, UBER, LLY, MA, COST, GOOG, INTC, PYPL, SQ, SNAP, V, HD, MU, QCOM, ABNB, DIS, LOW, TGT, NKE, SBUX, XOM, CVX, COP, PFE, ABBV, MRK, WMT, AMGN, GS, MS, C, BAC, CAT, DE, UPS, PANW, CRWD, NET, MSTR, MARA, SMCI, ARM, DELL, SOFI, HOOD, DKNG, RBLX |
| Date range | 2026-01-01 → 2026-04-30 |
| Interval | 1m |
| Leverage | 3.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| min_gap_pct | 1.5 |
| max_gap_pct | 15.0 |
| max_positions | 6 |
| target_mult | 2.0 |
| direction | both |
| use_spy_filter | True |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -1.01% |
| Monthly return | -0.25% |
| Sharpe ratio | -1.03 |
| Max drawdown | -2.91% |
| Fills | 340 |
| Round trips | 170 |
| Win rate | 47.6% |
| Profit factor | 0.85 |
| Expectancy | $-5.94 |
| Max consec losses | 7 |
| Final equity | $98,989.79 |

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

> _Fill in: What worked, what didn't, surprising findings._

## Decision

**[ ] Reject** — reason:  
**[ ] Revise** — what to change:  
**[ ] Mark as promising** — justification:  

## Next Step

> _Fill in: What to test next._