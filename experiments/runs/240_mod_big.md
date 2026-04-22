# Run 240_mod_big

**Date:** 2026-04-13
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === SELECTOR: top 15 by composite score ===
- Factors: RVOL + range + momentum + gap + RS
- Selection at 9:30+30min
- === BEAR EXECUTOR: RS shorts on short-biased selected ===
- RS < -1.0% | Stop 3.0% | Target 3.0%
- === BULL EXECUTOR: overnight longs on long-biased selected ===
- 4+4 | Exit 20min

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP, AVGO, CRM, UBER, LLY, MA, COST, GOOG, INTC, PYPL, SQ, SNAP, V, HD, MU, QCOM, ABNB, DIS, LOW, TGT, NKE, SBUX, XOM, CVX, COP, PFE, ABBV, MRK, WMT, AMGN, GS, MS, C, BAC, CAT, DE, UPS, PANW, CRWD, NET, MSTR, MARA, SMCI, ARM, DELL, SOFI, HOOD, DKNG, RBLX, VGK |
| Date range | 2026-01-01 → 2026-04-30 |
| Interval | 1m |
| Leverage | 5.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| selector | composite |
| select_top_n | 15 |
| rs_stop_pct | 3.0 |
| rs_target_pct | 3.0 |
| exit_after_min | 20 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -1.3% |
| Monthly return | -0.31% |
| Sharpe ratio | -0.98 |
| Max drawdown | -5.35% |
| Fills | 902 |
| Round trips | 451 |
| Win rate | 45.0% |
| Profit factor | 0.92 |
| Expectancy | $-2.88 |
| Max consec losses | 8 |
| Final equity | $98,702.91 |

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