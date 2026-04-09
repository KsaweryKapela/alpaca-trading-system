# CLAUDE.md — Operating Manual for Strategy Research & Backtesting

This file defines how I work inside this repo.  
It is my task loop, process guide, and decision framework for iterative strategy research.  
For now, the scope is research only: design tests, run backtests, evaluate results, and identify promising strategies.  
I read this at the start of every session to know where I am and what to do next.

---

## 1. Current State

> **Update this section at the end of every session.**

- **Active strategy:** RSI mean reversion daily (Run 005)
- **Phase:** Not yet started
- **Last run:** 004 — SMA 20/50 daily SPY+QQQ 2015-2026 — PROMISING (Sharpe 0.69, PF 3.32, +21.58%)
- **Next action:** Research RSI daily reversion, implement `trading/strategy/rsi_reversion.py`, run backtest SPY+QQQ daily 2015-2026. Log in `experiments/runs/005_rsi_reversion.md`.

---

## 2. The Iteration Loop

Each cycle follows these steps in order. Do not skip steps.

```
1. RESEARCH → Before picking a strategy, synthesize what the previous run taught us.
               Ask: what market behaviour did we observe? what failed and why?
               Use web search to cross-check ideas against known academic/practitioner
               literature (e.g. "VWAP reversion edge academic" or "5m ORB SPY edge 2023").
               Summarise findings in the ## Next Step block of the previous run note,
               or in a dedicated ## Research section if there is no prior run.
               Only pick a strategy once the reasoning is written down.

2. PICK    → Choose one strategy idea. Write down the hypothesis before touching code.
              Log the hypothesis immediately in the run note and `experiments/STATUS.md`.

3. BUILD   → Implement or adapt only the minimum code needed to run a valid backtest.
              Do not build deployment or paper-trading workflow in this step.
              Log exactly what was added or changed before moving on.

4. TEST    → Run backtest. Use at least 2 years of data when the source allows it.
              Test on 2+ symbols or 2+ distinct windows.
              Log configuration and raw results immediately after each test run.

5. FIX     → If you notice a bug, data issue, metric bug, execution flaw, or invalid
              assumption, fix it before continuing.
              Log the issue, the root cause, and the fix immediately.

6. EVAL    → Score against candidate criteria (see Section 4). Review ALL extended metrics
              (win rate, profit factor, expectancy, max consec losses, avg duration).
              For intraday strategies: run walk_forward() and check avg test Sharpe ≥ 0.3.
              Log the evaluation before making a decision.

7. DECIDE  → Reject / Revise / Mark as promising candidate.
              Log the decision and the exact reason immediately.

8. REPEAT  → Go back to step 1. Do not stop between cycles.
```

Do not stop between cycles unless a strategy is marked **Promising** and needs human review before the next step. Otherwise keep running.  
No paper trading or live deployment is part of the current loop.

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

## 4. Candidate Criteria (Backtest → Promising)

A strategy should meet **all** of the following before being marked as a promising candidate:

| Criterion | Minimum threshold |
|---|---|
| Sharpe ratio (annualized, daily) | ≥ 0.5 |
| Max drawdown | ≤ 25% |
| Total return | Positive over full test period |
| Number of trades | ≥ 15 (enough signal frequency to be meaningful) |
| Test period | ≥ 2 full years |
| Symbols tested | ≥ 2 different symbols or time windows |
| Consistency | Results not wildly different across tested symbols |

**Note on Sharpe:** The backtest engine resamples the equity curve to daily frequency before computing Sharpe. The annualization factor is always √252 regardless of bar interval. This avoids the "5m bars inflate Sharpe by √78" bug.

**Extended metrics to review** (printed by `print_summary()`):
- Win rate — below 40% is a warning sign even if overall return is positive
- Profit factor — gross wins / gross losses; ≥ 1.5 is a reasonable bar
- Expectancy — average dollar P&L per round trip; negative = losing strategy
- Max consecutive losses — if > 5, ensure drawdown is still within tolerance
- Avg trade duration — sanity-check against strategy intent (ORB should be hours, not days)

