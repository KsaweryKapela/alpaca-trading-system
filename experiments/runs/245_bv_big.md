# Run 245_bv_big

**Date:** 2026-04-13
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BOOSTED v10 (Score-Enhanced Ranking) ===
- Same trades as v10, but high-conviction stocks get PRIORITY
- RVOL boost +0.3 | Range boost +0.2
- Momentum boost +0.2 | Overnight boost +0.1
- RS < -1.0% | Stop 3.0% | Target 3.0%
- Overnight 4+4 | Exit 20min

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP, AVGO, CRM, UBER, LLY, MA, COST, GOOG, INTC, PYPL, SQ, SNAP, V, HD, MU, QCOM, ABNB, DIS, LOW, TGT, NKE, SBUX, XOM, CVX, COP, PFE, ABBV, MRK, WMT, AMGN, GS, MS, C, BAC, CAT, DE, UPS, PANW, CRWD, NET, MSTR, MARA, SMCI, ARM, DELL, SOFI, HOOD, DKNG, RBLX, VGK |
| Date range | 2026-01-01 → 2026-04-30 |
| Interval | 1m |
| Leverage | 5.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| rs_threshold | 1.0 |
| rs_stop_pct | 3.0 |
| rs_target_pct | 3.0 |
| exit_after_min | 20 |
| boost_type | rvol+range+mom+overnight |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 9.97% |
| Monthly return | 2.44% |
| Sharpe ratio | 2.09 |
| Max drawdown | -6.64% |
| Fills | 2026 |
| Round trips | 1013 |
| Win rate | 48.4% |
| Profit factor | 1.33 |
| Expectancy | $9.84 |
| Max consec losses | 10 |
| Final equity | $109,970.67 |

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