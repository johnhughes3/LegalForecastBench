"""Behavioural proof that a harness actually used a tool inside its container.

The lane's claim is that an agentic CLI beats the bare API *because it used its
tools*.  Today the only evidence for that is each harness grading its own
homework, and the grades are uneven: Claude Code and Codex name their tool
calls in the transcript, Grok and Kimi are unverified live, and Antigravity
names no tools at all -- :mod:`.tool_accounting` is careful to report that as
``unreported`` rather than as zero, because "the harness does not say" and "the
harness used nothing" are different claims.

A workspace sentinel replaces self-report with an observation.  A
high-entropy token is written into a file in the mounted workspace and appears
nowhere in the prompt; the prompt asks the agent to read that file and echo the
value back.  A token that returns could only have come from a local file read
inside the container, so the evidence is uniform across all five harnesses and
does not depend on any of them describing themselves.

WHY THIS IS A SEPARATE PROBE RUN AND NOT A RIDE-ALONG
-----------------------------------------------------
The cheap-looking design is to append the sentinel instruction to the scored
task's prompt.  It is rejected on two grounds, the first decisive:

* **The scored prompt is bound by digest.**
  :meth:`~.adapter.ContainerCliAdapter.run_with_solver_input` fetches the
  prompt *by* its ``prompt_sha256`` from the private solver-input store, and
  the release evidence binds request, packet, prompt and response together.
  Appending anything makes that recorded digest describe bytes the model never
  saw.  Trading a falsified provenance record for tool evidence is a bad trade
  in an academic benchmark, and it is not one this lane gets to make.
* **The answer channel is the scored channel.**  The deliverable is projected
  out of stdout by the manifest's ``task_projection``; a sentinel line inside
  it either breaks that projection or has to be stripped back out, which is
  exactly the coupling that would let a score depend on the sentinel.

So the probe is its own container run, once per harness per lane run -- five
invocations for a whole lane, not one per scored row (which is the expensive
version ride-along would actually cost).  It runs the same image, credentials,
mount and tool posture the scored rows will run under, in a workspace of its
own, so it can never collide with :func:`~.lab_workspace.stage_projected_lab_task`
and never touches a scored prompt.

WHAT IT PROVES, EXACTLY
-----------------------
That this harness, in this image, with this workspace mount and this tool
posture, exercised a local file-reading tool.  It does *not* prove tool use on
any particular scored row.  That is a narrower claim than a ride-along would
make -- and still strictly more than self-report gives, which for Antigravity
is nothing at all.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Final

from legalforecast.multiharness.container_harness.plan import WORKSPACE_TARGET

if TYPE_CHECKING:  # pragma: no cover - import only for the driver's annotation
    from legalforecast.multiharness.harness_lane.adapter import ContainerCliAdapter

SENTINEL_RELATIVE_PATH: Final = "harness-sentinel/workspace-token.txt"
CONTAINER_WORKSPACE_DIRECTORY: Final = "container-workspace"
CONTAINER_LOG_DIRECTORY: Final = "container-logs"
# 128 bits of entropy.  The floor is what makes substring matching meaningful:
# a short token could plausibly occur in a transcript by accident, and a
# guessable one would let a model that never read the file answer correctly.
TOKEN_BYTES: Final = 16
MINIMUM_TOKEN_CHARACTERS: Final = 16


class SentinelError(ValueError):
    """Raised when a workspace sentinel cannot prove what it claims to prove."""


class SentinelVerdict(StrEnum):
    """What one run's sentinel evidence actually says about tool use."""

    PROVEN = "proven"
    ABSENT = "absent"
    NOT_ATTEMPTED = "not_attempted"


@dataclass(frozen=True, slots=True)
class WorkspaceSentinel:
    """One run's token, where it is staged, and the prompt that asks for it."""

    token: str
    relative_path: str = SENTINEL_RELATIVE_PATH

    def __post_init__(self) -> None:
        if len(self.token) < MINIMUM_TOKEN_CHARACTERS:
            raise SentinelError(
                f"a sentinel token needs at least {MINIMUM_TOKEN_CHARACTERS} "
                f"characters so a chance substring match is not mistaken for "
                f"tool use, got {len(self.token)}"
            )
        if self.token.strip() != self.token or not self.token.isalnum():
            raise SentinelError(
                "a sentinel token must be alphanumeric with no surrounding "
                "whitespace so a harness cannot reflow it while echoing it back"
            )
        relative = PurePosixPath(self.relative_path)
        if relative.is_absolute() or any(
            part in {"", ".", ".."} for part in relative.parts
        ):
            raise SentinelError(
                "relative_path must stay inside the mounted workspace, got "
                f"{self.relative_path!r}"
            )

    @property
    def container_path(self) -> str:
        """Return the path the agent will be told to read, inside the container."""

        return f"{WORKSPACE_TARGET}/{self.relative_path}"

    def prompt(self) -> str:
        """Return the probe instruction, which never contains the token itself."""

        return (
            f"Use your file-reading tool to read the file {self.container_path}. "
            "Reply with exactly one line, SENTINEL=<the file's contents>, and "
            "nothing else. The value exists only inside that file: it is not in "
            "this message and cannot be guessed, so do not answer without "
            "reading the file."
        )


@dataclass(frozen=True, slots=True)
class SentinelCheck:
    """One typed verdict on whether the agent surfaced the token."""

    verdict: SentinelVerdict
    found_in: str | None = None
    token: str | None = None

    @property
    def proven(self) -> bool:
        """Return whether a local tool read was observed rather than reported."""

        return self.verdict is SentinelVerdict.PROVEN

    def to_public_record(self) -> dict[str, Any]:
        """Return the JSON-ready evidence record.

        The token is published on purpose: it is random, disposable, and
        secret to nothing, and publishing it is what lets a reader grep the
        stored transcript and redo the check rather than take this verdict on
        trust.
        """

        return {
            "sentinel_verdict": self.verdict.value,
            "sentinel_found_in": self.found_in,
            "sentinel_token": self.token,
        }


