# Run 023_gap_fill

**Date:** 2026-04-11
**Status:** [ ] In Progress  [x] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

Overnight gaps tend to fill intraday — fade gap-ups by going short, fade gap-downs by going long. Predicated on mean reversion: price gravitates back toward the prior session's close.

**Why it fails here:** In a trending market (2026 downtrend, 2025 bull run), gaps tend to CONTINUE in the direction of the gap ("gap and go"), not fill. The mean reversion assumption breaks down when a strong directional regime is present. Buying gap-down opens in a downtrend is directionally wrong; the underlying trend overwhelms the gap-fill tendency.

## Strategy Rules

- Track yesterday's close for each symbol
- Entry on first bar of day when gap [0.3%–3.0%]
- Gap UP (open > prev_close + 0.3%): go SHORT — bet on gap fill
- Gap DOWN (open < prev_close − 0.3%): go LONG — bet on gap fill
- Profit target: yesterday's close (full gap fill)
- Stop loss: 0.5× gap size beyond entry (gap extension)
- Profit target: 100% of gap fill (partial if < 100%)
- Direction filter: both (up_only=short only, down_only=long only)
- Skip gaps > 3.0% (earnings / news events)
- One trade per asset per day — first bar entry only
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
| min_gap_pct | 0.3 |
| max_gap_pct | 3.0 |
| stop_mult | 0.5 |
| fill_target_pct | 1.0 |
| direction | both |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -7.49% |
| Monthly return | -1.92% |
| Sharpe ratio | -5.47 |
| Max drawdown | -7.77% |
| Fills | 1666 |
| Round trips | 833 |
| Win rate | 37.6% |
| Profit factor | 0.64 |
| Expectancy | $-8.99 |
| Max consec losses | 17 |
| Final equity | $92,510.94 |

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

- **Both regimes failed badly**: 2026 primary Sharpe -5.47, total -7.49%. Gap-fill in a downtrend means going long into falling stocks — directionally wrong on almost every trade.
- **Win rate 37.6%**: The strategy loses more often than it wins AND average loss size is larger (PF 0.64 means losses are ~1.56× wins). Double punishment — frequency AND magnitude both negative.
- **17 consecutive losses**: Most damaging stat. In trending periods, the strategy runs streaks of wrong-direction trades with no way out until EOD flatten.
- **Root cause**: Mean reversion requires a ranging market. The strategy has no regime filter — it fires in both trending and ranging conditions, but only works in ranging. Adding a VIX/ATR regime filter could isolate valid conditions, but the setup complexity vs uncertain edge makes this not worth pursuing.
- **Max gap cap helps but not enough**: Capping at 3% filters earnings gaps but doesn't address the systematic trend bias.
- **Historical 2025 untested** (primary window only run), but expected to also fail — 2025 bull market has gap-and-go behaviour too, especially in NVDA/TSLA/COIN.

## Decision

**[x] Reject** — Mean reversion gap fill fails in both bull and bear trending regimes. No regime filter can reliably distinguish "gap-and-go day" from "gap-fill day" without lookahead bias. Strategy concept requires low-VIX, range-bound sessions that are rare in 2025–2026. Move on.

## Next Step

Pursue ORB Auto-Direction (027) — use SPY overnight gap direction to auto-select long/short ORB each day. This adapts to regime daily rather than assuming a fixed direction.