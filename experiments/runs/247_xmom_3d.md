# Run 247_xmom_3d

**Date:** 2026-04-13
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === PURE CROSS-SECTIONAL MOMENTUM ===
- Rank all stocks by 3-day return
- LONG top 3 | SHORT bottom 3
- Hold overnight, exit 20min after open
- Stop: 3.0%
- Intraday RS tiebreaker: ON (weight 0.3)
- No regime filter — always trades

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP, AVGO, CRM, UBER, LLY, MA, COST, GOOG, INTC, PYPL, SQ, SNAP, V, HD, MU, QCOM, ABNB, DIS, LOW, TGT, NKE, SBUX, XOM, CVX, COP, PFE, ABBV, MRK, WMT, AMGN, GS, MS, C, BAC, CAT, DE, UPS, PANW, CRWD, NET, MSTR, MARA, SMCI, ARM, DELL, SOFI, HOOD, DKNG, RBLX, VGK |
| Date range | 2026-01-01 → 2026-04-30 |
| Interval | 1m |
| Leverage | 3.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| momentum_days | 3 |
| long_k | 3 |
| short_k | 3 |
| exit_after_min | 20 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -2.84% |
| Monthly return | -0.71% |
| Sharpe ratio | -2.17 |
| Max drawdown | -4.32% |
| Fills | 766 |
| Round trips | 380 |
| Win rate | 50.5% |
| Profit factor | 0.79 |
| Expectancy | $-7.19 |
| Max consec losses | 8 |
| Final equity | $97,155.72 |

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