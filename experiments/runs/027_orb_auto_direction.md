# Run 027_orb_auto_direction

**Date:** 2026-04-11
**Status:** [ ] In Progress  [x] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

The ORB strategy has proven strong in 2026's downtrend (short-only, run 014: Sharpe 2.87), but fails in 2025's bull market because it only allows shorts. The fix: use SPY's overnight gap to auto-select direction each day. Gap-down SPY (≥0.2%) → short ORB (bearish day likely); Gap-up SPY (≥0.2%) → long ORB (bullish day likely). This should make ORB cross-regime by adapting to daily market direction rather than fixing direction permanently.

**Why it fails here:** The cross-regime idea is sound in theory but the full 19-symbol universe is the fatal flaw.
- **2026 primary (-5.67%)**: Most 2026 sessions have SPY gap-down → short ORB fires. But with 19 symbols, stable mega-caps (AAPL, MSFT, GOOGL, AMZN) drag down win rate. These stocks don't have strong ORB breakdowns — they're too large and liquid to have clean range breakdowns.
- **2025 catastrophic (-34.88%)**: SPY gaps up on most 2025 days → long ORB fires on 19 symbols. The problem: in a bull market, the 5-min opening range high is often the intraday extreme (stocks open strong and then consolidate). Buying the 5-min range high breakout is actually buying at the local top. For short ORB in downtrends, the range low breakout is meaningful — price was already weak. For long ORB in uptrends, the range high breakout is often extended and reversal-prone.
- **Asymmetry of ORB**: ORB short exploits "gap-and-go down from open range" in downtrends. ORB long in uptrends tries to buy a second leg up from an already-elevated open — a much weaker signal.
- **Symbol selection lesson reconfirmed**: 014's Sharpe 2.87 came from 6 specific high-beta stocks (PLTR, TSLA, COIN, AMD, SHOP, JPM). The full universe dilutes and destroys the edge. ORB longs would need a different high-beta set tuned for uptrends.

## Strategy Rules

- Opening range: first 5 minutes establish the range
- Direction: auto (SPY gap determines long/short each day, threshold=0.2%)
- Macro regime filter: SPY below its daily VWAP
- SPY intraday decline filter: no SPY intraday decline filter
- Stock VWAP filter: no stock VWAP filter
- Gap filter: no gap filter
- Min range width filter: no min range width filter
- SHORT entry: breakdown below range_low (all active filters must pass)
- LONG entry: breakout above range_high (when direction allows)
- Stop loss: 1.0% from entry
- Exit: EOD flatten
- One trade per asset per day — no re-entry
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | QQQ, SPY, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 2.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| range_minutes | 5 |
| stop_pct | 1.0 |
| profit_target_pct | 0.0 |
| direction | both |
| regime_filter | True |
| stock_vwap_filter | False |
| gap_filter_pct | 0.0 |
| max_trades_per_day | 1 |
| reentry_cooldown | 5 |
| spy_decline_pct | 0.0 |
| min_range_pct | 0.0 |
| auto_direction | True |
| spy_gap_threshold | 0.2 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -5.67% |
| Monthly return | -1.45% |
| Sharpe ratio | -2.13 |
| Max drawdown | -9.02% |
| Fills | 1070 |
| Round trips | 535 |
| Win rate | 39.6% |
| Profit factor | 0.8 |
| Expectancy | $-10.6 |
| Max consec losses | 9 |
| Final equity | $94,328.75 |

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

- **2025 is catastrophic (-34.88%, Sharpe -3.81, DD -35.67%)**: Worst historical result of any experiment. Long ORB on 19 symbols in a bull market is deeply flawed — the 5-min high breakout is a buy-at-the-top signal in uptrending conditions.
- **2026 is mediocre (-5.67%)**: Auto-direction means many 2026 sessions (gap-down days) trigger short ORB — similar to what we've tested before with full universe. Consistently negative because bad symbols drag it down.
- **Win rate 39.6% (2026), 35.3% (2025)**: Even worse in 2025 than 2026 despite the market going up overall. The long ORB entries are uniformly poor.
- **Fills only 1070 (2026), 3546 (2025)**: Fewer trades in primary window because auto_direction=none on small-gap days suppresses trades entirely. Many 2026 days have SPY gaps < 0.2% → no trades for any symbol that day.
- **Key takeaway**: ORB long in uptrending market does NOT work with this setup. The asymmetry is fundamental: short ORB (selling breakdown) exploits downward momentum; long ORB (buying breakout above 5-min high) fights the tendency of strong opens to consolidate.
- **If ORB long was to work**: Would need specifically high-momentum gap-up stocks (NVDA, TSLA, COIN on strong days) with additional confirmation (RVOL > 2×, ADX > 25) — not a general 19-symbol trigger.

## Historical 2025 Results

| Metric | Value |
|---|---|
| Total return | -34.88% |
| Monthly return | -3.49% |
| Sharpe ratio | -3.81 |
| Max drawdown | -35.67% |
| Win rate | 35.3% |
| Profit factor | 0.60 |

## Decision

**[x] Reject** — Auto-direction ORB fails in both regimes due to (a) full-universe symbol contamination and (b) structural weakness of long ORB in uptrends. The idea that SPY gap direction predicts intraday continuation for 19 diverse symbols is too simplistic. Each symbol has its own character; a general gap direction filter can't compensate for fundamentally weak long ORB signals.

## Next Step

Run 028: RS short-only with revised parameters (rs_threshold=1.0%, stop=1.0%, TP=2.0%, entry_after_min=15). The 024 experiment showed Sharpe 0.92 in 2026 — the edge is real for shorts. Eliminating longs and raising the threshold should fix the 2025 failure and improve PF above 1.5.