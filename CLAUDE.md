# CLAUDE.md — Operating Manual for Strategy Research & Deployment

This file defines how I work inside this repo.  
It is my task loop, process guide, and decision framework for iterative strategy research.  
I read this at the start of every session to know where I am and what to do next.

---

## 1. Current State

> **Update this section at the end of every session.**

- **Active strategy:** ORB with volume + regime filter (Run 002)
- **Phase:** Not yet started
- **Last run:** 001 — ORB base config — REJECTED (−1.08%, Sharpe −0.04)
- **Next action:** Implement volume filter + regime filter in `trading/strategy/orb.py`, run backtest on SPY with 5m Alpaca bars 2025-01-01 → 2026-01-01. Log in `experiments/runs/002_orb_filtered.md`.

---

## 2. The Iteration Loop

Each cycle follows these steps in order. Do not skip steps.

```
1. PICK    → Choose one strategy idea. Write down the hypothesis before touching code.
2. BUILD   → Implement or adapt existing code. Keep changes minimal and targeted.
3. TEST    → Run backtest. Use at least 2 years of data. Test on 2+ symbols.
4. EVAL    → Score against promotion criteria (see Section 4). Be honest.
5. DECIDE  → Reject / Revise / Promote to paper trading.
6. LOG     → Write the run note as soon as the FIRST result lands — not after variants.
              Variants are appended as ## Run 2, ## Run 3 in the same file after logging.
7. REPEAT  → Pick the next strategy. Go back to step 1.
```

If promoted:
```
5a. DEPLOY → Start paper trading on Alpaca with reduced risk settings.
5b. OBSERVE → Monitor for at least 10 trading days. Log observations.
5c. CONCLUDE → Write final conclusion. Mark cycle complete. Move to next strategy.
```

---

## 3. Folder & File Conventions

```
experiments/
├── runs/
│   ├── 001_sma_cross.md          ← one file per run, numbered sequentially
│   ├── 002_rsi_mean_reversion.md
│   └── ...
└── STATUS.md                     ← current state snapshot (same as Section 1 here)
                                     keep both in sync
trading/
├── strategy/
│   ├── base.py
│   ├── sma_cross.py              ← existing
│   └── <new_strategy>.py         ← add new strategies here
```

**Naming runs:** `NNN_<short_name>.md` — e.g., `003_bollinger_bands.md`  
**One file per strategy attempt.** If you revise and re-run the same strategy, append a new `## Run 2` section to the same file rather than creating a new file.

---

## 4. Promotion Criteria (Backtest → Paper Trading)

A strategy must meet **all** of the following before being promoted:

| Criterion | Minimum threshold |
|---|---|
| Sharpe ratio (annualized) | ≥ 0.5 |
| Max drawdown | ≤ 25% |
| Total return | Positive over full test period |
| Number of trades | ≥ 15 (enough signal frequency to be meaningful) |
| Test period | ≥ 2 full years |
| Symbols tested | ≥ 2 different symbols or time windows |
| Consistency | Results not wildly different across tested symbols |

If a strategy passes 5 out of 6 criteria with a compelling hypothesis, it may still be promoted — but this must be explicitly justified in the run note.

**Hard rules:**
- No strategy goes to paper trading without a completed run note in `experiments/runs/`.
- No strategy goes to paper trading based on a single symbol test.
- If it only barely passes, reduce paper trading exposure further (see Section 5).

---

## 5. Data Source Limitations

Know these before planning any backtest. They affect what date ranges are valid
and whether a "≥ 2 years tested" criterion can be met.

| Source | Interval | Max history | Notes |
|---|---|---|---|
| yfinance | 1m | **7 days** | Not usable for meaningful backtests |
| yfinance | 5m / 15m / 30m | **60 days** | ~40 trading days; too short for promotion criteria |
| yfinance | 1h | ~2 years | Usable for coarse intraday tests |
| yfinance | 1d | 50+ years | Best source for daily-bar strategies |
| Alpaca (free IEX feed) | 1m / 5m | **~1–2 years** | Verified: full 2025 returns fine; older data may be missing |
| Alpaca (free IEX feed) | 1d | ~5+ years | Sufficient for daily strategies |
| Alpaca (paid SIP feed) | all | Full history | Not currently subscribed |

**Practical rules:**
- For intraday strategies on 5m bars: use Alpaca, test 1 full calendar year at a time.
- Do not use yfinance for 5m backtests — 60 days is not enough signal.
- The "≥ 2 years tested" promotion criterion **cannot be met with Alpaca free tier
  on 5m bars.** Document this explicitly in every run note that uses intraday data.
  Promote with justification only if 1 year of results is strong (Sharpe ≥ 1.0).
- When using Alpaca historical data, always verify the loaded bar count in the logs
  before trusting the result. Sparse data can silently produce misleading metrics.

---

## 6. Paper Trading Parameters

When a strategy is promoted, use these conservative settings:

| Parameter | Backtest default | Paper trading |
|---|---|---|
| `max_position_pct` | 10% | 5% |
| `max_positions` | 10 | 5 |
| `initial_cash` | $100,000 | use Alpaca paper balance |

Run with:
```bash
uv run python main.py paper --symbols <SYMBOLS> --fast <N> --slow <N>
```

Observe for **at least 10 trading days** before drawing conclusions.  
Log observations in the run note under `## Paper Trading Log`.

