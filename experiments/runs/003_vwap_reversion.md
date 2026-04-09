# Run 003 — VWAP Mean Reversion

**Date:** 2026-04-09
**Status:** [ ] In Progress  [x] Rejected  [ ] Revised  [ ] Promising  [ ] Complete

---

## Research Summary

Prior to this run, searched for VWAP reversion evidence on 5m SPY. Key findings:
- Edge is documented (SSRN paper, practitioner backtests); institutional algos target VWAP,
  creating mean-reverting pressure when price deviates
- 0.1-0.2% threshold too tight for 5m bars — noise zone; literature recommends 0.5-1.2%
- Win rate often sub-50% but profit factor 1.5-1.7 is achievable
- Fails on strong trend days; regime filter (ADX < 25 or gap filter) helps
- Skip first 30 minutes (9:30-10:00) — opening auction creates VWAP distortions

## Hypothesis

Institutional execution algorithms (TWAP/VWAP algos) create systematic buying pressure
near the daily VWAP line throughout the session. When SPY dips 0.7% below intraday VWAP,
the aggregate effect of these algos pulling price back toward their benchmark creates a
statistically predictable reversion.

Expected edge: buy-the-dip-to-VWAP should show win rate ~45-55% with profit factor > 1.5
because the reward (revert to VWAP = +0.7%) is larger than the typical stop loss (−0.5%
below entry) and VWAP acts as a magnet.

Key differences from ORB (which failed): this strategy is mean-reverting, not
trend-following. ORB tries to ride a move that has already started; VWAP reversion
fades a short-term overextension. These work on different market conditions.

## Implementation

- New file added: `trading/strategy/vwap_reversion.py` — `VWAPReversionStrategy`
- No existing files modified
- Key parameters:
  - `entry_dev = 0.007` — enter when close < VWAP * (1 - 0.007), i.e. 0.7% below VWAP
  - `stop_pct = 0.005` — stop loss 0.5% below entry price
  - `target = VWAP` — take profit when price returns to VWAP
  - `entry_start = 10:00 NY` — skip first 30 min (opening noise)
  - `exit_time = 15:55 NY` — EOD flatten
  - Long-only, one trade per symbol per day

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY |
| Date range | 2025-01-01 → 2026-01-01 |
| Key parameters | entry_dev=0.7%, stop_pct=0.5%, target=VWAP, entry_start=10:00 |
| Data source | Alpaca (5m bars) |
| Bar interval | 5m |
| Initial cash | $100,000 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | |
| Sharpe ratio (daily) | |
| Max drawdown | |
| Round trips | |
| Win rate | |
| Profit factor | |
| Expectancy | |
| Max consec losses | |
| Avg trade duration | |
| Final equity | |

Paste full output here:

    Base config (entry_dev=0.7%, stop=0.5%) — after timestamp fix:
    Total return: −0.09%  Sharpe: −0.25  WR: 54.1%  PF: 0.90  37 RT  Avg dur: 1.4 hr

    Variant A (stop=0.3%): −0.36%  Sharpe: −1.32  WR: 32.4%  PF: 0.60  37 RT
    Variant B (entry=0.4%, stop=0.3%): −0.10%  Sharpe: −0.25  WR: 51.1%  PF: 0.94  92 RT
    Variant C (QQQ, base): −0.58%  Sharpe: −1.26  WR: 45.5%  PF: 0.68  55 RT
    Variant D (entry=0.4%, stop=0.4%, exit 14:30): −0.17%  Sharpe: −0.44  WR: 46.7%  PF: 0.89

Bugs found and fixed during this run:
  - Timestamp bug fixed: backtest engine now stamps orders with bar timestamp
    (created_at=signal bar ts, filled_at=fill bar ts). Avg duration now meaningful.
  - _entry_price bug fixed: stop loss now uses pos.avg_price (actual fill price)
    instead of signal bar close. Prevents slightly wrong stop levels.

## Walk-Forward (intraday strategies only)

    Not run — no variant showed positive PF; walk-forward not warranted.

Avg test Sharpe: N/A | Positive folds: N/A

## Evaluation

Score against candidate criteria:

- [ ] Sharpe ≥ 0.5 — FAIL (best: −0.25)
- [x] Max drawdown ≤ 25% — pass (best: −0.30%)
- [ ] Positive total return — FAIL (best: −0.09%)
- [x] ≥ 15 round trips — pass (37–92 across variants)
- [ ] ≥ 2 years tested — fail (1 year, Alpaca limit)
- [ ] ≥ 2 symbols / windows tested — fail (QQQ variant was worse)
- [ ] Win rate ≥ 40% OR profit factor ≥ 1.5 — FAIL (best PF: 0.94)
- [ ] Walk-forward avg test Sharpe ≥ 0.3 — not run

Observations:

Win rate of 54% is healthy but profit factor stays below 1 across all variants.
The average win is smaller than the average loss — tightening the stop (Variant A)
collapses win rate to 32%, showing price needs room before reverting.

2025 was a strong trending year for SPY. VWAP reversion thrives in range-bound
conditions where VWAP acts as a strong attractor. In a persistent uptrend, VWAP
follows price higher and a "dip to VWAP" often continues lower rather than reverting.

Transaction costs (5bps slippage each way + commission) are ~$9 per round trip.
The best variant earns ~$0 gross, so costs alone explain the negative result.

## Decision

**[x] Reject**

Reason: VWAP mean reversion at 5m on SPY cannot clear transaction costs in a trending
market. All 5 variants tested negative. The concept is sound but requires either:
(a) a regime filter to identify ranging vs trending days (ADX < 25), or
(b) a different market environment (sideways/volatile year).
Not worth further revision at this stage — pivoting to daily bar strategies where
multi-year data is available and documented edge is stronger.

---

## Final Conclusion

Three intraday strategy families tested (ORB breakout, ORB with filters, VWAP reversion) —
all failed on SPY 5m bars in 2025. The common thread: 2025 was a trending bull market, and
both trend-following (ORB) and mean-reverting (VWAP) intraday setups failed. ORB false-
breakouts are common in extended markets; VWAP dips don't revert in persistent uptrends.

Inference: intraday alpha on SPY at 5m resolution requires regime-dependent logic that is
significantly more complex than simple fixed-rule strategies. The bar-based system can
implement this, but it's not the right first target.

Daily bar strategies have decades of data available, well-documented edge (SMA crossover
Sharpe 0.5-0.8 in academic literature), and test across multiple bear/bull cycles.

## Next Step

**Run 004 — SMA Crossover on SPY+QQQ (daily bars, 2015–2026)**

No new code needed. `trading/strategy/sma_cross.py` already exists.

Two parameter sets:
1. fast=20, slow=50 (active, more trades)
2. fast=50, slow=200 (golden cross, fewer but stronger signals)

Test period: 2015-01-01 → 2026-01-01 (11 years, covers COVID crash, 2022 bear, 2023-2025 bull).
Data source: yfinance daily (50+ years available, no data limitation concerns).