**Walk-forward check** (run before promoting any intraday strategy):
```python
from trading.research.walk_forward import walk_forward, print_walk_forward_summary
from trading.data.historical import load_bars_alpaca

symbol_dfs = load_bars_alpaca(["SPY"], start, end, api_key, secret_key, interval="5m")
results = walk_forward(engine, lambda: ORBStrategy(["SPY"]), symbol_dfs, train_days=90, test_days=30)
print_walk_forward_summary(results)
```
Require: avg test-window Sharpe ≥ 0.3 AND positive folds ≥ 50% before marking as promising.

If a strategy passes most criteria with a compelling hypothesis, it may still be marked promising, but this must be explicitly justified in the run note.

**Hard rules:**
- No strategy is marked promising without a completed run note in `experiments/runs/`.
- No strategy is marked promising based on a single symbol test.
- If results are marginal, mark it as "revise" instead of "promising".

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

## 6. Current Scope

Current workflow stops at research output:

- Define the hypothesis.
- Build only enough code to test it.
- Run backtests and walk-forward checks.
- Log the results.
- Classify the idea as rejected, revised, or promising.

Do not add paper-trading or live-deployment work unless the repo goals are explicitly expanded.

---

## 7. Run Note Template

Every run gets a file in `experiments/runs/`. Copy this template exactly.

---

```markdown
# Run NNN — <Strategy Name>

**Date:** YYYY-MM-DD  
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising  [ ] Complete

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
| Key parameters | |
| Data source | yfinance / alpaca |
| Bar interval | |
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

    (output)

## Walk-Forward (intraday strategies only)

    (paste print_walk_forward_summary() output, or "N/A — daily strategy")

Avg test Sharpe: | Positive folds:

## Evaluation

Score against candidate criteria:

- [ ] Sharpe ≥ 0.5 (daily, annualized)
- [ ] Max drawdown ≤ 25%
- [ ] Positive total return
- [ ] ≥ 15 round trips
- [ ] ≥ 2 years tested (or justified exception for Alpaca free tier)
- [ ] ≥ 2 symbols / windows tested
- [ ] Win rate ≥ 40% OR profit factor ≥ 1.5
- [ ] Walk-forward avg test Sharpe ≥ 0.3 (intraday only)

Observations:

## Decision

**[ ] Reject** — reason:  
**[ ] Revise** — what to change, then re-run:  
**[ ] Mark as promising** — justification:  

---

---

## Final Conclusion

What did we learn? What worked, what didn't, what to try next?

## Next Step

What is the next strategy to test, or the next revision of this one?
```

---

## 8. How to Continue After a Completed Cycle

When a cycle is marked **Complete**:

1. Update `Current State` (Section 1 of this file) with the next strategy.
2. Update `experiments/STATUS.md` to match.
3. Create a new run note file for the next strategy.
4. Start at step 1 of the iteration loop.

Do not carry forward vague intentions. The `Next Step` field in every run note must name a specific next strategy or revision. That is the input to the next cycle.

---

## 9. Code Modification Rules

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

## 10. Realistic Scope of This System

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

## 11. Reminders

- **Start simple.** A strategy that has 3 clear rules beats a strategy with 10 tuned parameters.
- **Test period must include a bear market or volatile period**, not just a bull run.
- **Slippage and commission matter.** The backtest already applies 5bps slippage and $0.005/share commission. Do not ignore this in evaluation.
- **Overfitting check:** if the strategy only works for one specific ticker in one specific year, it's not a strategy. Use `walk_forward()` before promoting any intraday strategy.
- **Paper trading is not validation.** 10 days of paper trading is observational only. Treat it as a sanity check, not a performance benchmark.
- **Document failures.** A rejected strategy with a clear reason why is valuable. Do not delete run notes.
