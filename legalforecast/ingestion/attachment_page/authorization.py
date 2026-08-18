"""Owner authorization for one attachment-menu fetch plan.

The executor in this package refuses to spend without an authorization bound
to an exact plan digest. This module is the half that issues one, so the
enforcement never ships without a supported way to satisfy it.

Two properties matter more than the artifact shape. First, the confirmation an
owner types is derived from and displayed off the plan actually loaded here --
a string carried in from an earlier projection can bind a digest that has since
moved, which converts a fail-closed prompt into a spent authorization window
rather than a safe stop. Second, the prompt is TTY-only: a confirmation piped
in from a file or a chat transcript is not a person reading a number.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TextIO

from legalforecast._json_io import read_json_object
from legalforecast.contracts import (
    ARTIFACT_RAW_SHA256_V1,
    ATTACHMENT_PAGE_AUTHORIZATION_V1,
    CommitmentEncodingError,
)
from legalforecast.ingestion.attachment_page import _typed
from legalforecast.ingestion.attachment_page.artifact_io import (
    canonical_artifact_bytes,
    replace_artifact,
    write_new_artifact,
)
from legalforecast.ingestion.attachment_page.plan import (
    AttachmentPageFetchPlan,
    AttachmentPagePlanError,
)

AUTHORIZATION_SCHEMA_VERSION: Final = str(ATTACHMENT_PAGE_AUTHORIZATION_V1)
REVIEWER_ID: Final = "John Hughes"


class AttachmentPageAuthorizationError(ValueError):
    """Raised when an attachment-menu authorization is absent or unbound."""


@dataclass(frozen=True, slots=True)
class AttachmentPageAuthorization:
    """One owner decision bound to one exact plan digest."""

    plan_id: str
    plan_sha256: str
    menu_count: int
    total_ceiling_usd: str
    reviewer_id: str
    recorded_at_utc: str
    typed_confirmation: str

    def to_record(self) -> dict[str, object]:
        body = self.content_record()
        return {
            "schema_version": AUTHORIZATION_SCHEMA_VERSION,
            "authorization": body,
            "authorization_sha256": _digest(body),
        }

    def content_record(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "plan_sha256": self.plan_sha256,
            "menu_count": self.menu_count,
            "total_ceiling_usd": self.total_ceiling_usd,
            "reviewer_id": self.reviewer_id,
            "recorded_at_utc": self.recorded_at_utc,
            "typed_confirmation": self.typed_confirmation,
            "pacer_fee_acknowledged": True,
            "paid_activity_requested": True,
            "paid_activity_executed": False,
        }


def _digest(body: Mapping[str, object]) -> str:
    """Commit the authorization body under the blessed artifact profile."""

    try:
        commitment = ARTIFACT_RAW_SHA256_V1.commit(
            body, domain=ATTACHMENT_PAGE_AUTHORIZATION_V1
        )
    except CommitmentEncodingError as exc:
        raise AttachmentPageAuthorizationError(
            "authorization is not canonically serializable"
        ) from exc
    return str(commitment.digest)


def render_authorization_prompt(plan: AttachmentPageFetchPlan) -> str:
    """Render exactly what the owner sees before typing, from this plan."""

    lines = [
        "",
        "PACER attachment-menu fetch — charge-bearing, no documents purchased",
        "",
        f"  plan id       {plan.plan_id}",
        f"  plan digest   {plan.plan_sha256}",
        f"  menus         {len(plan.targets)}",
        f"  per menu      USD {plan.per_menu_ceiling_usd} (PACER bills menus per page)",
        f"  total ceiling USD {plan.total_ceiling_usd}",
        "",
        "Each fetch asks PACER for one attachment menu and asks CourtListener to",
        "parse it. No attachment document is purchased by this step.",
        "",
    ]
    for target in plan.targets:
        description = target.entry_description.strip().replace("\n", " ")
        if len(description) > 90:
            description = description[:87] + "..."
        lines.append(
            f"  {target.candidate_id} entry {target.docket_entry_number} "
            f"(main document {target.main_source_document_id})"
            + (f" — {description}" if description else "")
        )
    if plan.skipped:
        lines.append("")
        lines.append("  Excluded, no charge:")
        for skip in plan.skipped:
            lines.append(
                f"    {skip.candidate_id} entry {skip.docket_entry_number} "
                f"— {skip.reason}: {skip.detail}"
            )
    lines.extend(
        [
            "",
            "To authorize, type this line exactly:",
            "",
            f"  {plan.required_confirmation()}",
            "",
            "Anything else cancels without spending.",
            "",
        ]
    )
    return "\n".join(lines)


def record_attachment_page_authorization(
    *,
    plan: AttachmentPageFetchPlan,
    typed_confirmation: str,
    reviewer_id: str,
    recorded_at_utc: str,
) -> AttachmentPageAuthorization:
    """Bind one typed confirmation to this plan, or refuse.

    ``typed_confirmation`` is compared against the string this plan derives, so
    a confirmation minted from any other plan -- including an earlier revision
    of this one -- cannot authorize a fetch.
    """

    if reviewer_id != REVIEWER_ID:
        raise AttachmentPageAuthorizationError(
            f"attachment-menu reviewer must be {REVIEWER_ID}"
        )
    if not plan.plan_sha256:
        raise AttachmentPagePlanError("plan digest is required before authorization")
    if typed_confirmation != plan.required_confirmation():
        raise AttachmentPageAuthorizationError(
            "typed confirmation does not match this exact plan"
        )
    if not recorded_at_utc.endswith("Z") or "T" not in recorded_at_utc:
        raise AttachmentPageAuthorizationError(
            "recorded_at_utc must be a UTC timestamp ending in Z"
        )
    return AttachmentPageAuthorization(
        plan_id=plan.plan_id,
        plan_sha256=plan.plan_sha256,
        menu_count=len(plan.targets),
        total_ceiling_usd=plan.total_ceiling_usd,
        reviewer_id=reviewer_id,
        recorded_at_utc=recorded_at_utc,
        typed_confirmation=typed_confirmation,
    )


def prompt_for_attachment_page_authorization(
    *,
    plan: AttachmentPageFetchPlan,
    recorded_at_utc: str,
    stdin: TextIO,
    stdout: TextIO,
    reviewer_id: str = REVIEWER_ID,
) -> AttachmentPageAuthorization:
    """Display this plan and read one typed confirmation from a real TTY."""

    if not hasattr(stdin, "isatty") or not stdin.isatty():
        raise AttachmentPageAuthorizationError(
            "attachment-menu authorization requires an interactive terminal; "
            "a piped or file-supplied confirmation is not owner authorization"
        )
    stdout.write(render_authorization_prompt(plan))
    stdout.flush()
    typed = stdin.readline().strip()
    return record_attachment_page_authorization(
        plan=plan,
        typed_confirmation=typed,
        reviewer_id=reviewer_id,
        recorded_at_utc=recorded_at_utc,
    )


def load_attachment_page_authorization(record: object) -> AttachmentPageAuthorization:
    """Rebuild an authorization from its artifact and re-verify its digest."""

    error = AttachmentPageAuthorizationError
    envelope = _typed.mapping(record, "authorization artifact", error=error)
    if envelope.get("schema_version") != AUTHORIZATION_SCHEMA_VERSION:
        raise error("unexpected authorization schema version")
    body = _typed.mapping(
        envelope.get("authorization"), "authorization content", error=error
    )
    if envelope.get("authorization_sha256") != _digest(body):
        raise error("authorization digest does not verify")
    if body.get("paid_activity_executed") is not False:
        raise error("authorization already records executed paid activity")
    return AttachmentPageAuthorization(
        plan_id=_typed.text(body.get("plan_id"), "plan id", error=error),
        plan_sha256=_typed.text(body.get("plan_sha256"), "plan digest", error=error),
        menu_count=_typed.integer(body.get("menu_count"), "menu count", error=error),
        total_ceiling_usd=_typed.text(
            body.get("total_ceiling_usd"), "total ceiling", error=error
        ),
        reviewer_id=_typed.text(body.get("reviewer_id"), "reviewer id", error=error),
        recorded_at_utc=_typed.text(
            body.get("recorded_at_utc"), "recorded_at_utc", error=error
        ),
        typed_confirmation=_typed.text(
            body.get("typed_confirmation"), "typed confirmation", error=error
        ),
    )


def verify_authorization_binds_plan(
    *,
    authorization: AttachmentPageAuthorization,
    plan: AttachmentPageFetchPlan,
) -> None:
    """Refuse any authorization that does not bind this exact plan."""

    if authorization.plan_sha256 != plan.plan_sha256:
        raise AttachmentPageAuthorizationError(
            "authorization is bound to a different attachment-menu plan digest"
        )
    if authorization.plan_id != plan.plan_id:
        raise AttachmentPageAuthorizationError(
            "authorization is bound to a different attachment-menu plan id"
        )
    if authorization.menu_count != len(plan.targets):
        raise AttachmentPageAuthorizationError(
            "authorization menu count does not match the plan"
        )
    if authorization.reviewer_id != REVIEWER_ID:
        raise AttachmentPageAuthorizationError(
            f"attachment-menu reviewer must be {REVIEWER_ID}"
        )
    if authorization.typed_confirmation != plan.required_confirmation():
        raise AttachmentPageAuthorizationError(
            "recorded confirmation does not match this plan's required confirmation"
        )


def write_authorization(path: Path, authorization: AttachmentPageAuthorization) -> None:
    """Write one authorization artifact without clobbering an existing one."""

    if path.exists():
        raise AttachmentPageAuthorizationError(
            "an attachment-menu authorization already exists at this path"
        )
    write_new_artifact(
        path, authorization.to_record(), error=AttachmentPageAuthorizationError
    )


def mark_authorization_executed(path: Path) -> None:
    """Consume this authorization by recording that paid activity executed.

    ``load_attachment_page_authorization`` already refuses an artifact whose
    ``paid_activity_executed`` is anything but ``False``; until now nothing
    wrote it, so the gate had no key and one signed file authorized unlimited
    re-runs. This is the writer.

    It must be called *before* the first charge-bearing POST, never after. A
    crash between this write and the dispatch leaves the authorization spent
    for a charge that may never have gone out, which costs one fresh owner
    signature; the reverse ordering leaves a live authorization over a run
    whose charge state is unknown, which is the silent second charge this
    surface exists to refuse.
    """

    envelope = read_authorization_artifact(path)
    if envelope.get("schema_version") != AUTHORIZATION_SCHEMA_VERSION:
        raise AttachmentPageAuthorizationError(
            "unexpected authorization schema version"
        )
    body = dict(
        _typed.mapping(
            envelope.get("authorization"),
            "authorization content",
            error=AttachmentPageAuthorizationError,
        )
    )
    if envelope.get("authorization_sha256") != _digest(body):
        raise AttachmentPageAuthorizationError("authorization digest does not verify")
    if body.get("paid_activity_executed") is not False:
        raise AttachmentPageAuthorizationError(
            "authorization already records executed paid activity"
        )
    body["paid_activity_executed"] = True
    replace_artifact(
        path,
        canonical_artifact_bytes(
            {
                "schema_version": AUTHORIZATION_SCHEMA_VERSION,
                "authorization": body,
                "authorization_sha256": _digest(body),
            },
            error=AttachmentPageAuthorizationError,
        ),
        error=AttachmentPageAuthorizationError,
    )


def read_authorization_artifact(path: Path) -> Mapping[str, object]:
    """Read one authorization artifact, refusing rather than tracebacking.

    A missing or malformed artifact on a charge-bearing path must produce the
    same fail-closed refusal as an unbound one, not a stack trace and an exit
    code that says something else.
    """

    try:
        return read_json_object(
            path,
            error_factory=AttachmentPageAuthorizationError,
            missing_message=lambda target: (
                f"no attachment-menu authorization exists at {target}"
            ),
            non_object_message=lambda target: (
                f"attachment-menu authorization at {target} is not a JSON object"
            ),
        )
    except json.JSONDecodeError as exc:
        raise AttachmentPageAuthorizationError(
            f"attachment-menu authorization at {path} is not valid JSON: {exc}"
        ) from exc
    except OSError as exc:
        raise AttachmentPageAuthorizationError(
            f"attachment-menu authorization at {path} could not be read: {exc}"
        ) from exc
