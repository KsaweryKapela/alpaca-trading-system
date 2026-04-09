"""Build static dashboard data from experiment reports and run notes."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


RUN_STATUS_ORDER = ["In Progress", "Promising", "Revised", "Rejected", "Complete", "Unknown"]


def _parse_status(markdown: str) -> str:
    for label in RUN_STATUS_ORDER:
        if label == "Unknown":
            continue
        pattern = rf"\[x\]\s*{re.escape(label)}"
        if re.search(pattern, markdown, flags=re.IGNORECASE):
            return label
    return "Unknown"


def _extract_field(markdown: str, labels: List[str]) -> Optional[str]:
    for label in labels:
        match = re.search(rf"\*\*{re.escape(label)}:\*\*\s*(.+)", markdown)
        if match:
            return match.group(1).strip()
    return None


def _extract_markdown_metric(markdown: str, labels: List[str]) -> Optional[float]:
    for label in labels:
        pattern = rf"\|\s*{re.escape(label)}\s*\|\s*([^\|\n]+)\|"
        match = re.search(pattern, markdown, flags=re.IGNORECASE)
        if not match:
            pattern = rf"{re.escape(label)}:\s*([^\n]+)"
            match = re.search(pattern, markdown, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip().replace("$", "").replace("%", "")
            value = value.replace(",", "").replace("−", "-")
            value = value.split("—")[0].strip()
            if value in {"", "N/A", "(pending)", "pending"}:
                return None
            try:
                return float(value)
            except ValueError:
                continue
    return None


def parse_run_note(path: Path) -> Dict:
    markdown = path.read_text(encoding="utf-8")
    title_match = re.search(r"^#\s+(.+)$", markdown, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem

    return {
        "slug": path.stem,
        "title": title,
        "status": _parse_status(markdown),
        "date": _extract_field(markdown, ["Date", "Date started"]),
        "summary": {
            "total_return_pct": _extract_markdown_metric(markdown, ["Total return"]),
            "sharpe_ratio": _extract_markdown_metric(markdown, ["Sharpe ratio", "Sharpe ratio (daily)"]),
            "max_drawdown_pct": _extract_markdown_metric(markdown, ["Max drawdown"]),
            "round_trips": _extract_markdown_metric(markdown, ["Round trips"]),
            "win_rate_pct": _extract_markdown_metric(markdown, ["Win rate"]),
            "profit_factor": _extract_markdown_metric(markdown, ["Profit factor"]),
            "final_equity": _extract_markdown_metric(markdown, ["Final equity"]),
        },
        "report_path": None,
    }


def _status_rank(status: str) -> int:
    try:
        return RUN_STATUS_ORDER.index(status)
    except ValueError:
        return len(RUN_STATUS_ORDER)


def build_dashboard_data(project_root: Path) -> Dict:
    project_root = project_root.resolve()
    runs_dir = project_root / "experiments" / "runs"
    reports_dir = project_root / "experiments" / "reports"
    frontend_dir = project_root / "frontend" / "data"
    frontend_reports_dir = frontend_dir / "reports"

    frontend_reports_dir.mkdir(parents=True, exist_ok=True)
    report_slugs = set()
    runs = []

    for run_note in sorted(runs_dir.glob("*.md")):
        entry = parse_run_note(run_note)
        report_file = reports_dir / f"{run_note.stem}.json"
        if report_file.exists():
            report_slugs.add(run_note.stem)
            with report_file.open("r", encoding="utf-8") as handle:
                report = json.load(handle)
            entry["report_path"] = f"data/reports/{report_file.name}"
            entry["summary"] = {
                "total_return_pct": report.get("metrics", {}).get("total_return_pct"),
                "sharpe_ratio": report.get("metrics", {}).get("sharpe_ratio"),
                "max_drawdown_pct": report.get("metrics", {}).get("max_drawdown_pct"),
                "round_trips": report.get("extended_metrics", {}).get("round_trips"),
                "win_rate_pct": report.get("extended_metrics", {}).get("win_rate_pct"),
                "profit_factor": report.get("extended_metrics", {}).get("profit_factor"),
                "final_equity": report.get("metrics", {}).get("final_equity"),
            }
            entry["metadata"] = report.get("metadata", {})
            shutil.copyfile(report_file, frontend_reports_dir / report_file.name)
        runs.append(entry)

    for extra_report in frontend_reports_dir.glob("*.json"):
        if extra_report.stem not in report_slugs:
            extra_report.unlink()

    runs.sort(
        key=lambda item: (
            item.get("date") or "",
            -_status_rank(item.get("status", "Unknown")),
            item["slug"],
        ),
        reverse=True,
    )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs": runs,
    }
    frontend_dir.mkdir(parents=True, exist_ok=True)
    with (frontend_dir / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    return manifest
