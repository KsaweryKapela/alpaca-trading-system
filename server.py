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
            experiments.append({
                "slug": data.get("slug", path.stem),
                "status": data.get("status", "in_progress"),
                "ran_at": data.get("ran_at"),
                "rules": data.get("rules", []),
                "metadata": data.get("metadata", {}),
                "metrics": data.get("metrics", {}),
                "extended_metrics": data.get("extended_metrics", {}),
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
