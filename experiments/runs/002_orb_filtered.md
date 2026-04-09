# Run 002 — ORB with Volume + Regime Filter

**Date:** 2026-04-09
**Status:** [ ] In Progress  [x] Rejected  [ ] Revised  [ ] Promoted to Paper  [ ] Complete

---

## Hypothesis

Base ORB (Run 001) had no edge on SPY/QQQ in 2025: −1.08% return, Sharpe −0.04, 44-47% win rate.
The diagnosis identified two root causes:

1. **No volume filter** — entry fires on every close above range high, including low-volume fades
   where institutional conviction is absent. Genuine breakouts are accompanied by expanding volume.

2. **No regime filter** — ORB works on trending days and loses on choppy/reverting days.
   Without a market regime check, the strategy trades every day regardless of conditions.

**Hypothesis:** Requiring (a) entry bar volume ≥ 1.5× average range bar volume AND (b) SPY
above its 20-day SMA should filter out most false entries. Fewer trades but higher quality
should produce a positive Sharpe and win rate above 50%.

## Implementation

- New file added: `trading/strategy/orb_filtered.py` — `ORBFilteredStrategy` subclasses `ORBStrategy`
- `main.py` extended: added `orb-filtered` strategy choice and three new CLI args
- No existing strategy files modified

Key parameters:
- `volume_multiplier = 1.5` — entry bar volume must be ≥ 1.5× avg range bar volume
- `sma_period = 20` — 20-day SMA for regime filter
- `regime_symbol = "SPY"` — regime filter uses SPY's own daily data (loaded from yfinance)
- Range: 15 minutes (3 bars at 5m resolution), EOD exit 15:55 NY

Regime filter design note: uses the *previous session's* close vs SMA to avoid lookahead.
Regime data loaded from yfinance (5y daily) at strategy construction time.

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY |
| Date range | 2025-01-01 → 2026-01-01 |
| Key parameters | range=15m, vol_mult=1.5, sma=20, regime=SPY |
| Data source | Alpaca (5m bars) |
| Bar interval | 5m |
| Initial cash | $100,000 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | −0.37% |
| Sharpe ratio (daily) | −1.05 |
| Max drawdown | −0.68% |
| Round trips | 82 |
| Win rate | 31.7% |
| Profit factor | 0.69 |
| Expectancy | −$4.53 |
| Max consec losses | 10 |
| Avg trade duration | N/A (bug — see notes) |
| Final equity | $99,628.99 |

Paste full output here:

    ====================================
             Backtest Results
    ====================================
      Initial equity:  $  100,000.00
      Final equity:    $   99,628.99
      Total return:          -0.37%
      Sharpe ratio:           -1.05
      Max drawdown:          -0.68%
      Trades (fills):           165
    ------------------------------------
      Round trips:               82
      Win rate:               31.7%
      Profit factor:           0.69
      Expectancy:      $      -4.53
      Max consec loss:           10
      Avg duration:           0.0 hr
    ====================================

**Bug found and fixed — fill timestamp:**
`SimulatedExecutor` was stamping fills with `datetime.now()` (wall-clock) rather
than bar timestamp. Fixed: now uses `order.created_at` (= signal bar time).
Avg trade duration is now meaningful in future runs.

**Bug found and fixed — volume cap on exits:**
`max_volume_pct` was applied to sell orders, splitting one position close into
two partial fills (11 + 3 shares). Fixed: volume cap now applies to buys only.
Round-trip P&L in this run is still valid (same shares bought and sold, same prices).
Win rate metric may be slightly off due to the one split sell — not material.

## Walk-Forward (intraday strategies only)

    Not run — result clearly negative, walk-forward not warranted.

Avg test Sharpe: N/A | Positive folds: N/A

## Evaluation

Score against promotion criteria:

