# Run 001_orb_baseline

**Date:** 2026-04-10
**Status:** [ ] In Progress  [x] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

ORB exploits the idea that the first 15 minutes of trading establishes a key intraday range. A breakout above/below that range signals directional momentum that tends to continue. Jan-Apr 2026 is a bearish macro environment — the expectation is that long breakouts will frequently fail while short breakdowns should benefit from the trend. This run tests the bidirectional baseline to measure the long vs. short split.

## Strategy Rules

- Observe first 15 minutes of each day to establish the opening range
- Go LONG when price breaks above the range high
- Go SHORT when price breaks below the range low
- Stop loss: 0.5% from entry price
- Only one trade per asset per day — no re-entry after exit
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
| range_minutes | 15 |
| stop_pct | 0.5 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -3.61% |
| Monthly return | -0.9% |
| Sharpe ratio | -1.54 |
| Max drawdown | -5.3% |
| Fills | 2206 |
| Round trips | 1103 |
| Win rate | 31.5% |
| Profit factor | 0.88 |
| Expectancy | $-3.27 |
| Max consec losses | 20 |
| Final equity | $96,391.62 |

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

- Terrible win rate (31.5%) — less than 1 in 3 trades wins. For a trend-following strategy in a known downtrend, this means long breakouts are getting crushed.
- Profit factor 0.88 < 1.0 — losing more than making, confirmed by -3.61% total return.
- 1103 round trips across 17 symbols is a large sample — the edge is genuinely negative for bidirectional ORB.
- Sharpe -1.54 is severe. The longs are the drag; shorts likely have better stats.
- "No fill price" warnings for BA, SHOP, COIN, RIVN suggest these thinly-traded names have gaps in the Alpaca IEX feed. They contribute noise without edge.
- Next test: ORB short-only. The downtrend hypothesis says shorts should dominate.

## Decision

**[x] Reject** — Bidirectional ORB in a downtrending environment has negative expectancy (-$3.27/trade) and 31.5% WR. The longs are structural losers in this regime.

## Next Step

002: ORB short-only — test if filtering to breakdowns only improves win rate and Sharpe. If shorts alone are profitable, we have a directional edge to build on.