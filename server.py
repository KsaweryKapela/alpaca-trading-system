"""Frontend server — serves completed experiment results only.

Claude runs experiments via:
  .venv/bin/python run_experiment.py --strategy orb --symbols SPY QQQ ...

The frontend reads the saved reports; it does NOT trigger backtests.

Endpoints:
  GET /                            → frontend/index.html
  GET /api/experiments             → list all saved experiments (metadata + metrics)
  GET /api/experiments/<slug>      → full data for one experiment
  GET /api/universe                → full asset universe

Run with:
  .venv/bin/python server.py
"""

import json
import logging
import os
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="frontend", static_url_path="")

ROOT = Path(__file__).parent
FRONTEND_DIR = ROOT / "frontend"
REPORTS_DIR = ROOT / "experiments" / "reports"

from trading.config import STOCKS, ETFS, DEFAULT_UNIVERSE


def _per_symbol_from_txns(transactions: list, initial_equity: float) -> dict:
    """Derive per-symbol metrics from the stored transaction list.
    Used to backfill old reports that predate the per_symbol_metrics field.
    Each exit transaction (pnl != null) is treated as one round-trip result.
    """
    fills: dict = {}
    total_pnl: dict = {}
    round_trips: dict = {}
    wins: dict = {}
    gross_win: dict = {}
    gross_loss: dict = {}

    for t in transactions:
        sym = t.get("asset")
        if not sym:
            continue
        fills[sym] = fills.get(sym, 0) + 1
        p = t.get("pnl")
        if p is not None:
            total_pnl[sym] = total_pnl.get(sym, 0.0) + p
            round_trips[sym] = round_trips.get(sym, 0) + 1
            if p > 0:
                wins[sym] = wins.get(sym, 0) + 1
                gross_win[sym] = gross_win.get(sym, 0.0) + p
            else:
                gross_loss[sym] = gross_loss.get(sym, 0.0) + abs(p)

    result = {}
    for sym in fills:
        tp = round(total_pnl.get(sym, 0.0), 2)
        rt = round_trips.get(sym, 0)
        w = wins.get(sym, 0)
        gw = gross_win.get(sym, 0.0)
        gl = gross_loss.get(sym, 0.0)
        result[sym] = {
            "total_pnl": tp,
            "return_pct": round(tp / initial_equity * 100, 2) if initial_equity else None,
            "fills": fills[sym],
            "round_trips": rt,
            "win_count": w,
            "gross_win": round(gw, 2),
            "gross_loss": round(gl, 2),
            "win_rate_pct": round(w / rt * 100, 1) if rt else None,
            "profit_factor": round(gw / gl, 2) if gl > 0 else None,
            "expectancy": round(tp / rt, 2) if rt else None,
        }
    return result


# ── Static ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ── API ───────────────────────────────────────────────────────────────────────

@app.route("/api/universe")
def universe():
    return jsonify({"stocks": STOCKS, "etfs": ETFS, "all": DEFAULT_UNIVERSE})


@app.route("/api/experiments")
def list_experiments():
    """List all saved experiment reports, newest first.
    Returns only slug, status, ran_at, metadata, metrics, extended_metrics —
    not the full transaction/calendar lists which are only fetched on demand.
    """
    experiments = []
    for path in sorted(REPORTS_DIR.glob("*.json"), reverse=True):
        try:
            with path.open() as f:
                data = json.load(f)
            ps = data.get("per_symbol_metrics") or {}
            if not ps:
                # Backfill from stored transactions for reports generated before
                # per_symbol_metrics was added to to_dict()
                txns = data.get("transactions", [])
                init_eq = (data.get("metrics") or {}).get("initial_equity", 100000)
                ps = _per_symbol_from_txns(txns, init_eq)
            experiments.append({
                "slug": data.get("slug", path.stem),
                "status": data.get("status", "in_progress"),
                "ran_at": data.get("ran_at"),
                "rules": data.get("rules", []),
                "metadata": data.get("metadata", {}),
                "metrics": data.get("metrics", {}),
                "extended_metrics": data.get("extended_metrics", {}),
                "per_symbol_metrics": ps,
            })
        except Exception as e:
            logger.warning("Skipping unreadable report %s: %s", path.name, e)
    return jsonify(experiments)


@app.route("/api/experiments/<slug>")
def get_experiment(slug):
    path = REPORTS_DIR / f"{slug}.json"
    if not path.exists():
        return jsonify({"error": f"Experiment '{slug}' not found"}), 404
    with path.open() as f:
        return jsonify(json.load(f))


if __name__ == "__main__":
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    port = int(os.environ.get("PORT", 5000))
    logger.info("Starting viewer at http://localhost:%d", port)
    app.run(debug=True, port=port, use_reloader=False)
