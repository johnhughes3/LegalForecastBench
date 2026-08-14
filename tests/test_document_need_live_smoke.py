"""Optional live Haiku smoke for document-need pass 1. Default suite skips this.

Authorized by legalforecastbench-dn9.1: up to five already-downloaded cases,
zero PACER, model claude-haiku-4-5-20251001, behind LFB_LIVE_SMOKE=1.
Credentials must come from the sanctioned Infisical path; if the key is
absent, skip — never fall back to unsanctioned host credentials beyond the
wrapper-populated environment.
"""

from __future__ import annotations

import json
import os

import pytest
from legalforecast.document_need.cycle_config import (
    document_need_view_from_cycle_config,
)
from legalforecast.document_need.protocol import (
    PASS1_SCHEMA,
    build_pass1_prompt,
)
from legalforecast.document_need.selector import (
    CLEARED_LIVE_MODEL,
    live_smoke_enabled,
)
from legalforecast.document_need.types import (
    BlindBundle,
    Chronology,
    ChronologyEntry,
    DocketDocument,
)
from tests.document_need_fixtures import activated_haiku_config

pytestmark = pytest.mark.skipif(
    not live_smoke_enabled(),
    reason="set LFB_LIVE_SMOKE=1 to run the document-need Haiku smoke",
)

_ANTHROPIC = "ANTHROPIC_API_KEY"


def test_live_haiku_classifies_synthetic_chronology() -> None:
    if not os.environ.get(_ANTHROPIC, "").strip():
        pytest.skip(
            "ANTHROPIC_API_KEY missing after Infisical wrapper; skip live smoke"
        )
    from legalforecast.document_need.selector import verdict_from_pass1_output
    from legalforecast.evals.live_model_solver import complete_live_prompt
    from legalforecast.evals.model_registry import ModelRegistryEntry, ToolPolicy
    from legalforecast.selection.eligibility import TrainingCutoffStatus

    chronology = Chronology(
        candidate_id="smoke-1",
        case_name="Smoke v. Fixture",
        court="nysd",
        docket_number="1:26-cv-smoke",
        target_motion_entries=(10,),
        decision_cut_entry=20,
        entries=(
            ChronologyEntry(
                entry=1,
                filed="2026-01-02",
                text="Complaint filed.",
                documents=(
                    DocketDocument(
                        selector="main_document",
                        description="Complaint (5 pages)",
                        freely_available=True,
                        pacer_only=False,
                        page_count=5,
                    ),
                ),
            ),
            ChronologyEntry(
                entry=10,
                filed="2026-03-01",
                text="Defendant's motion to dismiss.",
                documents=(
                    DocketDocument(
                        selector="main_document",
                        description="Motion to Dismiss (20 pages)",
                        freely_available=False,
                        pacer_only=True,
                        page_count=20,
                    ),
                ),
            ),
        ),
    )
    prompt = build_pass1_prompt(
        BlindBundle(
            chronology=chronology,
            motion_markdown={10: "Defendant moves to dismiss the complaint."},
        ),
        bucket_definitions=document_need_view_from_cycle_config(
            activated_haiku_config()
        ).document_need_buckets,
    )
    schema_hint = (
        prompt
        + "\nRespond with JSON only: "
        + json.dumps(
            {
                "schema": PASS1_SCHEMA,
                "candidate_id": "smoke-1",
                "entries": [
                    {
                        "entry": 1,
                        "bucket": "clearly_required",
                        "asserted_role": "complaint",
                        "rationale": "why",
                    }
                ],
            }
        )
        + " covering every entry."
    )
    entry = ModelRegistryEntry(
        provider="anthropic",
        model_id=CLEARED_LIVE_MODEL,
        display_name="Claude Haiku 4.5",
        model_version_or_snapshot=CLEARED_LIVE_MODEL,
        provider_training_cutoff_status=TrainingCutoffStatus.UNKNOWN,
        temperature=0.0,
        top_p=1.0,
        max_output_tokens=2048,
        network_disabled=True,
        search_disabled=True,
        tool_policy=ToolPolicy.NO_TOOLS,
        context_limit=200000,
        pricing_source=(
            "https://www.anthropic.com/pricing, Haiku 4.5, checked 2026-08-13"
        ),
        input_token_price=1.0,
        output_token_price=5.0,
    )
    response = complete_live_prompt(entry, schema_hint)
    verdict = verdict_from_pass1_output(
        response.raw_output, model_id=CLEARED_LIVE_MODEL
    )
    assert verdict.candidate_id == "smoke-1"
    assert {row.entry for row in verdict.entries} == {1, 10}
    assert response.estimated_cost >= 0
