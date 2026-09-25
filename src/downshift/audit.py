"""Validate Bob audit files and compare them with the ast scan.

The Bob auditor writes downshift.audit.json in the same format as the scan
(see schema.py). `validate_file` checks one file and lints it for work Bob
left unfinished. `compare_scans` puts the ast scan and the audit side by
side so the gaps Bob closed are visible. The CLI commands `validate` and
`compare` are thin wrappers around these functions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from downshift.evals import expression_placeholders
from downshift.schema import CallSite, ScanResult, SchemaError

ENRICHMENT_FIELDS = ("purpose", "output_contract", "difficulty", "grading")

METRIC_LABELS = {
    "call_sites": "Call sites",
    "models_resolved": "Models resolved",
    "prompts_resolved": "Prompts resolved",
    "enriched": "Enriched",
    "found_by_bob": "Found by Bob",
    "via_helper": "Split from helpers",
}


# --- validate -----------------------------------------------------------------


@dataclass
class ValidationReport:
    path: Path
    result: ScanResult | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None


def is_enriched(site: CallSite) -> bool:
    return all(getattr(site, name) is not None for name in ENRICHMENT_FIELDS)


def validate_file(path: Path) -> ValidationReport:
    """Load a callsites or audit file; schema problems become `error`, lint becomes `warnings`."""
    report = ValidationReport(path=path)
    try:
        report.result = ScanResult.load(path)
    except SchemaError as exc:
        report.error = str(exc)
        return report
    report.warnings = lint(report.result)
    return report


def lint(result: ScanResult) -> list[str]:
    """Problems that pass the schema but mean the audit is not finished."""
    warnings: list[str] = []
    ids = {site.id for site in result.call_sites}
    from_bob = result.generated_by == "bob"

    for site in result.call_sites:
        if site.grading == "json_fields" and site.output_format != "json":
            warnings.append(
                f"{site.id}: grading is json_fields but output_format is {site.output_format}"
            )
        if site.via is not None and site.via in ids:
            warnings.append(f"{site.id}: via {site.via} is still listed as its own call site")
        if site.found_by == "bob" and not any(note.startswith("Bob:") for note in site.notes):
            warnings.append(f"{site.id}: found_by is bob but there is no 'Bob:' note")
        if from_bob:
            missing = [name for name in ENRICHMENT_FIELDS if getattr(site, name) is None]
            if missing:
                warnings.append(f"{site.id}: missing {', '.join(missing)}")
            if not site.model.resolved:
                warnings.append(f"{site.id}: model still unresolved")
            if not site.prompt_resolved:
                warnings.append(f"{site.id}: prompt still unresolved")
            for expression in expression_placeholders(site):
                warnings.append(
                    f"{site.id}: placeholder {{{expression}}} is an expression; "
                    "use a plain name so eval inputs can fill it"
                )

    if from_bob and not any(site.found_by == "bob" for site in result.call_sites):
        warnings.append("generated_by is bob but no call site has found_by bob")
    return warnings


# --- compare ------------------------------------------------------------------


@dataclass(frozen=True)
class Metric:
    name: str
    ast: int
    audit: int


@dataclass(frozen=True)
class SiteChange:
    id: str
    kind: str  # split | removed | added | resolved | changed | enriched | unchanged
    detail: str


@dataclass
class Comparison:
    metrics: list[Metric]
    changes: list[SiteChange]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": [asdict(metric) for metric in self.metrics],
            "changes": [asdict(change) for change in self.changes],
        }


def metrics_for(result: ScanResult) -> dict[str, int]:
    summary = result.summary()
    sites = result.call_sites
    return {
        "call_sites": summary["call_sites"],
        "models_resolved": summary["models_resolved"],
        "prompts_resolved": summary["prompts_resolved"],
        "enriched": sum(1 for site in sites if is_enriched(site)),
        "found_by_bob": sum(1 for site in sites if site.found_by == "bob"),
        "via_helper": sum(1 for site in sites if site.via is not None),
    }


def compare_scans(ast: ScanResult, audit: ScanResult) -> Comparison:
    """Side-by-side metrics plus one change row per call site id."""
    before_metrics = metrics_for(ast)
    after_metrics = metrics_for(audit)
    metrics = [
        Metric(label, before_metrics[key], after_metrics[key])
        for key, label in METRIC_LABELS.items()
    ]

    before_sites = {site.id: site for site in ast.call_sites}
    after_sites = {site.id: site for site in audit.call_sites}
    changes: list[SiteChange] = []

    for site_id in before_sites:
        if site_id in after_sites:
            continue
        children = sorted(site.id for site in audit.call_sites if site.via == site_id)
        if children:
            changes.append(SiteChange(site_id, "split", "into " + ", ".join(children)))
        else:
            changes.append(SiteChange(site_id, "removed", "not in the audit"))

    for site_id, after in after_sites.items():
        changes.append(_change(site_id, before_sites.get(site_id), after))

    changes.sort(key=lambda change: change.id)
    return Comparison(metrics=metrics, changes=changes)


def _change(site_id: str, before: CallSite | None, after: CallSite) -> SiteChange:
    if before is None:
        detail = f"via {after.via}" if after.via else "not found by the scanner"
        return SiteChange(site_id, "added", detail)

    parts: list[str] = []
    filled_gap = False
    if after.model.value != before.model.value:
        if before.model.resolved:
            parts.append(f"model {before.model.value} -> {after.model.value}")
        else:
            parts.append(f"model resolved: {after.model.value}")
            filled_gap = True
    if after.prompt_resolved and not before.prompt_resolved:
        parts.append("prompt resolved")
        filled_gap = True
    if parts:
        return SiteChange(site_id, "resolved" if filled_gap else "changed", "; ".join(parts))

    if is_enriched(after) and not is_enriched(before):
        return SiteChange(site_id, "enriched", ", ".join(ENRICHMENT_FIELDS))
    return SiteChange(site_id, "unchanged", "")
