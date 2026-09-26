import json
from pathlib import Path
from typing import Any

import pytest

from downshift.config import resolve_config
from downshift.export import (
    AUDIT_FILE,
    CALLSITES_FILE,
    DISCLAIMER,
    EVALS_FILE,
    EXPORT_FILES,
    REPORT_FILE,
    SUMMARY_FILE,
    audit_payload,
    build_export,
    write_export,
)
from downshift.report import Report, build_report, render_markdown
from downshift.schema import ScanResult

ROOT = Path(__file__).resolve().parents[2]
SD = ROOT / "examples" / "supportdesk"
MODELS = ["qwen2.5:7b", "qwen2.5:3b", "qwen2.5:1.5b", "qwen2.5:0.5b"]


def _fn(site_id: str) -> str:
    return site_id.split("::")[-1]


@pytest.fixture(scope="module")
def data() -> dict[str, Any]:
    audit = ScanResult.load(SD / "downshift.audit.json")
    ast = ScanResult.load(SD / "downshift.scan.json")
    after = ScanResult.load(SD / "downshift.scan.after.json")
    config = resolve_config(None, SD)
    report = build_report(audit, config, SD / "evals", SD / "results")
    payloads = build_export(
        report,
        config,
        audit=audit,
        ast=ast,
        ast_after=after,
        evals_dir=SD / "evals",
        results_dir=SD / "results",
        project="supportdesk",
    )
    return {"audit": audit, "config": config, "report": report, "payloads": payloads}


def test_payload_files(data: dict[str, Any]) -> None:
    assert set(data["payloads"]) == {SUMMARY_FILE, CALLSITES_FILE, AUDIT_FILE, EVALS_FILE}
    assert set(EXPORT_FILES) == set(data["payloads"]) | {REPORT_FILE}


def test_payloads_are_json(data: dict[str, Any]) -> None:
    for payload in data["payloads"].values():
        json.dumps(payload)


def test_summary_matches_report(data: dict[str, Any]) -> None:
    s = data["payloads"][SUMMARY_FILE]
    assert s["project"] == "supportdesk"
    assert s["baseline"] == "qwen2.5:7b"
    assert s["candidates"] == ["qwen2.5:3b", "qwen2.5:1.5b", "qwen2.5:0.5b"]
    assert s["judge_models"] == ["openai/gpt-oss-120b"]
    assert s["sites_total"] == 8
    assert s["sites_downgraded"] == 3
    assert s["cost"]["before_monthly"] == pytest.approx(3137.26, abs=0.01)
    assert s["cost"]["after_monthly"] == pytest.approx(2572.61, abs=0.01)
    assert s["cost"]["savings"] == pytest.approx(564.65, abs=0.01)
    assert s["cost"]["savings_pct"] == pytest.approx(0.18, abs=0.001)
    assert s["disclaimer"] == DISCLAIMER
    assert [p["model"] for p in s["pricing"]] == MODELS


def test_summary_downgrades(data: dict[str, Any]) -> None:
    got = {_fn(d["site_id"]): d["to"] for d in data["payloads"][SUMMARY_FILE]["downgrades"]}
    assert got == {
        "extract_order_info": "qwen2.5:3b",
        "detect_sentiment": "qwen2.5:3b",
        "lang_of": "qwen2.5:1.5b",
    }


def test_summary_quality(data: dict[str, Any]) -> None:
    q = data["payloads"][SUMMARY_FILE]["quality"]
    assert q["baseline_pass_rate"] is not None
    assert q["after_pass_rate"] is not None
    assert q["delta"] == pytest.approx(q["after_pass_rate"] - q["baseline_pass_rate"], abs=1e-3)


