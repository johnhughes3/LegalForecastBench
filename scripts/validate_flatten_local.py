"""Validate and flatten any local model result envelope.

The envelope implementation remains in ``validate_flatten_local_luna`` for
backward compatibility with the completed Luna run.  This adapter supplies
the expected model and, when requested, the authenticated prompt-commitment
map for supplementary model runs.  It never creates labels or overwrites an
existing score input.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from scripts.validate_flatten_local_luna import (
    LocalLunaResultError,
)
from scripts.validate_flatten_local_luna import (
    flatten_results as _flatten_results,
)

LocalModelResultError = LocalLunaResultError


def _read_prompt_commitments(path: Path) -> Mapping[str, str]:
    """Read a bare prompt map or a frozen run-record prompt map."""

    if path.is_symlink() or not path.is_file():
        raise LocalModelResultError(
            f"prompt commitments must be a regular non-symlink file: {path}"
        )
    try:
        decoded: object = json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise LocalModelResultError(
            f"prompt commitments are not readable JSON: {path}"
        ) from exc
    if isinstance(decoded, Mapping):
        decoded_mapping = cast(Mapping[str, object], decoded)
        prompt_commitments = decoded_mapping.get("prompt_commitments")
        if isinstance(prompt_commitments, Mapping):
            decoded = cast(Mapping[object, object], prompt_commitments)
    if not isinstance(decoded, Mapping):
        raise LocalModelResultError("prompt commitments must be an object")
    result: dict[str, str] = {}
    mapping = cast(Mapping[object, object], decoded)
    for key, value in mapping.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise LocalModelResultError(
                "prompt commitments must map string identities to string digests"
            )
        result[key] = value
    return result


def flatten_results(
    results_dir: Path,
    output_path: Path,
    *,
    expected_count: int | None = None,
    expected_model_key: str,
    expected_registry_sha256: str | None = None,
    expected_prompt_commitments: Mapping[str, str] | None = None,
    derive_missing_output_statuses: frozenset[str] = frozenset(),
) -> int:
    """Validate model, registry, prompt, and response commitments then flatten."""

    return _flatten_results(
        results_dir,
        output_path,
        expected_count=expected_count,
        expected_model_key=expected_model_key,
        expected_registry_sha256=expected_registry_sha256,
        expected_prompt_commitments=expected_prompt_commitments,
        derive_missing_output_statuses=derive_missing_output_statuses,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--model-key", required=True)
    parser.add_argument("--expected-registry-sha256")
    parser.add_argument(
        "--expected-prompt-commitments",
        type=Path,
        help="Frozen run record or bare identity-to-prompt-SHA map.",
    )
    parser.add_argument(
        "--derive-missing-output-statuses-for",
        action="append",
        default=[],
        metavar="CASE:ABLATION",
    )
    args = parser.parse_args(argv)
    prompt_commitments = (
        _read_prompt_commitments(args.expected_prompt_commitments)
        if args.expected_prompt_commitments is not None
        else None
    )
    count = flatten_results(
        args.results_dir,
        args.output,
        expected_count=args.expected_count,
        expected_model_key=args.model_key,
        expected_registry_sha256=args.expected_registry_sha256,
        expected_prompt_commitments=prompt_commitments,
        derive_missing_output_statuses=frozenset(
            cast(list[str], args.derive_missing_output_statuses_for)
        ),
    )
    print(
        json.dumps({"result_count": count, "output": str(args.output)}, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
