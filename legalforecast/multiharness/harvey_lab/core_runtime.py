"""Verified subprocess runtime for the public lab-core 1.1.0 contract."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from legalforecast._canonical import sha256_file
from legalforecast.multiharness.host_environment import (
    build_container_backend_environment,
    build_host_subprocess_environment,
    require_local_pinned_container_image,
    require_rootless_container_daemon,
)
from legalforecast.multiharness.process_containment import (
    ProcessContainmentHandle,
    cleanup_process_containment,
)
from legalforecast.multiharness.spec import POSIX_PROCESS_GROUP_CONTAINMENT

UPSTREAM_REPOSITORY = "https://github.com/harveyai/harvey-labs"
UPSTREAM_COMMIT = "1dd81403b2fbb60596f7aea3fcecafad7bf73143"
UPSTREAM_TREE = "bc7e16d2b5b794b86624288506a5d0be17c1052b"
PACKAGE_VERSION = "1.1.0"
RUN_MODULE = "lab_core.harness.run"
EVALUATE_MODULE = "lab_core.evaluation.run_eval"
_PACKAGE_PROBE = """import importlib.metadata, importlib.util, json, pathlib
print(json.dumps({"version": importlib.metadata.version("lab-core"),
"root": str(pathlib.Path(importlib.util.find_spec("lab_core").origin).parent)}))
"""


class LabCoreError(ValueError):
    """The pinned LAB package, request, or result cannot be used safely."""


@dataclass(frozen=True)
class LabCoreRuntime:
    """A caller-installed Python environment and its verified upstream source."""

    source_root: Path
    python: Path

    def verify(self, private_root: Path) -> dict[str, str]:
        """Bind Git source, installed package bytes, and interpreter identity."""
        source = self.source_root.resolve(strict=True)
        environment = self.environment(private_root)
        for spec, expected in (
            ("HEAD", UPSTREAM_COMMIT),
            ("HEAD^{tree}", UPSTREAM_TREE),
        ):
            observed = self._git(source, environment, "rev-parse", spec).strip()
            if observed != expected:
                raise LabCoreError("LAB source does not match the supported v1.1.0 pin")
        if self._git(
            source, environment, "status", "--porcelain", "--untracked-files=all"
        ).strip():
            raise LabCoreError("LAB source checkout has unreviewed changes")
        if (
            Path(self._git(source, environment, "rev-parse", "--show-toplevel").strip())
            != source
        ):
            raise LabCoreError("LAB source must be the checkout root")
        result = subprocess.run(
            [str(self.python.absolute()), "-B", "-I", "-c", _PACKAGE_PROBE],
            cwd=private_root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        (private_root / "package-probe.stderr").write_text(
            result.stderr, encoding="utf-8"
        )
        if result.returncode != 0:
            raise LabCoreError("Python environment cannot import installed lab-core")
        try:
            decoded: object = json.loads(result.stdout)
            if not isinstance(decoded, dict):
                raise LabCoreError("lab-core identity probe must return an object")
            record = cast(dict[str, object], decoded)
            if record.get("version") != PACKAGE_VERSION:
                raise LabCoreError("installed lab-core must be version 1.1.0")
            root = record.get("root")
            if not isinstance(root, str):
                raise LabCoreError("installed lab-core has no package root")
            installed = Path(root).resolve(strict=True)
        except (json.JSONDecodeError, OSError) as exc:
            raise LabCoreError(
                "lab-core identity probe returned malformed output"
            ) from exc
        expected_files = regular_files(source / "lab_core")
        installed_files = regular_files(installed)
        if set(expected_files) != set(installed_files) or any(
            sha256_file(path) != sha256_file(installed_files[name])
            for name, path in expected_files.items()
        ):
            raise LabCoreError("installed lab-core bytes differ from the pinned source")
        return {
            "repository": UPSTREAM_REPOSITORY,
            "commit": UPSTREAM_COMMIT,
            "tree": UPSTREAM_TREE,
            "package_version": PACKAGE_VERSION,
            "python_sha256": sha256_file(self.python),
            "license": "MIT",
            "license_sha256": sha256_file(source / "LICENSE"),
        }

    def environment(
        self, private_root: Path, provider_env: tuple[str, ...] = ()
    ) -> dict[str, str]:
        """Project only requested provider values, with no dotenv discovery."""
        environment = build_host_subprocess_environment(private_root, provider_env)
        environment["PYTHON_DOTENV_DISABLED"] = "1"
        return environment

    def probe(self, private_root: Path) -> dict[str, str]:
        """Check both real CLI entrypoints without credentials or provider calls."""
        identity = self.verify(private_root)
        for module, flags in (
            (
                RUN_MODULE,
                ("--model", "--task", "--run-id", "--max-turns", "--sandbox-image"),
            ),
            (EVALUATE_MODULE, ("--run-id", "--task", "--judges", "--parallel")),
        ):
            self.invoke(
                module,
                ("--help",),
                private_root=private_root,
                lab_root=private_root,
                phase=module.rsplit(".", 1)[-1] + "-help",
                timeout=60,
            )
            help_text = (
                private_root / (module.rsplit(".", 1)[-1] + "-help.stdout")
            ).read_text()
            if any(flag not in help_text for flag in flags):
                raise LabCoreError(
                    "lab-core CLI no longer exposes the supported contract"
                )
        if self.verify(private_root) != identity:
            raise LabCoreError("lab-core provenance changed during its probe")
        return identity

    def prepare_sandbox(self, private_root: Path, image: str) -> None:
        """Require a local rootless image before any provider-bearing command."""
        executable = shutil.which("podman")
        if executable is None:
            raise LabCoreError("the native LAB solver requires Podman")
        environment = self.sandbox_environment(private_root)
        require_rootless_container_daemon(Path(executable), "podman", environment)
        require_local_pinned_container_image(Path(executable), image, environment)

    def sandbox_environment(self, private_root: Path) -> dict[str, str]:
        """Retain local container storage/runtime paths alongside isolated homes."""
        environment = self.environment(private_root)
        environment.update(build_container_backend_environment())
        # Podman locates rootless images here. Preserve data storage, not the
        # caller's home/config directories (which can contain provider credentials).
        environment["XDG_DATA_HOME"] = os.environ.get(
            "XDG_DATA_HOME", str(Path.home() / ".local" / "share")
        )
        return environment

    def invoke(
        self,
        module: str,
        arguments: tuple[str, ...],
        *,
        private_root: Path,
        lab_root: Path,
        phase: str,
        timeout: float,
        provider_env: tuple[str, ...] = (),
    ) -> None:
        """Execute one upstream command with shared process-group cleanup."""
        environment = self.environment(private_root, provider_env)
        if module == RUN_MODULE and arguments != ("--help",):
            environment.update(self.sandbox_environment(private_root))
        environment["LAB_ROOT"] = str(lab_root.resolve(strict=True))
        argv = [
            str(self.python.absolute()),
            "-B",
            "-I",
            "-X",
            f"pycache_prefix={private_root / 'unused-bytecode'}",
            "-m",
            module,
            *arguments,
        ]
        with (
            (private_root / f"{phase}.stdout").open("wb") as stdout,
            (private_root / f"{phase}.stderr").open("wb") as stderr,
        ):
            process = subprocess.Popen(
                argv,
                cwd=private_root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
            handle = ProcessContainmentHandle(
                requested=POSIX_PROCESS_GROUP_CONTAINMENT, process_group_id=process.pid
            )
            try:
                returncode = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                # Let native LAB's finally/atexit handlers stop its container.
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=65)
                except subprocess.TimeoutExpired:
                    pass  # Shared process-group cleanup remains the backstop.
                raise LabCoreError(
                    f"LAB {phase} exceeded its timeout; inspect private logs"
                ) from exc
            finally:
                cleanup_process_containment(handle, process, grace_seconds=3)
        if returncode:
            raise LabCoreError(f"LAB {phase} exited {returncode}; inspect private logs")

    @staticmethod
    def _git(source: Path, environment: dict[str, str], *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(source), *args],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode:
            raise LabCoreError(
                f"unable to verify LAB Git source: {result.stderr.strip()}"
            )
        return result.stdout


def regular_files(root: Path) -> dict[str, Path]:
    """Enumerate regular contained files, excluding Python's generated bytecode."""
    if root.is_symlink() or not root.is_dir():
        raise LabCoreError("LAB file root must be a real directory")
    result: dict[str, Path] = {}
    for directory, directories, names in os.walk(root, followlinks=False):
        directories[:] = [name for name in directories if name != "__pycache__"]
        for name in (*directories, *names):
            if (Path(directory) / name).is_symlink():
                raise LabCoreError("LAB inputs and outputs must not contain symlinks")
        for name in names:
            path = Path(directory) / name
            if not path.is_file():
                raise LabCoreError("LAB inputs and outputs must be regular files")
            result[path.relative_to(root).as_posix()] = path
    return result