def test_callsites(data: dict[str, Any]) -> None:
    sites = data["payloads"][CALLSITES_FILE]
    assert len(sites) == 8
    by_fn = {_fn(s["id"]): s for s in sites}
    for site in sites:
        assert [m["model"] for m in site["models"]] == MODELS
        assert sum(m["chosen"] for m in site["models"]) == 1
        assert site["eval_cases"] >= 20
        assert site["cost"] is not None
        assert site["found_by"] in {"ast", "bob"}

    lang = by_fn["lang_of"]
    assert lang["decision"]["action"] == "downgrade"
    assert lang["decision"]["model"] == "qwen2.5:1.5b"
    small = next(m for m in lang["models"] if m["model"] == "qwen2.5:1.5b")
    assert (small["passed"], small["cases"]) == (20, 22)
    assert small["chosen"] and small["check"] is not None

    refund = by_fn["decide_refund"]
    assert refund["decision"]["action"] == "keep"
    base = next(m for m in refund["models"] if m["is_baseline"])
    assert base["check"] is None
    assert base["cost_per_call"] is not None


def test_audit(data: dict[str, Any]) -> None:
    a = data["payloads"][AUDIT_FILE]
    assert a["ast"]["call_sites"] == 7
    assert a["ast"]["models_resolved"] == 6
    assert a["audit"]["call_sites"] == 8
    assert a["audit"]["models_resolved"] == 8
    assert a["ast_after"]["models_resolved"] == 0
    assert len(a["ast_sites"]) == 7
    assert len(a["audit_sites"]) == 8
    assert "call_sites" in a["labels"]


def test_audit_without_ast(data: dict[str, Any]) -> None:
    a = audit_payload(data["audit"])
    assert a["ast"] is None
    assert a["ast_after"] is None
    assert a["changes"] == []
    assert a["ast_sites"] == []


def test_evals(data: dict[str, Any]) -> None:
    evals = data["payloads"][EVALS_FILE]
    assert len(evals) == 8
    assert sum(e["cases"] for e in evals) == 181
    for e in evals:
        assert e["models"] == MODELS
        assert len(e["examples"]) == 3
        assert len(e["grid"]) == e["cases"]
        for ex in e["examples"]:
            assert set(ex["outputs"]) == set(MODELS)
            assert all(o is not None for o in ex["outputs"].values())
            assert ex["inputs"]


def test_examples_zero_and_negative(data: dict[str, Any]) -> None:
    kwargs: dict[str, Any] = {
        "audit": data["audit"],
        "evals_dir": SD / "evals",
        "results_dir": SD / "results",
    }
    none = build_export(data["report"], data["config"], examples=0, **kwargs)
    assert all(e["examples"] == [] for e in none[EVALS_FILE])
    with pytest.raises(ValueError):
        build_export(data["report"], data["config"], examples=-1, **kwargs)


def test_missing_results_and_evals(data: dict[str, Any], tmp_path: Path) -> None:
    report: Report = data["report"]
    no_results = build_export(
        report,
        data["config"],
        audit=data["audit"],
        evals_dir=SD / "evals",
        results_dir=tmp_path,
    )
    assert no_results[SUMMARY_FILE]["judge_models"] == []
    grid = no_results[EVALS_FILE][0]["grid"][0]["passed"]
    assert set(grid.values()) == {None}

    no_evals = build_export(
        report,
        data["config"],
        audit=data["audit"],
        evals_dir=tmp_path,
        results_dir=SD / "results",
    )
    assert no_evals[EVALS_FILE] == []
    assert all(s["eval_cases"] == 0 for s in no_evals[CALLSITES_FILE])


def test_deterministic(data: dict[str, Any]) -> None:
    again = build_export(
        data["report"],
        data["config"],
        audit=data["audit"],
        ast=ScanResult.load(SD / "downshift.scan.json"),
        ast_after=ScanResult.load(SD / "downshift.scan.after.json"),
        evals_dir=SD / "evals",
        results_dir=SD / "results",
        project="supportdesk",
    )
    assert json.dumps(again) == json.dumps(data["payloads"])


def test_write_export(data: dict[str, Any], tmp_path: Path) -> None:
    md = render_markdown(data["report"])
    out = tmp_path / "web" / "data"
    written = write_export(out, data["payloads"], md)
    assert sorted(p.name for p in written) == sorted(EXPORT_FILES)
    summary = json.loads((out / SUMMARY_FILE).read_text(encoding="utf-8"))
    assert summary == data["payloads"][SUMMARY_FILE]
    assert (out / REPORT_FILE).read_text(encoding="utf-8") == md
    committed = (SD / "downshift.report.md").read_text(encoding="utf-8")
    assert md == committed
