from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from downshift.evals import EvalSet, load_eval_set, render_messages, slug_for
from downshift.llm import FakeLLMClient, LLMError
from downshift.runner import (
    WARMUP_MESSAGES,
    ResultRow,
    Runner,
    append_row,
    load_results,
    model_filename,
    results_path,
    summarize_rows,
)
from downshift.schema import CallSite, ScanResult
from downshift.scorer import JUDGE_SYSTEM, Judge

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "supportdesk"
AUDIT = EXAMPLE / "downshift.audit.json"
EVALS = EXAMPLE / "evals"


@pytest.fixture(scope="module")
def sites() -> dict[str, CallSite]:
    return {s.function: s for s in ScanResult.load(AUDIT).call_sites}


def eval_set_for(site: CallSite) -> EvalSet:
    return load_eval_set(EVALS / f"{slug_for(site.id)}.jsonl")


def answer_key_client(site: CallSite, eval_set: EvalSet) -> FakeLLMClient:
    """A fake model that returns each case's expected answer."""
    key: dict[str, str] = {}
    for case in eval_set.cases:
        msgs = render_messages(site, eval_set.inputs_for(case))
        expected = case.expected
        key[json.dumps(msgs, sort_keys=True)] = (
            expected if isinstance(expected, str) else json.dumps(expected)
        )
    return FakeLLMClient(lambda model, msgs: key.get(json.dumps(msgs, sort_keys=True), "OK"))


# --- helpers --------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("qwen2.5:7b", "qwen2.5-7b"),
        ("gpt-4o-mini", "gpt-4o-mini"),
        ("org/model:tag", "org-model-tag"),
        (":::", "model"),
    ],
)
def test_model_filename(model: str, expected: str) -> None:
    assert model_filename(model) == expected


def test_results_path(tmp_path: Path) -> None:
    path = results_path(tmp_path, "supportdesk/triage.py::classify_category", "qwen2.5:7b")
    assert path == tmp_path / "supportdesk.triage__classify_category" / "qwen2.5-7b.jsonl"


def test_result_row_round_trip() -> None:
    row = ResultRow(
        "c1",
        "m",
        output="x",
        prompt_tokens=3,
        completion_tokens=1,
        latency_s=0.12345,
        score=1.0,
        passed=True,
        detail="match",
    )
    data = row.to_dict()
    assert data["latency_s"] == 0.123
    assert ResultRow.from_dict({**data, "extra": 1}) == replace(row, latency_s=0.123)
    assert row.ok
    assert not ResultRow("c1", "m", error="boom").ok
    assert not ResultRow("c1", "m").ok


def test_load_results_missing_file(tmp_path: Path) -> None:
    assert load_results(tmp_path / "nope.jsonl") == {}


def test_load_results_skips_bad_lines_and_last_row_wins(tmp_path: Path) -> None:
    path = tmp_path / "r.jsonl"
    lines = [
        json.dumps(ResultRow("a", "m", error="boom").to_dict()),
        "not json",
        "[1, 2]",
        json.dumps({"model": "m"}),
        "",
        json.dumps(ResultRow("a", "m", score=1.0, passed=True).to_dict()),
        json.dumps(ResultRow("b", "m", score=0.0, passed=False).to_dict()),
    ]
    path.write_text("\n".join(lines) + "\n")
    rows = load_results(path)
    assert set(rows) == {"a", "b"}
    assert rows["a"].ok


