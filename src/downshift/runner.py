"""Run eval sets against models and store scored results.

For each call site and model, the runner renders the site's prompt with every
eval case, calls the model with the site's own settings, scores the output and
appends one JSON line per case to results/<slug>/<model>.jsonl.

Runs are resumable: cases that already have a scored row are skipped, and rows
that failed (model or judge error) are retried. The last row for a case wins.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any

from downshift.evals import EvalCase, EvalSet, graded_fields, render_messages, slug_for
from downshift.llm import LLMClient, LLMError
from downshift.schema import CallSite
from downshift.scorer import Judge, score_case

RESULTS_SUFFIX = ".jsonl"
WARMUP_MESSAGES: list[dict[str, str]] = [{"role": "user", "content": "Reply with the word OK."}]


def model_filename(model: str) -> str:
    """Filesystem-safe model name: `qwen2.5:7b` -> `qwen2.5-7b`."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", model).strip("-") or "model"


def results_path(results_dir: Path, site_id: str, model: str) -> Path:
    return results_dir / slug_for(site_id) / f"{model_filename(model)}{RESULTS_SUFFIX}"


@dataclass(frozen=True)
class ResultRow:
    """One eval case run on one model."""

    case_id: str
    model: str
    output: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    score: float | None = None
    passed: bool | None = None
    detail: str = ""
    judge_score: int | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        """Scored without errors."""
        return self.error is None and self.score is not None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["latency_s"] = round(self.latency_s, 3)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ResultRow:
        known = {f.name for f in dataclass_fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


def load_results(path: Path) -> dict[str, ResultRow]:
    """Rows by case id. Unreadable lines are skipped; the last row for a case wins."""
    rows: dict[str, ResultRow] = {}
    if not path.is_file():
        return rows
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            row = ResultRow.from_dict(json.loads(raw))
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue
        rows[row.case_id] = row
    return rows


def append_row(path: Path, row: ResultRow) -> None:
    """Append one row, starting a new line if a previous write was cut off."""
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = ""
    if path.is_file() and path.stat().st_size:
        with path.open("rb") as fh:
            fh.seek(-1, os.SEEK_END)
            if fh.read(1) != b"\n":
                prefix = "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(prefix + json.dumps(row.to_dict(), ensure_ascii=False) + "\n")


@dataclass(frozen=True)
class RunSummary:
    """Totals for one call site on one model, over the cases in scope."""

    site_id: str
    model: str
    cases: int
    scored: int
    passed: int
    errors: int
    new: int
    mean_score: float | None
    avg_latency_s: float | None
    avg_prompt_tokens: float | None
    avg_completion_tokens: float | None

    @property
    def pass_rate(self) -> float | None:
        return self.passed / self.scored if self.scored else None


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize_rows(
    site_id: str,
    model: str,
    case_ids: Sequence[str],
    rows: Mapping[str, ResultRow],
    new: int = 0,
) -> RunSummary:
    """Summarize the rows for these case ids (rows for other cases are ignored)."""
    selected = [rows[c] for c in case_ids if c in rows]
    ok = [r for r in selected if r.ok]
    return RunSummary(
        site_id=site_id,
        model=model,
        cases=len(case_ids),
        scored=len(ok),
        passed=sum(1 for r in ok if r.passed),
        errors=sum(1 for r in selected if r.error is not None),
        new=new,
        mean_score=_mean([r.score or 0.0 for r in ok]),
        avg_latency_s=_mean([r.latency_s for r in ok]),
        avg_prompt_tokens=_mean([float(r.prompt_tokens) for r in ok]),
        avg_completion_tokens=_mean([float(r.completion_tokens) for r in ok]),
    )


class Runner:
    """Runs eval sets on models and appends scored rows to results files."""

    def __init__(
        self,
        client: LLMClient,
        *,
        results_dir: Path,
        judge: Judge | None = None,
        limit: int | None = None,
        warmup: bool = True,
        on_case: Callable[[ResultRow], None] | None = None,
    ) -> None:
        self.client = client
        self.results_dir = results_dir
        self.judge = judge
        self.limit = limit
        self.warmup = warmup
        self.on_case = on_case
        self._warmed: set[str] = set()

    def warm_up(self, model: str) -> None:
        """One untimed call so model load time does not count as latency.

        LLMError propagates: a model that cannot answer this cannot run evals.
        """
        if not self.warmup or model in self._warmed:
            return
        self.client.complete(model, WARMUP_MESSAGES, temperature=0.0, max_tokens=5)
        self._warmed.add(model)

    def cases_for(self, eval_set: EvalSet) -> list[EvalCase]:
        return eval_set.cases[: self.limit] if self.limit else list(eval_set.cases)

    def run_site(self, site: CallSite, eval_set: EvalSet, model: str) -> RunSummary:
        cases = self.cases_for(eval_set)
        path = results_path(self.results_dir, site.id, model)
        rows = load_results(path)
        todo = [c for c in cases if not (c.id in rows and rows[c.id].ok)]
        if todo:
            self.warm_up(model)
            if self.judge is not None and any(c.grading == "judge" for c in todo):
                self.warm_up(self.judge.model)
        fields = graded_fields(site)
        for case in todo:
            row = self._run_case(site, eval_set, case, model, fields)
            append_row(path, row)
            rows[case.id] = row
            if self.on_case is not None:
                self.on_case(row)
        return summarize_rows(site.id, model, [c.id for c in cases], rows, new=len(todo))

    def _run_case(
        self,
        site: CallSite,
        eval_set: EvalSet,
        case: EvalCase,
        model: str,
        fields: list[str] | None,
    ) -> ResultRow:
        messages = render_messages(site, eval_set.inputs_for(case))
        temperature = float(site.temperature) if site.temperature is not None else 0.0
        try:
            completion = self.client.complete(
                model,
                messages,
                temperature=temperature,
                max_tokens=site.max_tokens,
                json_mode=site.output_format == "json",
            )
        except LLMError as exc:
            return ResultRow(case.id, model, error=str(exc))
        row = ResultRow(
            case.id,
            model,
            output=completion.text,
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
            latency_s=completion.latency_s,
        )
        try:
            score = score_case(
                case.grading,
                case.expected,
                completion.text,
                fields=fields,
                prompt_messages=messages,
                judge=self.judge,
            )
        except (LLMError, ValueError) as exc:
            return replace(row, error=f"scoring failed: {exc}")
        return replace(
            row,
            score=score.value,
            passed=score.passed,
            detail=score.detail,
            judge_score=score.judge_score,
        )
