"""Run the provider-free recovery-slice developer check with stable results."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TextIO, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_MANIFEST = REPO_ROOT / "tests" / "fixtures" / "cycle-preflight" / "manifest.json"
SCHEMA_VERSION = "legalforecast.dev_check_recovery_vertical_slice.v1"  # contract-ratchet: allow dev-only result  # noqa: E501
MANIFEST_ENV = "LEGALFORECAST_CYCLE_PREFLIGHT_MANIFEST"

CheckStatus = Literal["PASS", "FAIL", "NOT_EVALUATED"]
Mode = Literal["full", "quick"]
OutputFormat = Literal["text", "json"]


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One non-authoritative developer-check result and its elapsed time."""

    id: str
    status: CheckStatus
    duration_seconds: float
    code: str | None = None
    message: str | None = None
    suggestions: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    exit_code: int | None = None

    def to_record(self) -> dict[str, object]:
        """Return a stable JSON-compatible result record."""

        return {
            "id": self.id,
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "code": self.code,
            "message": self.message,
            "suggestions": list(self.suggestions),
            "examples": list(self.examples),
            "exit_code": self.exit_code,
        }


def _parser() -> argparse.ArgumentParser:
    """Build the compact, agent-oriented command-line interface."""

    parser = argparse.ArgumentParser(
        prog="scripts/dev-check-recovery-vertical-slice.sh",
        description=(
            "Run provider-free checks for the Cycle 1 recovery vertical slice. "
            "Diagnostics go to stderr; the final summary goes to stdout."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""\
Examples:
  scripts/dev-check-recovery-vertical-slice.sh --quick --manifest <path>
  scripts/dev-check-recovery-vertical-slice.sh --manifest <path> --require-real-lineage
  {MANIFEST_ENV}=<path> scripts/dev-check-recovery-vertical-slice.sh --json

Exit status: 0 for PASS or PASS_FIXTURE_ONLY, 1 for a failed check, 2 for usage.
""",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--full",
        action="store_true",
        help=(
            "Run focused regressions plus capsule and optional real preflight "
            "(default)."
        ),
    )
    mode.add_argument(
        "--quick",
        action="store_true",
        help="Run only the supplied real preflight, or the public capsule if absent.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help=f"Real-lineage manifest (or set {MANIFEST_ENV}).",
    )
    parser.add_argument(
        "--require-real-lineage",
        action="store_true",
        help="Fail when no non-fixture real-lineage manifest is configured.",
    )
    parser.add_argument(
        "--format",
        choices=("auto", "text", "json"),
        default="auto",
        help="Summary format; auto uses text on a TTY and JSON when piped.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the final summary as JSON (alias for --format json).",
    )
    return parser


def _execute(command: Sequence[str], *, diagnostics: TextIO) -> int:
    """Run one check in the repository and stream all child output to stderr."""

    return subprocess.run(
        tuple(command),
        cwd=REPO_ROOT,
        stdout=diagnostics,
        stderr=diagnostics,
        check=False,
    ).returncode


def _run_check(
    check_id: str,
    command: Sequence[str],
    *,
    diagnostics: TextIO,
) -> CheckResult:
    """Execute one check, retaining failure while allowing later checks to run."""

    print(f"CHECK {check_id}", file=diagnostics, flush=True)
    started = time.perf_counter()
    exit_code = _execute(command, diagnostics=diagnostics)
    elapsed = round(time.perf_counter() - started, 3)
    if exit_code == 0:
        result = CheckResult(check_id, "PASS", elapsed, exit_code=0)
    else:
        result = CheckResult(
            check_id,
            "FAIL",
            elapsed,
            code="CHECK_COMMAND_FAILED",
            message=f"command exited with status {exit_code}",
            suggestions=("Inspect the child diagnostics written to stderr.",),
            examples=(shlex.join(command),),
            exit_code=exit_code,
        )
    print(
        f"CHECK_RESULT {result.status} {check_id} duration_seconds={elapsed:.3f}",
        file=diagnostics,
        flush=True,
    )
    return result


def _real_manifest(args: argparse.Namespace) -> Path | None:
    """Resolve the explicit manifest before the backward-compatible environment."""

    explicit = cast(Path | None, args.manifest)
    if explicit is not None:
        return explicit.resolve()
    configured = os.environ.get(MANIFEST_ENV)
    return Path(configured).resolve() if configured else None


def _manifest_commitment_signature(value: object) -> tuple[str, ...]:
    """Return the order-independent SHA-256 commitment multiset in JSON data."""

    commitments: list[str] = []

    def collect(candidate: object) -> None:
        if isinstance(candidate, Mapping):
            for key, nested in cast(Mapping[object, object], candidate).items():
                if key == "sha256" and isinstance(nested, str):
                    digest = nested.removeprefix("sha256:").lower()
                    if len(digest) == 64 and all(
                        character in "0123456789abcdef" for character in digest
                    ):
                        commitments.append(digest)
                collect(nested)
        elif isinstance(candidate, Sequence) and not isinstance(
            candidate, (str, bytes)
        ):
            for nested in cast(Sequence[object], candidate):
                collect(nested)

    collect(value)
    return tuple(sorted(commitments))


def _is_public_fixture_manifest(manifest: Path) -> bool:
    """Recognize the public fixture by path or semantic commitment identity."""

    if manifest == PUBLIC_MANIFEST.resolve():
        return True
    try:
        configured = json.loads(manifest.read_bytes())
        public = json.loads(PUBLIC_MANIFEST.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    configured_commitments = frozenset(_manifest_commitment_signature(configured))
    public_commitments = frozenset(_manifest_commitment_signature(public))
    return bool(public_commitments) and public_commitments <= configured_commitments


def _classify_real_manifest(manifest: Path | None) -> tuple[Path | None, bool]:
    """Keep any copy of the checked-in synthetic capsule out of real scope."""

    if manifest is None:
        return None, False
    if _is_public_fixture_manifest(manifest):
        return None, True
    return manifest, False


def _is_v2_sidecar(manifest: Path) -> bool:
    """Recognize the non-authoritative v2 discovery input without trusting paths."""

    try:
        record = json.loads(manifest.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(record, Mapping):
        return False
    sidecar = cast(Mapping[str, object], record)
    return (
        sidecar.get("schema_version")
        == "legalforecast.cycle_preflight_manifest_sidecar.v1"
        and sidecar.get("non_authoritative") is True
    )


def _python_module(*arguments: str) -> tuple[str, ...]:
    """Build a child command using the already uv-managed interpreter."""

    return (sys.executable, "-m", *arguments)


def _missing_real_result(*, required: bool, public_fixture: bool) -> CheckResult:
    """Describe an absent real-lineage manifest without implying verification."""

    if public_fixture:
        return CheckResult(
            "real-lineage-preflight",
            "FAIL" if required else "NOT_EVALUATED",
            0.0,
            code="REAL_LINEAGE_MANIFEST_IS_PUBLIC_FIXTURE",
            message=(
                "the configured manifest is the checked-in public fixture or an "
                "equivalent copy"
            ),
            suggestions=("Supply the current authenticated lineage manifest.",),
            examples=(
                "scripts/dev-check-recovery-vertical-slice.sh "
                "--quick --manifest <real-lineage-path>",
            ),
        )
    if required:
        return CheckResult(
            "real-lineage-preflight",
            "FAIL",
            0.0,
            code="REAL_LINEAGE_MANIFEST_REQUIRED",
            message=f"pass --manifest PATH or set {MANIFEST_ENV}",
            suggestions=("Supply the current authenticated lineage manifest.",),
            examples=(
                "scripts/dev-check-recovery-vertical-slice.sh "
                "--quick --manifest <path>",
            ),
        )
    return CheckResult(
        "real-lineage-preflight",
        "NOT_EVALUATED",
        0.0,
        code="REAL_LINEAGE_MANIFEST_NOT_CONFIGURED",
        message=f"pass --manifest PATH or set {MANIFEST_ENV}",
        suggestions=("Use --require-real-lineage before merge.",),
        examples=(
            "scripts/dev-check-recovery-vertical-slice.sh --quick --manifest <path>",
        ),
    )


def _output_format(
    args: argparse.Namespace,
    *,
    stdout: TextIO,
    parser: argparse.ArgumentParser,
) -> OutputFormat:
    """Resolve explicit formatting flags and TTY-aware automatic output."""

    requested = cast(str, args.format)
    json_alias = cast(bool, args.json)
    if json_alias and requested == "text":
        parser.error("--json cannot be combined with --format text")
    if json_alias or requested == "json":
        return "json"
    if requested == "text":
        return "text"
    return "text" if stdout.isatty() else "json"


def _verdict(results: Sequence[CheckResult], *, real_manifest: Path | None) -> str:
    """Compute the honest aggregate result without elevating fixture coverage."""

    if any(result.status == "FAIL" for result in results):
        return "FAIL"
    if real_manifest is None:
        return "PASS_FIXTURE_ONLY"
    return "PASS"


def _text_summary(
    results: Sequence[CheckResult],
    *,
    verdict: str,
    duration_seconds: float,
    stream: TextIO,
) -> None:
    """Render the stable human-readable summary."""

    for result in results:
        fields = [
            "RESULT",
            result.status,
            result.id,
            f"duration_seconds={result.duration_seconds:.3f}",
        ]
        if result.code is not None:
            fields.append(f"code={result.code}")
        if result.exit_code is not None:
            fields.append(f"exit_code={result.exit_code}")
        print(" ".join(fields), file=stream)
        if result.message is not None:
            print(f"MESSAGE {result.id} {result.message}", file=stream)
        for suggestion in result.suggestions:
            print(f"SUGGESTION {suggestion}", file=stream)
        for example in result.examples:
            print(f"EXAMPLE {example}", file=stream)
    print(
        f"DEV_CHECK_VERDICT {verdict} duration_seconds={duration_seconds:.3f}",
        file=stream,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run requested checks, emit one stable summary, and return their status."""

    output = stdout if stdout is not None else sys.stdout
    diagnostics = stderr if stderr is not None else sys.stderr
    parser = _parser()
    args = parser.parse_args(argv)
    mode: Mode = "quick" if cast(bool, args.quick) else "full"
    output_format = _output_format(args, stdout=output, parser=parser)
    configured_manifest = _real_manifest(args)
    real_manifest, public_fixture = _classify_real_manifest(configured_manifest)
    require_real = cast(bool, args.require_real_lineage)

    started = time.perf_counter()
    results: list[CheckResult] = []
    if real_manifest is not None:
        command = (
            _python_module(
                "legalforecast.ingestion.cycle_preflight_manifest",
                "--verify-v2-sidecar",
                str(real_manifest),
                "--json",
            )
            if _is_v2_sidecar(real_manifest)
            else _python_module(
                "legalforecast.ingestion.cycle_preflight",
                "--manifest",
                str(real_manifest),
                "--format",
                "text",
            )
        )
        results.append(
            _run_check(
                "real-lineage-preflight",
                command,
                diagnostics=diagnostics,
            )
        )
    else:
        results.append(
            _missing_real_result(
                required=require_real,
                public_fixture=public_fixture,
            )
        )

    if mode == "full" and not (require_real and real_manifest is None):
        results.append(
            _run_check(
                "focused-regressions",
                _python_module(
                    "pytest",
                    "-q",
                    "tests/test_cycle_preflight.py",
                    "tests/test_successor_ledger_rehearsal.py",
                ),
                diagnostics=diagnostics,
            )
        )
        results.append(
            _run_check(
                "public-capsule-preflight",
                _python_module(
                    "legalforecast.ingestion.cycle_preflight",
                    "--manifest",
                    str(PUBLIC_MANIFEST),
                    "--format",
                    "text",
                ),
                diagnostics=diagnostics,
            )
        )
    elif mode == "quick" and real_manifest is None and not require_real:
        results.append(
            _run_check(
                "public-capsule-preflight",
                _python_module(
                    "legalforecast.ingestion.cycle_preflight",
                    "--manifest",
                    str(PUBLIC_MANIFEST),
                    "--format",
                    "text",
                ),
                diagnostics=diagnostics,
            )
        )

    duration_seconds = round(time.perf_counter() - started, 3)
    verdict = _verdict(results, real_manifest=real_manifest)
    if output_format == "json":
        json.dump(
            {
                "schema_version": SCHEMA_VERSION,
                "mode": mode,
                "verdict": verdict,
                "real_lineage_evaluated": real_manifest is not None,
                "duration_seconds": duration_seconds,
                "checks": [result.to_record() for result in results],
            },
            output,
            sort_keys=True,
            separators=(",", ":"),
        )
        output.write("\n")
    else:
        _text_summary(
            results,
            verdict=verdict,
            duration_seconds=duration_seconds,
            stream=output,
        )
    return 1 if verdict == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
