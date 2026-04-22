# Run 249_xmom_mega

**Date:** 2026-04-13
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === PURE CROSS-SECTIONAL MOMENTUM ===
- Rank all stocks by 5-day return
- LONG top 8 | SHORT bottom 5
- Hold overnight, exit 20min after open
- Stop: 3.0%
- Intraday RS tiebreaker: ON (weight 0.3)
- No regime filter — always trades

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | AAPL, ABBV, ABNB, AMD, AMGN, AMZN, APD, ARKF, ARKK, ARM, AVGO, BA, BAC, C, CAT, CELH, CHTR, CMCSA, COIN, COP, COST, CRM, CRWD, CVX, DASH, DDOG, DE, DELL, DIS, DKNG, DUK, EFA, EOG, EWG, FCX, FDX, FXI, GD, GOOG, GOOGL, GS, HD, HIMS, HOOD, INTC, IONQ, IWM, JPM, LIN, LLY, LMT, LOW, MA, MARA, META, MMM, MPC, MRK, MS, MSFT, MSTR, MU, NEE, NEM, NET, NFLX, NKE, NVDA, OKLO, PANW, PATH, PFE, PLTR, PSX, PYPL, QCOM, QQQ, RBLX, RGTI, RIVN, RKLB, ROKU, RTX, SBUX, SHOP, SLB, SMCI, SNAP, SNOW, SO, SOFI, SPY, SQ, T, TGT, TQQQ, TSLA, TTD, U, UBER, UNH, UPS, UVXY, V, VGK, VLO, VZ, WM, WMT, XLB, XLC, XLE, XLI, XLK, XLP, XLU, XLV, XLY, XOM, ZS |
| Date range | 2026-01-01 → 2026-04-30 |
| Interval | 1m |
| Leverage | 3.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| momentum_days | 5 |
| long_k | 8 |
| short_k | 5 |
| exit_after_min | 20 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 2.16% |
| Monthly return | 0.54% |
| Sharpe ratio | 1.4 |
| Max drawdown | -2.03% |
| Fills | 1429 |
| Round trips | 709 |
| Win rate | 50.1% |
| Profit factor | 1.17 |
| Expectancy | $3.33 |
| Max consec losses | 8 |
| Final equity | $102,162.11 |

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