def test_append_row_repairs_truncated_line(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "r.jsonl"
    append_row(path, ResultRow("a", "m", score=1.0, passed=True))
    with path.open("a") as fh:
        fh.write('{"case_id": "b", "mod')
    append_row(path, ResultRow("c", "m", score=1.0, passed=True))
    assert set(load_results(path)) == {"a", "c"}


def test_summarize_rows() -> None:
    rows = {
        "a": ResultRow(
            "a", "m", prompt_tokens=10, completion_tokens=2, latency_s=1.0, score=1.0, passed=True
        ),
        "b": ResultRow(
            "b", "m", prompt_tokens=20, completion_tokens=4, latency_s=3.0, score=0.5, passed=False
        ),
        "c": ResultRow("c", "m", error="boom"),
        "old": ResultRow("old", "m", score=1.0, passed=True),
    }
    s = summarize_rows("site", "m", ["a", "b", "c", "d"], rows, new=2)
    assert (s.cases, s.scored, s.passed, s.errors, s.new) == (4, 2, 1, 1, 2)
    assert s.pass_rate == 0.5
    assert s.mean_score == 0.75
    assert s.avg_latency_s == 2.0
    assert s.avg_prompt_tokens == 15
    assert s.avg_completion_tokens == 3


def test_summarize_rows_empty() -> None:
    s = summarize_rows("site", "m", ["a"], {})
    assert s.pass_rate is None
    assert s.mean_score is None
    assert s.avg_latency_s is None


# --- runner ---------------------------------------------------------------


def test_run_exact_site_all_pass(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["classify_category"]
    eval_set = eval_set_for(site)
    client = answer_key_client(site, eval_set)
    summary = Runner(client, results_dir=tmp_path, limit=5).run_site(site, eval_set, "cand")
    assert (summary.cases, summary.scored, summary.passed, summary.errors, summary.new) == (
        5,
        5,
        5,
        0,
        5,
    )
    warm, *calls = client.calls
    assert warm.messages == WARMUP_MESSAGES
    assert warm.max_tokens == 5
    assert len(calls) == 5
    assert calls[0].temperature == float(site.temperature or 0.0)
    assert calls[0].max_tokens == site.max_tokens
    assert calls[0].json_mode is False
    rows = load_results(results_path(tmp_path, site.id, "cand"))
    assert list(rows) == [c.id for c in eval_set.cases[:5]]


def test_run_json_site_uses_json_mode(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["extract_order_info"]
    eval_set = eval_set_for(site)
    client = answer_key_client(site, eval_set)
    summary = Runner(client, results_dir=tmp_path, limit=4).run_site(site, eval_set, "cand")
    assert summary.passed == 4
    assert client.calls[1].json_mode is True


def test_run_is_resumable(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["classify_category"]
    eval_set = eval_set_for(site)
    Runner(answer_key_client(site, eval_set), results_dir=tmp_path, limit=3).run_site(
        site, eval_set, "cand"
    )

    again = answer_key_client(site, eval_set)
    s = Runner(again, results_dir=tmp_path, limit=3).run_site(site, eval_set, "cand")
    assert (s.new, s.passed) == (0, 3)
    assert again.calls == []

    more = answer_key_client(site, eval_set)
    s = Runner(more, results_dir=tmp_path, limit=5).run_site(site, eval_set, "cand")
    assert (s.new, s.passed) == (2, 5)
    assert len(more.calls) == 3  # warm-up + 2 new cases


def test_model_error_is_recorded_then_retried(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["classify_category"]
    eval_set = eval_set_for(site)

    def flaky(model: str, msgs: list[dict[str, str]]) -> str:
        if msgs == WARMUP_MESSAGES:
            return "OK"
        raise LLMError("model down")

    s = Runner(FakeLLMClient(flaky), results_dir=tmp_path, limit=2).run_site(site, eval_set, "cand")
    assert (s.errors, s.scored) == (2, 0)
    row = load_results(results_path(tmp_path, site.id, "cand"))[eval_set.cases[0].id]
    assert row.error == "model down"

    s = Runner(answer_key_client(site, eval_set), results_dir=tmp_path, limit=2).run_site(
        site, eval_set, "cand"
    )
    assert (s.errors, s.passed, s.new) == (0, 2, 2)


def _judge_responder(model: str, msgs: list[dict[str, str]]) -> str:
    if msgs[0]["content"] == JUDGE_SYSTEM:
        return '{"score": 5, "reason": "fine"}'
    return "Thanks for reaching out, we are on it."


def test_run_judge_site(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["draft_reply"]
    eval_set = eval_set_for(site)
    client = FakeLLMClient(_judge_responder)
    runner = Runner(client, results_dir=tmp_path, judge=Judge(client, "judge-m"), limit=2)
    s = runner.run_site(site, eval_set, "cand")
    assert s.passed == 2
    warmed = [c.model for c in client.calls if c.messages == WARMUP_MESSAGES]
    assert warmed == ["cand", "judge-m"]
    judged = [c for c in client.calls if c.model == "judge-m" and c.messages != WARMUP_MESSAGES]
    assert len(judged) == 2
    rows = load_results(results_path(tmp_path, site.id, "cand"))
    assert all(r.judge_score == 5 for r in rows.values())


def test_judge_site_without_judge_records_error(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["draft_reply"]
    eval_set = eval_set_for(site)
    s = Runner(FakeLLMClient(_judge_responder), results_dir=tmp_path, limit=2).run_site(
        site, eval_set, "cand"
    )
    assert s.errors == 2
    row = load_results(results_path(tmp_path, site.id, "cand"))[eval_set.cases[0].id]
    assert row.error is not None
    assert row.error.startswith("scoring failed")
    assert row.output


def test_judge_error_keeps_output(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["draft_reply"]
    eval_set = eval_set_for(site)

    def responder(model: str, msgs: list[dict[str, str]]) -> str:
        if model == "judge-m" and msgs != WARMUP_MESSAGES:
            raise LLMError("judge down")
        return "A reply."

    client = FakeLLMClient(responder)
    runner = Runner(client, results_dir=tmp_path, judge=Judge(client, "judge-m"), limit=1)
    s = runner.run_site(site, eval_set, "cand")
    assert s.errors == 1
    row = load_results(results_path(tmp_path, site.id, "cand"))[eval_set.cases[0].id]
    assert row.error == "scoring failed: judge down"
    assert row.output == "A reply."
    assert row.prompt_tokens > 0


def test_warmup_failure_propagates_and_writes_nothing(
    tmp_path: Path, sites: dict[str, CallSite]
) -> None:
    site = sites["classify_category"]
    eval_set = eval_set_for(site)
    with pytest.raises(LLMError):
        Runner(FakeLLMClient({"other": "x"}), results_dir=tmp_path, limit=1).run_site(
            site, eval_set, "cand"
        )
    assert not results_path(tmp_path, site.id, "cand").exists()


def test_warm_up_once_per_model_and_skippable(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["classify_category"]
    eval_set = eval_set_for(site)
    other = sites["lang_of"]

    client = answer_key_client(site, eval_set)
    runner = Runner(client, results_dir=tmp_path, limit=1)
    runner.run_site(site, eval_set, "cand")
    runner.run_site(other, eval_set_for(other), "cand")
    assert sum(1 for c in client.calls if c.messages == WARMUP_MESSAGES) == 1

    no_warm = answer_key_client(site, eval_set)
    Runner(no_warm, results_dir=tmp_path / "b", limit=1, warmup=False).run_site(
        site, eval_set, "cand"
    )
    assert all(c.messages != WARMUP_MESSAGES for c in no_warm.calls)


def test_on_case_callback(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["classify_category"]
    eval_set = eval_set_for(site)
    seen: list[ResultRow] = []
    Runner(
        answer_key_client(site, eval_set), results_dir=tmp_path, limit=2, on_case=seen.append
    ).run_site(site, eval_set, "cand")
    assert [r.case_id for r in seen] == [c.id for c in eval_set.cases[:2]]
