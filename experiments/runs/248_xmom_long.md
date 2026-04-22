# Run 248_xmom_long

**Date:** 2026-04-13
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === PURE CROSS-SECTIONAL MOMENTUM ===
- Rank all stocks by 5-day return
- LONG top 8 | SHORT bottom 0
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
| momentum_days | 5 |
| long_k | 8 |
| short_k | 0 |
| exit_after_min | 20 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 3.31% |
| Monthly return | 0.82% |
| Sharpe ratio | 2.36 |
| Max drawdown | -1.88% |
| Fills | 671 |
| Round trips | 333 |
| Win rate | 51.4% |
| Profit factor | 1.46 |
| Expectancy | $10.35 |
| Max consec losses | 10 |
| Final equity | $103,306.52 |

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