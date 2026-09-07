"""Native official-run tool-container construction.

The runner passes only authenticated model-visible documents to this factory.
The provider call remains owned by the managed model runtime; this module only
constructs and cleans the network-disabled tool session.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from pathlib import Path

from legalforecast.multiharness.adapters import ToolExecutor
from legalforecast.multiharness.container_runtime import ContainerToolSession
from legalforecast.multiharness.harvey_tools import HARVEY_TOOL_POLICY
from legalforecast.multiharness.sandbox import NETWORK_NONE, sandbox_policy
from legalforecast.multiharness.solver_inputs import (
    SolverInputPayload,
    SolverInputVisibleFile,
    prepare_solver_input,
    write_solver_input_store,
)
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    RunRequest,
)


@contextmanager
def open_official_tool_session(
    *,
    documents: Mapping[str, bytes],
    workspace: Path,
    session_id: str,
    environ: Mapping[str, str] | None = None,
) -> Generator[ToolExecutor]:
    """Stage documents and yield a real network-disabled container executor.

    ``environ`` is accepted for the caller's environment policy, but no values
    are copied into the container.  The only required variable is the local,
    digest-pinned tool image; provider and AWS credentials never enter it.
    """

    values = os.environ if environ is None else environ
    image = values.get("LFB_HARVEY_TOOL_IMAGE", "").strip()
    if not image:
        raise RuntimeError("LFB_HARVEY_TOOL_IMAGE is required for official tools")
    backend = values.get("LFB_CONTAINER_BACKEND", "docker").strip()
    if not session_id or any(char.isspace() for char in session_id):
        raise ValueError("session_id must be a non-empty identifier")
    if not documents:
        raise ValueError("at least one authenticated document is required")
    for path, content in documents.items():
        if not path.startswith("documents/") or not content:
            raise ValueError("documents must be non-empty bytes under documents/")

    workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="official-tools-", dir=workspace) as temp:
        private_root = Path(temp)
        packet = b"{}\n"
        task_sha = f"sha256:{hashlib.sha256(packet).hexdigest()}"
        prompt = _minimal_prompt(session_id, tuple(sorted(documents)))
        prompt_sha = f"sha256:{hashlib.sha256(prompt.encode()).hexdigest()}"
        task = CanonicalTask(
            task_id=f"official-tools:{session_id}",
            family="legalforecast_mtd",
            scoring_mode="lfb_brier",
            suite_version="forecast-release.v1",
            source_id="forecast-release.v1",
            task_sha256=task_sha,
            metadata={
                "prompt_sha256": prompt_sha,
                "required_unit_ids": [session_id],
                "tool_policy": HARVEY_TOOL_POLICY,
            },
        )
        store = write_solver_input_store(
            destination_root=private_root / "store",
            task_index_sha256=f"sha256:{'a' * 64}",
            payloads=(
                SolverInputPayload(
                    task=task,
                    prompt=prompt,
                    source_packet_bytes=packet,
                    visible_files=tuple(
                        SolverInputVisibleFile(
                            destination_path=path,
                            media_type="application/octet-stream",
                            content=content,
                        )
                        for path, content in sorted(documents.items())
                    ),
                ),
            ),
        )
        logs_root = private_root / "logs"
        logs_root.mkdir(mode=0o700)
        prepared = prepare_solver_input(store, task, logs_root)
        assert prepared.root is not None
        assert prepared.entry is not None
        policy = sandbox_policy(
            policy_id=HARVEY_TOOL_POLICY,
            backend=backend,
            image=image,
            mounts=(),
            network_policy=NETWORK_NONE,
            uid_gid="65532:65532",
            timeout_seconds=900,
            allowed_provider_env_vars=(),
        )
        adapter = AdapterManifest(
            adapter_id="official-harvey-tools",
            display_name="Official closed-universe Harvey tools",
            adapter_version="1.0.0",
            command=("legalforecast-harvey-tools",),
        )
        request = RunRequest(
            request_id=session_id,
            task=task,
            adapter=adapter,
            model_key="official-tools",
            sandbox_policy=policy,
            request_sha256=f"sha256:{hashlib.sha256(session_id.encode()).hexdigest()}",
        )
        session = ContainerToolSession(
            policy,
            request,
            workspace,
            solver_input_root=prepared.root,
            solver_input=prepared.entry,
            input_tree_sha256=prepared.tree_sha256,
        )
        try:
            yield session
        finally:
            session.abort()
            prepared.cleanup()


def _minimal_prompt(session_id: str, paths: tuple[str, ...]) -> str:
    return json.dumps(
        {
            "case_id": session_id,
            "document_paths": list(paths),
            "instruction": (
                "Read selected documents with the workspace tools before forecasting."
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


__all__ = ["open_official_tool_session"]