@dataclass(frozen=True, slots=True)
class SentinelProbe:
    """A probe run's verdict plus enough to tell a crash from a refusal."""

    sentinel: WorkspaceSentinel
    check: SentinelCheck
    exit_code: int | None
    timed_out: bool

    def to_public_record(self) -> dict[str, Any]:
        """Return the verdict beside the probe's own exit, never merged into it.

        A probe that crashed and a probe whose model never surfaced the token
        both leave the verdict at ``absent``; only these two fields separate
        "the harness declined to use a tool" from "the run never happened".
        """

        return {
            **self.check.to_public_record(),
            "sentinel_probe_exit_code": self.exit_code,
            "sentinel_probe_timed_out": self.timed_out,
        }


def mint_workspace_sentinel(
    *, token: str | None = None, relative_path: str = SENTINEL_RELATIVE_PATH
) -> WorkspaceSentinel:
    """Mint one run's sentinel, with a fresh token unless one is supplied."""

    return WorkspaceSentinel(
        token=token if token is not None else secrets.token_hex(TOKEN_BYTES),
        relative_path=relative_path,
    )


def materialize_workspace_sentinel(
    sentinel: WorkspaceSentinel, workspace: Path
) -> Path:
    """Write the token into the workspace the container will mount.

    Refuses an existing file rather than overwriting: a token left over from an
    earlier run would make this run's verdict describe the wrong invocation.
    """

    path = workspace.joinpath(*PurePosixPath(sentinel.relative_path).parts)
    if path.exists():
        raise SentinelError(
            f"{sentinel.relative_path} already exists in this workspace; a "
            "sentinel is per-run, and reusing a staged one would attribute an "
            "earlier run's token to this one"
        )
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(f"{sentinel.token}\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def check_workspace_sentinel(
    sentinel: WorkspaceSentinel | None,
    *,
    prompt: str,
    answer: str | None = None,
    transcript: str | None = None,
) -> SentinelCheck:
    """Return the typed verdict for one run's sentinel evidence.

    ``prompt`` is the text the agent was actually handed, and it is checked
    first: a token the prompt discloses proves nothing, because the agent could
    have echoed it without touching a file.  That is a void sentinel, not a run
    outcome, so it is refused rather than scored as one of the three verdicts.

    Matching is exact-substring on purpose.  A model that paraphrases or
    mangles the token lands at ``absent``, which is the safe direction for
    evidence: this understates tool use rather than inventing it.
    """

    if sentinel is None:
        return SentinelCheck(verdict=SentinelVerdict.NOT_ATTEMPTED)
    if sentinel.token in prompt:
        raise SentinelError(
            "the sentinel token appears in the prompt, so echoing it back "
            "would prove nothing about tool use; mint a fresh sentinel and "
            "keep the token out of everything the agent is handed"
        )
    for channel, text in (("answer", answer), ("transcript", transcript)):
        if text is not None and sentinel.token in text:
            return SentinelCheck(
                verdict=SentinelVerdict.PROVEN,
                found_in=channel,
                token=sentinel.token,
            )
    return SentinelCheck(verdict=SentinelVerdict.ABSENT, token=sentinel.token)


def probe_workspace_tool_use(
    adapter: ContainerCliAdapter,
    *,
    workspace: Path,
    model_key: str,
    sentinel: WorkspaceSentinel | None = None,
) -> SentinelProbe:
    """Run one sentinel probe for a harness and return what it observed.

    The spec is assembled here rather than through
    :meth:`~.adapter.ContainerCliAdapter.container_spec` because that method
    takes a ``RunRequest``, and inventing a synthetic scored row to satisfy it
    would put a fake task into production code.  Everything the spec needs is
    already on the adapter's public surface.
    """

    from legalforecast.multiharness.container_harness import ContainerHarnessSpec
    from legalforecast.multiharness.harness_lane.auth import (
        container_child_env,
        container_credentials,
    )

    minted = sentinel if sentinel is not None else mint_workspace_sentinel()
    container_workspace = workspace / CONTAINER_WORKSPACE_DIRECTORY
    container_workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
    materialize_workspace_sentinel(minted, container_workspace)
    prompt = minted.prompt()
    spec = ContainerHarnessSpec(
        run_id=(
            f"{adapter.identity.executable_basename}-sentinel-{secrets.token_hex(5)}"
        ),
        image=adapter.image,
        harness_argv=adapter.local_manifest.invocation.render_argv(
            prompt=prompt, model=model_key, workspace=WORKSPACE_TARGET
        ),
        workspace=container_workspace,
        log_root=workspace / CONTAINER_LOG_DIRECTORY,
        allow_hosts=adapter.allow_hosts,
        allow_subdomains=adapter.allow_subdomains,
        allow_ports=adapter.allow_ports,
        credentials=container_credentials(
            adapter.identity, adapter.auth_profile, adapter.environment()
        ),
        environment=container_child_env(adapter.identity, adapter.auth_profile),
        timeout_seconds=adapter.local_manifest.timeout_retry.timeout_seconds,
    )
    result = adapter.run_container(spec)
    try:
        transcript = result.stdout_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        # A missing stdout file is a failed probe, not a crash of the checker;
        # the empty transcript lands as ``absent`` beside the exit code.
        transcript = ""
    return SentinelProbe(
        sentinel=minted,
        check=check_workspace_sentinel(minted, prompt=prompt, transcript=transcript),
        exit_code=result.exit_code,
        timed_out=result.timed_out,
    )
