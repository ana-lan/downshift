"""Snapshot test for render_markdown against the real SupportDesk example.

Run with UPDATE_SNAPSHOTS=1 to regenerate the golden file.
"""

from __future__ import annotations

import os
from pathlib import Path

from downshift.config import load_config
from downshift.report import build_report, render_markdown
from downshift.schema import ScanResult

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "supportdesk"
SNAPSHOT = REPO_ROOT / "tests" / "snapshots" / "supportdesk_report.md"


def test_supportdesk_report_snapshot() -> None:
    audit = EXAMPLE / "downshift.audit.json"
    evals_dir = EXAMPLE / "evals"
    results_dir = EXAMPLE / "results"
    cfg = load_config(EXAMPLE / "downshift.yaml")
    scan = ScanResult.load(audit)

    report = build_report(scan, cfg, evals_dir, results_dir)
    md = render_markdown(report)

    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(md, encoding="utf-8")
        return

    assert SNAPSHOT.is_file(), (
        f"Snapshot not found: {SNAPSHOT}. Run with UPDATE_SNAPSHOTS=1 to generate it."
    )
    expected = SNAPSHOT.read_text(encoding="utf-8")
    assert md == expected, (
        "render_markdown output differs from snapshot. Run with UPDATE_SNAPSHOTS=1 to update it."
    )
