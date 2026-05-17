"""Post-feasibility pilot readiness reporting."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, cast

DOCKET_ENTRY_LISTING_UNAVAILABLE: Final = "docket_entry_listing_unavailable"


@dataclass(frozen=True, slots=True)
class CaseDevSmokeReadinessMetrics:
    """Metrics parsed from the Phase 0 case.dev smoke report."""

    generated_at: str | None
    total_hit_count: int
    unique_candidate_count: int
    retrieved_candidate_count: int
    clean_mtd_candidate_count: int
    retrieval_attempt_count: int
    docket_entry_listing_unavailable_count: int
    request_count: int
    estimated_cost: str


@dataclass(frozen=True, slots=True)
class FixtureWorkflowReadiness:
    """No-network fixture workflow status used as a local path check."""

    status: str
    missing_artifacts: tuple[str, ...]
    validation_passed: bool | None
    artifact_count: int | None

    @property
    def display_status(self) -> str:
        if self.status == "passed":
            return "passed"
        if self.status == "not_supplied":
            return "not supplied"
        if self.missing_artifacts:
            return f"{self.status}; missing {', '.join(self.missing_artifacts)}"
        return self.status


@dataclass(frozen=True, slots=True)
class PilotReadinessReport:
    """Rendered post-feasibility pilot/readiness report inputs."""

    generated_at: datetime
    smoke_metrics: CaseDevSmokeReadinessMetrics
    fixture_workflow: FixtureWorkflowReadiness


def build_pilot_readiness_report(
    smoke_report_text: str,
    *,
    fixture_output_dir: Path | None = None,
    generated_at: datetime | None = None,
) -> PilotReadinessReport:
    """Build the readiness report from smoke and optional fixture artifacts."""

    return PilotReadinessReport(
        generated_at=generated_at or datetime.now(UTC),
        smoke_metrics=parse_case_dev_smoke_markdown(smoke_report_text),
        fixture_workflow=inspect_fixture_workflow(fixture_output_dir),
    )


def parse_case_dev_smoke_markdown(
    smoke_report_text: str,
) -> CaseDevSmokeReadinessMetrics:
    """Extract the live smoke metrics needed for the pilot gate."""

    unavailable_count = _parse_missing_reason_count(
        smoke_report_text,
        DOCKET_ENTRY_LISTING_UNAVAILABLE,
    )
    candidate_ledger_rows = len(
        re.findall(r"^\| case-dev-smoke-[^|]+\|", smoke_report_text, flags=re.MULTILINE)
    )
    retrieved_candidate_count = _parse_required_bullet_int(
        smoke_report_text,
        "Retrieved candidate cases",
    )
    return CaseDevSmokeReadinessMetrics(
        generated_at=_parse_optional_bullet_text(smoke_report_text, "Generated at"),
        total_hit_count=_parse_required_bullet_int(
            smoke_report_text,
            "Total hit count",
        ),
        unique_candidate_count=_parse_required_bullet_int(
            smoke_report_text,
            "Unique candidate cases",
        ),
        retrieved_candidate_count=retrieved_candidate_count,
        clean_mtd_candidate_count=_parse_required_bullet_int(
            smoke_report_text,
            "Clean MTD candidates",
        ),
        retrieval_attempt_count=max(
            retrieved_candidate_count,
            unavailable_count,
            candidate_ledger_rows,
        ),
        docket_entry_listing_unavailable_count=unavailable_count,
        request_count=_parse_optional_bullet_int(
            smoke_report_text,
            "case.dev request count",
        ),
        estimated_cost=(
            _parse_optional_bullet_text(smoke_report_text, "Estimated case.dev cost")
            or "not reported"
        ),
    )


def inspect_fixture_workflow(output_dir: Path | None) -> FixtureWorkflowReadiness:
    """Inspect a fixture E2E output directory without depending on live services."""

    if output_dir is None:
        return FixtureWorkflowReadiness(
            status="not_supplied",
            missing_artifacts=(),
            validation_passed=None,
            artifact_count=None,
        )
    required_paths = (
        Path("candidate-manifest.jsonl"),
        Path("packets.jsonl"),
        Path("runs.jsonl"),
        Path("scores.json"),
        Path("preregistration-validation.json"),
        Path("report/leaderboard.json"),
        Path("artifact-index.json"),
    )
    missing = tuple(
        str(path) for path in required_paths if not (output_dir / path).is_file()
    )
    validation_passed: bool | None = None
    artifact_count: int | None = None
    if (output_dir / "preregistration-validation.json").is_file():
        validation = _read_json_object(output_dir / "preregistration-validation.json")
        validation_passed_value = validation.get("passed")
        if isinstance(validation_passed_value, bool):
            validation_passed = validation_passed_value
    if (output_dir / "artifact-index.json").is_file():
        artifact_index = _read_json_object(output_dir / "artifact-index.json")
        artifact_count_value = artifact_index.get("artifact_count")
        if isinstance(artifact_count_value, int) and not isinstance(
            artifact_count_value,
            bool,
        ):
            artifact_count = artifact_count_value

    status = "passed"
    if missing:
        status = "missing"
    elif validation_passed is not True:
        status = "failed"
    return FixtureWorkflowReadiness(
        status=status,
        missing_artifacts=missing,
        validation_passed=validation_passed,
        artifact_count=artifact_count,
    )


def render_pilot_readiness_markdown(report: PilotReadinessReport) -> str:
    """Render an honest post-feasibility pilot report."""

    metrics = report.smoke_metrics
    fixture = report.fixture_workflow
    clean_yield = _percentage(
        metrics.clean_mtd_candidate_count,
        metrics.retrieval_attempt_count,
    )
    discovery_yield = _percentage(
        metrics.clean_mtd_candidate_count,
        metrics.unique_candidate_count,
    )
    generated_at = _iso_datetime(report.generated_at)
    smoke_generated_at = metrics.generated_at or "not reported"
    blocked_attempts = metrics.docket_entry_listing_unavailable_count

    return (
        "# Phase 0 Post-Feasibility Pilot Report\n\n"
        f"- Generated at: {generated_at}\n"
        f"- Source smoke report generated at: {smoke_generated_at}\n\n"
        "## Bottom Line\n\n"
        "The planned 50-100 clean-case pilot should not proceed as a "
        "case.dev-only run in the current API state. The live case.dev search "
        "path is usable for MTD candidate discovery, but docket-entry listing "
        f"still returns `{DOCKET_ENTRY_LISTING_UNAVAILABLE}`. That failure "
        "blocks clean-packet construction before linkage, extraction, "
        "unitization, labeling, model execution, or lawyer review can be "
        "meaningfully measured on live cases.\n\n"
        "Coordinator update for this gate: a new all-permissions "
        "`CASE_DEV_API_KEY` works for live smoke. The remaining blocker should "
        "therefore be treated as a case.dev docket-entry/source-document "
        "availability problem, not a key-permission problem and not a required "
        "CourtListener dependency.\n\n"
        "The next live pilot should be a case.dev retrieval/export pilot:\n\n"
        "```text\n"
        "case.dev discovery -> case.dev docket-entry and source-document "
        "retrieval or case.dev-supported export -> normal "
        "LegalForecast packet workflow\n"
        "```\n\n"
        "## Evidence Used\n\n"
        "This report relies on the current Phase 0 smoke artifacts and the "
        "no-network fixture workflow:\n\n"
        "- the current case.dev smoke report;\n"
        "- the acquisition policy in `docs/acquisition.md`;\n"
        "- `legalforecast fixture e2e`, which validates the local artifact "
        "path once clean packets exist.\n\n"
        "No live 50-100 clean-case run was completed for this bead because the "
        "first live retrieval blocker is still docket-entry listing "
        "availability.\n\n"
        "Regenerate this report with:\n\n"
        "```bash\n"
        "legalforecast pilot readiness --smoke-report "
        "tmp/case-dev-smoke.md --fixture-output-dir "
        "<fixture-e2e-output-dir> --output "
        "tmp/pilot-readiness.md\n"
        "```\n\n"
        "## Pilot Status\n\n"
        "| Field | Result |\n"
        "| --- | --- |\n"
        "| Intended pilot size | 50-100 clean MTD packets |\n"
        f"| Live clean packets produced | {metrics.clean_mtd_candidate_count} |\n"
        f"| Live search hits in current smoke artifact | {metrics.total_hit_count} |\n"
        "| Unique candidate cases in current smoke artifact | "
        f"{metrics.unique_candidate_count} |\n"
        "| Candidate retrieval attempts in current smoke artifact | "
        f"{metrics.retrieval_attempt_count} |\n"
        "| Retrieval attempts blocked by docket-entry listing | "
        f"{blocked_attempts} |\n"
        f"| Primary blocker | `{DOCKET_ENTRY_LISTING_UNAVAILABLE}` |\n"
        "| Key-permission diagnosis | Not the current blocker |\n"
        f"| Fixture E2E artifact path | {fixture.display_status} |\n"
        "| Recommended next run | case.dev discovery plus case.dev "
        "docket-entry/source-document retrieval or export |\n\n"
        "## Clean-Packet Yield\n\n"
        "| Metric | Count |\n"
        "| --- | ---: |\n"
        f"| Clean packets accepted | {metrics.clean_mtd_candidate_count} |\n"
        "| Partially reviewable packets | 0 |\n"
        f"| Excluded retrieval attempts | {metrics.retrieval_attempt_count} |\n"
        f"| Clean-packet yield from retrieval attempts | {clean_yield} |\n"
        "| Clean-packet yield from unique discovery candidates | "
        f"{discovery_yield} |\n\n"
        "This is a structural zero, not a merits zero. The search layer produced "
        "a candidate pool, but the API did not expose enough docket-entry data "
        "to determine whether those candidates had the complaint, target "
        "motion, briefing, and first written disposition required for a "
        "benchmark packet.\n\n"
        "## Exclusion Ledger Summary\n\n"
        "| Primary exclusion reason | Count | Notes |\n"
        "| --- | ---: | --- |\n"
        f"| `{DOCKET_ENTRY_LISTING_UNAVAILABLE}` | {blocked_attempts} | "
        "case.dev returned the provider feature-unavailable response for every "
        "retrieved candidate in the smoke artifact. |\n\n"
        "Representative candidate IDs are listed in the smoke report. They "
        "should remain examples of the retrieval blocker, not clean pilot "
        "examples for outcome-rule rows.\n\n"
        "## Case-Mix Distribution\n\n"
        "Retained-packet case mix is not reportable yet because there are no "
        "retained live packets. The only honest source-class distribution for "
        "this attempted pilot is:\n\n"
        "| Source class | Candidate count | Unit count | Interpretation |\n"
        "| --- | ---: | ---: | --- |\n"
        "| `case.dev-only` | 0 | 0 | No case.dev-only clean packets could be "
        "built. |\n"
        "| `case.dev-plus-fallback` | 0 | 0 | Fallback reconstruction has not yet "
        "been run live. |\n"
        f"| `excluded` | {metrics.retrieval_attempt_count} | 0 | Retrieval attempts "
        "blocked before packet construction. |\n\n"
        "Do not infer district, NOS, judge, document-completeness, or unit-count "
        "distributions from search hits alone. Those fields belong to retained "
        "or reviewed packets.\n\n"
        "## Labeling, Review, And Cost\n\n"
        "| Field | Result |\n"
        "| --- | --- |\n"
        "| Stage A units | Not created from live cases |\n"
        "| Stage B labels | Not created from live cases |\n"
        "| Label ambiguity rate | Not measurable |\n"
        "| Lawyer review minutes | Not measurable |\n"
        "| Model/harness cost | Not incurred for live cases |\n"
        f"| case.dev request count | {metrics.request_count} in the current smoke "
        "artifact |\n"
        f"| Estimated case.dev cost | {metrics.estimated_cost} |\n"
        "| Cost per clean packet | Undefined because clean packet count is zero |\n\n"
        "The completed fixture E2E command is still valuable: it proves the "
        "local manifest, freeze, preregistration, packet, mock-run, scoring, "
        "diagnostics, and leaderboard path works. It does not substitute for a "
        "live clean-packet pilot.\n\n"
        "## Failure Modes\n\n"
        "| Failure mode | Current status | Operational response |\n"
        "| --- | --- | --- |\n"
        "| case.dev search unavailable | Not observed | Search produced a usable "
        "candidate pool. |\n"
        "| API credentials insufficient | Not the current diagnosis | Coordinator "
        "reports the all-permissions key works for live smoke. |\n"
        "| Docket-entry listing unavailable | Observed and blocking | Block the "
        "official cycle until case.dev exposes docket-entry retrieval or a "
        "supported export path. |\n"
        "| Source documents unavailable | Not separately measurable | Requires "
        "case.dev docket entries, case.dev document retrieval, or a "
        "case.dev-supported export. |\n"
        "| Motion-to-order linkage ambiguous | Not measurable | Requires "
        "reconstructed docket history. |\n"
        "| Leakage controls untested live | Not measurable | Requires source "
        "documents and first written disposition. |\n"
        "| Clean-packet case-mix dominance | Not measurable | Requires retained "
        "packets. |\n\n"
        "## Recommended Protocol Revisions\n\n"
        "1. Keep case.dev as the primary discovery layer for now, not yet the "
        "complete packet source.\n"
        "2. Make the next pilot a case.dev retrieval/export pilot over the "
        "existing case.dev candidate ledger.\n"
        "3. For each candidate with "
        f"`{DOCKET_ENTRY_LISTING_UNAVAILABLE}`, request or use the case.dev "
        "docket-entry/source-document API or a case.dev-supported export path. "
        "Do not make CourtListener/RECAP a required dependency for v1 unless "
        "that fallback is explicitly enabled later.\n"
        "4. Classify every candidate as `case.dev-only`, "
        "`case.dev-plus-fallback`, or `excluded`; publish the source-class "
        "distribution.\n"
        "5. Keep case.dev request/export counts separate from any optional "
        "fallback request/cost counts.\n"
        "6. Do not replace outcome-rules appendix placeholders with "
        "search-only candidate IDs. Use only candidates that reach reviewed "
        "clean-packet or excluded-after-record-review status.\n"
        "7. Do not start an official evaluation until the case.dev retrieval "
        "pilot "
        "produces either 50 clean packets or a credible path to 50-100 clean "
        "packets.\n\n"
        "## Next Pilot Acceptance Criteria\n\n"
        "The case.dev retrieval/export pilot should produce:\n\n"
        "- a candidate ledger seeded by case.dev discovery;\n"
        "- a case.dev docket-entry/source-document retrieval or export ledger;\n"
        "- a clean-packet ledger and exclusion ledger;\n"
        "- case-mix diagnostics over retained packets;\n"
        "- document hashes and source provenance for every mounted document;\n"
        "- label ambiguity and lawyer-review-time measurements for reviewed "
        "packets;\n"
        "- case.dev request/export cost reports, plus optional fallback cost "
        "reports only if fallback is later enabled;\n"
        "- protocol revisions before official ingestion.\n\n"
        "If case.dev cannot provide the docket entries and source documents "
        "needed for clean packets, the official cycle should remain blocked "
        "unless the project explicitly chooses a public-record fallback path.\n"
    )


def _parse_required_bullet_int(markdown: str, label: str) -> int:
    value = _parse_optional_bullet_text(markdown, label)
    if value is None:
        raise ValueError(f"{label} is missing from smoke report")
    if not value.isdigit():
        raise ValueError(f"{label} must be an integer in smoke report")
    return int(value)


def _parse_optional_bullet_int(markdown: str, label: str) -> int:
    value = _parse_optional_bullet_text(markdown, label)
    if value is None:
        return 0
    if not value.isdigit():
        raise ValueError(f"{label} must be an integer in smoke report")
    return int(value)


def _parse_optional_bullet_text(markdown: str, label: str) -> str | None:
    match = re.search(
        rf"^- {re.escape(label)}:\s*(.+?)\s*$",
        markdown,
        flags=re.MULTILINE,
    )
    if match is None:
        return None
    return match.group(1).strip()


def _parse_missing_reason_count(markdown: str, reason: str) -> int:
    match = re.search(
        rf"^- {re.escape(reason)}:\s*([0-9]+)\s*$",
        markdown,
        flags=re.MULTILINE,
    )
    if match is None:
        return 0
    return int(match.group(1))


def _read_json_object(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return dict(cast(Mapping[str, Any], loaded))


def _percentage(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "undefined"
    percent = numerator / denominator * 100
    if percent.is_integer():
        return f"{int(percent)} percent"
    return f"{percent:.1f} percent"


def _iso_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