---

## 6. Run Note Template

Every run gets a file in `experiments/runs/`. Copy this template exactly.

---

```markdown
# Run NNN — <Strategy Name>

**Date:** YYYY-MM-DD  
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promoted to Paper  [ ] Complete

---

## Hypothesis

What is the idea? Why should it work? What market behavior does it exploit?  
Write this before running any code.

## Implementation

- New file(s) added: 
- Existing file(s) modified: 
- Key parameters:
- Notes on implementation decisions:

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | |
| Date range | |
| Fast period | |
| Slow period (or other params) | |
| Data source | yfinance / alpaca |
| Initial cash | $100,000 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | |
| Sharpe ratio | |
| Max drawdown | |
| Number of trades | |
| Final equity | |

Paste full output here:

    (output)

## Evaluation

Score against promotion criteria:

- [ ] Sharpe ≥ 0.5
- [ ] Max drawdown ≤ 25%
- [ ] Positive total return
- [ ] ≥ 15 trades
- [ ] ≥ 2 years tested
- [ ] ≥ 2 symbols / windows tested

Observations:

## Decision

**[ ] Reject** — reason:  
**[ ] Revise** — what to change, then re-run:  
**[ ] Promote to paper trading** — justification:  

---

## Paper Trading Log

*(Fill in only if promoted)*

**Start date:**  
**Symbols:**  
**Settings used:**  

| Date | Observation |
|---|---|
| | |

**Paper trading conclusion:**

---

## Final Conclusion

What did we learn? What worked, what didn't, what to try next?

## Next Step

What is the next strategy to test, or the next revision of this one?
```

---

## 7. How to Continue After a Completed Cycle

When a cycle is marked **Complete**:

1. Update `Current State` (Section 1 of this file) with the next strategy.
2. Update `experiments/STATUS.md` to match.
3. Create a new run note file for the next strategy.
4. Start at step 1 of the iteration loop.

Do not carry forward vague intentions. The `Next Step` field in every run note must name a specific next strategy or revision. That is the input to the next cycle.

---

## 8. Code Modification Rules

- If existing code is sufficient to test the strategy, **do not modify it**. Just run it.
- If the strategy requires a new signal type or data, **add a new file** in `trading/strategy/`. Do not modify existing strategies.
- If the strategy requires a new data source or execution logic, **extend** the relevant module. Keep changes backward compatible.
- After any code change, run a quick smoke test before backtesting:
  ```bash
  uv run python -c "from trading.strategy.<new_module> import <ClassName>; print('OK')"
  ```
- Commit code changes separately from run notes:
  ```bash
  git add trading/
  git commit -m "strategy: add <name> implementation"
  
  git add experiments/
  git commit -m "experiment: run NNN <strategy name> — <result in one word>"
  ```

---

## 9. Realistic Scope of This System

This is a **bar-based rule-driven system**, not an HFT platform.

**What it can do well:**
- Rule-based strategies on 1m/5m/1h/daily bars
- Backtest, paper trade, and live trade with shared strategy code
- ETFs (SPY, QQQ) and highly liquid large-caps (AAPL, MSFT, NVDA)
- Intraday strategies that hold through the session and flatten by EOD
- Daily and multi-day swing strategies

**What it is NOT built for:**
- Sub-second or tick-by-tick execution (needs a different stack)
- Order book / Level 2 strategies
- News-driven or latency-sensitive plays
- Low-float momentum, options, multi-leg stat-arb
- Strategies that depend on millisecond timing or co-location

**Recommended strategy families for fast feedback:**

| Strategy | Interval | Why it works here |
|---|---|---|
| Opening Range Breakout (ORB) | 5m | Simple rules, daily decision, clear exit |
| VWAP mean reversion | 5m | Common intraday structure, many samples |
| Gap-and-go / gap-fade | Daily or 5m | One clean window per day |
| ETF intraday trend (SPY/QQQ) | 5m | Liquid, low single-name risk |
| SMA crossover | Daily | Slow but clean, good baseline |

**Start here (in order):**
1. SPY / QQQ — cleanest liquidity, fewest idiosyncratic risks
2. One setup at a time — ORB or VWAP, not both simultaneously
3. Fixed rules before the first backtest — no tuning until after first results
4. Measure after costs — slippage and commission already baked in (5bps + $0.005/share)

**PDT rule (US traders):** Four or more day trades in five business days in a
margin account with < $25k equity triggers Pattern Day Trader requirements.
Paper trading with ETFs on this system avoids PDT concerns entirely.

**Backtest overfitting warning:** More variants = higher chance of false positives.
Fix the rules first, run once, accept the result. If you tweak parameters until
it looks good, the result is not a strategy — it is a curve fit.

---

## 10. Reminders

- **Start simple.** A strategy that has 3 clear rules beats a strategy with 10 tuned parameters.
- **Test period must include a bear market or volatile period**, not just a bull run.
- **Slippage and commission matter.** The backtest already applies 5bps slippage and $0.005/share commission. Do not ignore this in evaluation.
- **Overfitting check:** if the strategy only works for one specific ticker in one specific year, it's not a strategy.
- **Paper trading is not validation.** 10 days of paper trading is observational only. Treat it as a sanity check, not a performance benchmark.
- **Document failures.** A rejected strategy with a clear reason why is valuable. Do not delete run notes.
