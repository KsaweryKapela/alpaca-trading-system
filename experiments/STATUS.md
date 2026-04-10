# Experiment Status

> Auto-updated by run_experiment.py after each run. Edit the Decision section manually.

## Best Configuration Found

- **Slug:** 010_gap_dn_only
- **Strategy:** Gap Fill — down_only
- **Status:** revised (near-breakeven, not yet promising)
- **Params:** min_gap=0.5%, max_gap=2.0%, stop_mult=0.5, fill_target=100%, down_only
- **Symbols:** SPY, QQQ, AAPL, MSFT, NVDA
- **Total return:** -0.06%
- **Monthly return:** -0.02%
- **Sharpe:** -0.15  ← best of all runs
- **PF:** 0.97       ← best of all runs
- **Max drawdown:** -0.83%
- **Win rate:** 45.7%
- **Round trips:** 81

## Run Summary (newest first)

| # | Slug | Strategy | Sharpe | PF | WR | Status |
|---|---|---|---|---|---|---|
| 013 | gap_universe | Gap Fill both, 8 syms | -1.54 | 0.75 | 39.1% | rejected |
| 012 | gap_tightstop | Gap Fill dn, stop 0.3× | -1.43 | 0.76 | 37.0% | rejected |
| 011 | gap_partial | Gap Fill dn, 70% fill | -1.06 | 0.83 | 46.9% | rejected |
| **010** | **gap_dn_only** | **Gap Fill dn only** | **-0.15** | **0.97** | **45.7%** | **revised** |
| 009 | gap_up_only | Gap Fill up only | -2.83 | 0.66 | 46.8% | rejected |
| 008 | gap_fill_r2 | Gap Fill 0.7% min | -2.72 | 0.69 | 43.7% | rejected |
| 007 | gap_fill_r1 | Gap Fill 0.5% min | -1.85 | 0.81 | 46.2% | revised |
| 006 | gap_fill | Gap Fill 0.3% min | -2.57 | 0.75 | 43.9% | revised |
| 005 | vwap_mom | VWAP Momentum | -7.11 | 0.66 | 36.5% | rejected |
| 004 | vwap_nostop | VWAP Rev no stop | -4.50 | 0.56 | 57.8% | rejected |
| 003 | vwap_r1 | VWAP Rev 0.6% | -4.61 | 0.72 | 42.7% | revised |
| 002 | vwap | VWAP Rev 0.3% | -9.00 | 0.55 | 54.0% | revised |
| 001 | orb | ORB 15min | -3.44 | 0.70 | 35.8% | rejected |

## Key Learnings

- **Jan-Apr 2026 regime**: High volatility, trending down. Mean reversion and pure ORB fail.
- **VWAP reversion**: Direction right (58% WR) but payoff inverted. Losses too large.
- **VWAP momentum**: Wrong direction (37% WR). Consistent with mean-reverting market.
- **Gap fills**: Best family. Gap-downs fill more reliably than gap-ups in this regime.
- **Optimal found**: gap_fill, down_only, 0.5% min gap, stop at 50% of gap, full fill target.

## Next Action

Explore WR filters for gap-down strategy to push above 50% WR and PF > 1.0:
- Volume spike filter (gap-down with high relative volume = panic = more likely to bounce)
- SPY breadth filter (only trade individual stock gap-downs when SPY itself is NOT gapping down)
- Or: explore a different strategy family (opening range expansion at 10:00 ET)
