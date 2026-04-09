# Run 001 — Opening Range Breakout (ORB), base config

**Date started:** 2026-04-09
**Status:** [x] Rejected

---

## Hypothesis

The first 15 minutes of a trading session establish a meaningful support/resistance
range. A close above that range's high signals that buyers have conviction and the
move is likely to continue intraday. Exit at end of day to avoid overnight gap risk.

Expected edge: breakout above the opening range tends to follow through on trending
days and in highly liquid ETFs like SPY and QQQ.

## Implementation

- New file added: `trading/strategy/orb.py`
- No existing files modified
- Key parameters:
  - `range_minutes = 15` — opening range duration
  - `exit_time = 15:55 NY` — EOD flatten
  - Entry: first close above range high
  - Stop: close below range low
  - Long-only, max one trade per symbol per day

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ |
| Date range | 2025-01-01 → 2026-01-01 (full year) |
| Range period | 15 minutes |
| Exit time | 15:55 NY |
| Data source | Alpaca (5-minute bars) |
| Initial cash | $100,000 |
| Slippage | 5 bps |
| Commission | $0.005/share |

## Backtest Results

```
================================
      Backtest Results
================================
  Initial equity:  $  100,000.00
  Final equity:    $   98,915.12
  Total return:          -1.08%
  Sharpe ratio:           -0.04
  Max drawdown:          -2.75%
  Trades:                   728
================================
```

Win rates (round trips):
- SPY: 81 wins / 103 losses → 44.0%
- QQQ: 84 wins / 96 losses → 46.7%

## Evaluation

- [ ] Sharpe ≥ 0.5 — **FAIL** (−0.04)
- [ ] Max drawdown ≤ 25% — pass (−2.75%)
- [ ] Positive total return — **FAIL** (−1.08%)
- [ ] ≥ 15 trades — pass (728)
- [ ] ≥ 2 years tested — fail (1 year only — Alpaca free tier limit)
- [ ] ≥ 2 symbols tested — pass (SPY + QQQ)

## Decision after Run 1

**Revise** — run parameter variants before final decision.
Win rate of 44-47% with no clear edge. Likely issues: no volume filter,
no market regime filter, range too narrow on 5m bars. Worth testing variants
before abandoning the setup entirely.

---

## Run 2 — Parameter Variants (same day)

**Motivation:** confirm the base result is not a parameter artefact.
Three variants tested immediately after Run 1 to understand sensitivity.

| Variant | Return | Sharpe | Trades | Max DD |
|---|---|---|---|---|
| SPY only, range=15m | −0.62% | −0.05 | 368 | −1.32% |
| SPY only, range=30m | −1.14% | −0.10 | 350 | −1.53% |
| SPY + QQQ, range=30m | −2.05% | −0.08 | 684 | −2.84% |

All variants negative. The result is not sensitive to range width or symbol choice —
it is a structural problem with the setup.

## Final Decision

**[x] Reject**

Reason: negative return across all four variants tested on two liquid ETFs over
a full calendar year. The 44-47% win rate shows no edge. Parameter tuning will
not fix this — the core setup is missing necessary filters.

---

## Analysis: Why It Fails

**1. No volume filter.**
Entry fires on any close above range high. Many are low-volume fades.
A filter (e.g. entry bar volume ≥ 1.5× avg range volume) would reduce false entries.

**2. No market regime filter.**
ORB works on trending days, loses on choppy days. Trading every signal regardless
of SPY trend or VIX level wastes capital on bad-regime days.

**3. Range defined by only 3 bars.**
15 minutes / 5-minute bars = 3 bars. Too coarse. With 1-minute bars the same
range uses 15 data points — more robust high/low definition.

**4. No gap filter.**
Large gap-open days have different dynamics (gap-and-go vs gap-fade).
Treating all days the same dilutes the edge on normal breakout days.

## Final Conclusion

Basic ORB without filters has no edge on SPY/QQQ in 2025 at 5-minute resolution.
The setup is valid in concept but underpowered as implemented. The strategy class
(`trading/strategy/orb.py`) is reusable — the next run extends it with filters
rather than replacing it.

## Next Step

**Run 002 — ORB with volume confirmation + market regime filter.**

Changes:
1. Volume filter: entry bar volume ≥ 1.5× average range bar volume.
2. Regime filter: only trade when SPY close > SPY 20-day SMA (trending market).
3. Test on 1-minute bars if volume data is reliable at that resolution.
4. SPY only first. Add QQQ only if SPY shows improvement.

If Run 002 still fails → abandon ORB, move to VWAP mean reversion.
