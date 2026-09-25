from __future__ import annotations

from pathlib import Path

import pytest

from downshift.evals import load_eval_set, slug_for
from downshift.llm import OpenAICompatClient
from downshift.runner import Runner, load_results, results_path
from downshift.schema import ScanResult

pytestmark = pytest.mark.integration

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "supportdesk"


def test_run_classify_on_ollama(tmp_path: Path) -> None:
    site = next(
        s
        for s in ScanResult.load(EXAMPLE / "downshift.audit.json").call_sites
        if s.function == "classify_category"
    )
    eval_set = load_eval_set(EXAMPLE / "evals" / f"{slug_for(site.id)}.jsonl")
    client = OpenAICompatClient("http://localhost:11434/v1")
    summary = Runner(client, results_dir=tmp_path, limit=2).run_site(site, eval_set, "qwen2.5:0.5b")
    assert summary.errors == 0
    assert summary.scored == 2
    rows = load_results(results_path(tmp_path, site.id, "qwen2.5:0.5b"))
    assert all(r.prompt_tokens > 0 and r.latency_s > 0 for r in rows.values())