- [ ] Sharpe ≥ 0.5 — **FAIL** (−1.05, worse than base config's −0.04)
- [x] Max drawdown ≤ 25% — pass (−0.68%, but only because trades are rare)
- [ ] Positive total return — **FAIL** (−0.37%)
- [x] ≥ 15 round trips — pass (82)
- [ ] ≥ 2 years tested — fail (1 year, Alpaca free tier)
- [ ] ≥ 2 symbols / windows tested — fail (SPY only)
- [ ] Win rate ≥ 40% OR profit factor ≥ 1.5 — **FAIL** (31.7% win rate, PF=0.69)
- [ ] Walk-forward avg test Sharpe ≥ 0.3 — not run

Observations:

The filters made performance *worse*, not better. Key observations:

1. **Win rate collapsed from 44-47% → 31.7%.** The volume filter appears to be
   selecting for adverse entries. High-volume breakout bars at 9:45-9:50 may be
   exhaustion/capitulation events that reverse — the opposite of what was expected.

2. **Trade count dropped from 364 → 82 round trips (-77%).** Heavy filtering removed
   most signals, leaving a small sample where the remaining trades are losing money
   more decisively. Profit factor 0.69 means losses outweigh wins by 45%.

3. **Regime filter (SPY > 20d SMA) may be counterproductive.** It restricts trading
   to trending/bullish conditions. In those conditions SPY's intraday breakouts may
   be getting "bought into" by the market, only to retrace. The strategy captures
   the post-breakout pullback, not the follow-through.

4. **Trend within the year:** The equity curve shows consistent losses from July 2025
   onward as SPY moved to new highs ($640-$689). The regime filter kept us invested
   in precisely the overbought conditions where ORB false breakouts are most common.

5. **Structural conclusion:** ORB as implemented does not work on SPY at 5m resolution
   in 2025. Neither the base config nor the filtered version has edge. Adding filters
   on top of a broken core does not fix the core.

## Decision

**[x] Reject**

Reason: Filters made performance worse across all metrics. Sharpe −1.05, win rate 31.7%,
profit factor 0.69. The volume filter selects for entries that reverse rather than continue.
ORB as a concept requires either a different timeframe (1m bars, longer range) or a different
instrument (individual stocks with cleaner opening range dynamics, not broad market ETFs).

---

## Analysis: Why the Filters Failed

**Volume filter selecting against us:**
High volume at the breakout level on SPY often marks institutional selling into strength
(distribution), not buying conviction. The 1.5× filter inadvertently picks the hardest
spots to trade: heavy two-way action at key levels that chops both directions.

**Regime filter problem:**
SPY > 20d SMA means we only trade during bull runs. But SPY intraday ORB on 5m bars tends
to see more false breakouts during trending conditions — the market gaps up, makes a new
intraday high, then reverts. Bear markets or sideways markets have sharper, cleaner ORB
setups because the breakout is a genuine sentiment shift.

**5m bars are too coarse:**
Range = 3 bars (9:30, 9:35, 9:40). Three data points set the support/resistance level.
On 1m bars the same range would use 15 data points, defining a more meaningful level.

## Final Conclusion

ORB is not dead as a concept but is dead on SPY at 5m resolution with the filters tested.
Two runs, six variants (including the four from Run 001) — all negative. The structural
problems are too deep for parameter tuning to fix.

**What this means:** We have learned that SPY 5m ORB with standard filters does not produce
a backtest-grade edge in 2025. This eliminates a large family of approaches quickly, which
is valuable information.

## Next Step

**Run 003 — VWAP mean reversion on SPY (5m bars, 2025)**

Completely different mechanism: instead of buying breakouts, buy when price pulls back to VWAP
after an upside gap open. VWAP reversion works on different market dynamics (mean reversion
vs trend-following) and has a theoretical basis rooted in institutional execution algorithms
targeting VWAP fills throughout the day.

If VWAP reversion also fails → pivot to daily-bar strategies (SMA crossover on SPY/QQQ with
a proper multi-year test) where the data limitations are more forgiving.
