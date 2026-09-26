from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from downshift.evals import EvalSet, load_eval_set, slug_for
from downshift.llm import FakeLLMClient, LLMError
from downshift.runner import WARMUP_MESSAGES, Runner, load_results, rescore_site, results_path
from downshift.schema import CallSite, ScanResult
from downshift.scorer import JUDGE_SYSTEM, Judge

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "supportdesk"
AUDIT = EXAMPLE / "downshift.audit.json"
EVALS = EXAMPLE / "evals"
REPLY = "Thanks for reaching out, we are on it."


@pytest.fixture(scope="module")
def sites() -> dict[str, CallSite]:
    return {s.function: s for s in ScanResult.load(AUDIT).call_sites}


def small(site: CallSite, n: int) -> EvalSet:
    full = load_eval_set(EVALS / f"{slug_for(site.id)}.jsonl")
    return EvalSet(path=full.path, cases=full.cases[:n], shared=full.shared)


def responder_with(score: int | None) -> Callable[[str, list[dict[str, str]]], str]:
    def responder(model: str, msgs: list[dict[str, str]]) -> str:
        if msgs[0]["content"] == JUDGE_SYSTEM:
            if score is None:
                raise LLMError("rate limited")
            return f'{{"score": {score}}}'
        return REPLY

    return responder


def seed(tmp_path: Path, site: CallSite, eval_set: EvalSet) -> None:
    client = FakeLLMClient(responder_with(5))
    Runner(client, results_dir=tmp_path, judge=Judge(client, "old-j")).run_site(
        site, eval_set, "cand"
    )


def rows_for(tmp_path: Path, site: CallSite):  # type: ignore[no-untyped-def]
    return load_results(results_path(tmp_path, site.id, "cand"))


def test_run_records_judge_model(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["draft_reply"]
    seed(tmp_path, site, small(site, 2))
    assert {r.judge_model for r in rows_for(tmp_path, site).values()} == {"old-j"}


def test_run_exact_rows_have_no_judge_model(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["classify_category"]
    Runner(FakeLLMClient("billing"), results_dir=tmp_path).run_site(site, small(site, 1), "cand")
    row = next(iter(rows_for(tmp_path, site).values()))
    assert row.judge_model is None


def test_hosted_judge_is_warmed_on_its_own_client(
    tmp_path: Path, sites: dict[str, CallSite]
) -> None:
    site = sites["draft_reply"]
    main = FakeLLMClient(responder_with(5))
    hosted = FakeLLMClient(responder_with(5))
    Runner(main, results_dir=tmp_path, judge=Judge(hosted, "big")).run_site(
        site, small(site, 1), "cand"
    )
    assert [c.model for c in main.calls if c.messages == WARMUP_MESSAGES] == ["cand"]
    assert [c.model for c in hosted.calls if c.messages == WARMUP_MESSAGES] == ["big"]
    assert all(c.messages[0]["content"] != JUDGE_SYSTEM for c in main.calls)


def test_rescore_regrades_without_calling_the_model(
    tmp_path: Path, sites: dict[str, CallSite]
) -> None:
    site = sites["draft_reply"]
    eval_set = small(site, 3)
    seed(tmp_path, site, eval_set)
    judge_client = FakeLLMClient(responder_with(2))
    before, after = rescore_site(
        site, eval_set, "cand", results_dir=tmp_path, judge=Judge(judge_client, "new-j")
    )
    assert (before.passed, before.scored) == (3, 3)
    assert (after.passed, after.scored, after.new) == (0, 3, 3)
    assert len(judge_client.calls) == 3
    assert all(c.model == "new-j" for c in judge_client.calls)
    rows = rows_for(tmp_path, site).values()
    assert all(r.judge_model == "new-j" and r.judge_score == 2 for r in rows)
    assert all(r.output == REPLY for r in rows)


def test_rescore_is_resumable(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["draft_reply"]
    eval_set = small(site, 2)
    seed(tmp_path, site, eval_set)
    rescore_site(
        site,
        eval_set,
        "cand",
        results_dir=tmp_path,
        judge=Judge(FakeLLMClient(responder_with(4)), "new-j"),
    )
    again = FakeLLMClient(responder_with(4))
    _, after = rescore_site(
        site, eval_set, "cand", results_dir=tmp_path, judge=Judge(again, "new-j")
    )
    assert after.new == 0
    assert after.passed == 2
    assert again.calls == []


def test_rescore_judge_errors_are_retried(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["draft_reply"]
    eval_set = small(site, 3)
    seed(tmp_path, site, eval_set)
    _, after = rescore_site(
        site,
        eval_set,
        "cand",
        results_dir=tmp_path,
        judge=Judge(FakeLLMClient(responder_with(None)), "new-j"),
    )
    assert (after.errors, after.scored) == (3, 0)
    row = rows_for(tmp_path, site)[eval_set.cases[0].id]
    assert row.error == "scoring failed: rate limited"
    assert row.output == REPLY
    assert row.judge_score is None

    _, after = rescore_site(
        site,
        eval_set,
        "cand",
        results_dir=tmp_path,
        judge=Judge(FakeLLMClient(responder_with(5)), "new-j"),
    )
    assert (after.errors, after.passed, after.new) == (0, 3, 3)


def test_rescore_skips_model_errors(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["draft_reply"]
    eval_set = small(site, 2)

    def flaky(model: str, msgs: list[dict[str, str]]) -> str:
        if msgs == WARMUP_MESSAGES:
            return "OK"
        raise LLMError("model down")

    Runner(FakeLLMClient(flaky), results_dir=tmp_path).run_site(site, eval_set, "cand")
    judge_client = FakeLLMClient(responder_with(5))
    _, after = rescore_site(
        site, eval_set, "cand", results_dir=tmp_path, judge=Judge(judge_client, "new-j")
    )
    assert (after.new, after.errors) == (0, 2)
    assert judge_client.calls == []


def test_rescore_ignores_non_judge_sites(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["classify_category"]
    eval_set = small(site, 2)
    Runner(FakeLLMClient("billing"), results_dir=tmp_path).run_site(site, eval_set, "cand")
    judge_client = FakeLLMClient(responder_with(5))
    before, after = rescore_site(
        site, eval_set, "cand", results_dir=tmp_path, judge=Judge(judge_client, "new-j")
    )
    assert before == after
    assert judge_client.calls == []


def test_rescore_without_results(tmp_path: Path, sites: dict[str, CallSite]) -> None:
    site = sites["draft_reply"]
    _, after = rescore_site(
        site,
        small(site, 2),
        "cand",
        results_dir=tmp_path,
        judge=Judge(FakeLLMClient("x"), "j"),
    )
    assert (after.scored, after.new) == (0, 0)
    assert not results_path(tmp_path, site.id, "cand").exists()
