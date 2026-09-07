"""Pure, testable plan data for one containerized harness run.

Everything here is a value: the run spec, the derived Docker object names, the
exact argv and environment that would be handed to the backend, and the typed
result.  Nothing in this module spawns a process, so the whole plan -- including
the isolation flags and the clean-HOME environment -- is asserted directly in
tests without a container backend being present.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any, Final

from legalforecast.multiharness.container_harness.cli_fence import (
    DEFAULT_BIN_DIR,
    DEFAULT_CREDENTIALS_ROOT,
    DEFAULT_LIBEXEC_DIR,
    FENCED_CLIS,
    WRAPPER_NAME,
)
from legalforecast.multiharness.container_harness.egress_proxy import (
    DEFAULT_ALLOWED_PORTS,
    EgressAllowlist,
)
from legalforecast.multiharness.container_harness.images import (
    require_digest_pinned_image,
)

FENCE_BIN_DIR = DEFAULT_BIN_DIR
CREDENTIALS_TARGET = DEFAULT_CREDENTIALS_ROOT
FENCE_LIBEXEC_DIR = DEFAULT_LIBEXEC_DIR
PROXY_SOURCE_TARGET: Final[str] = "/opt/legalforecast/egress_proxy.py"
PROXY_EVIDENCE_DIR: Final[str] = "/var/legalforecast-egress"
PROXY_EVIDENCE_TARGET: Final[str] = f"{PROXY_EVIDENCE_DIR}/egress-evidence.json"
WORKSPACE_TARGET: Final[str] = "/workspace"
DEFAULT_CONTAINER_HOME: Final[str] = "/home/harness"
DEFAULT_PROXY_PORT: Final[int] = 3128
FENCE_WRAPPER_TARGET: Final[str] = f"{FENCE_BIN_DIR}/{WRAPPER_NAME}"
FENCE_PATH: Final[str] = (
    f"{FENCE_BIN_DIR}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
)
_RUN_ID_CHARACTERS: Final[str] = "abcdefghijklmnopqrstuvwxyz0123456789-"


class ContainerHarnessError(RuntimeError):
    """Raised when a containerized harness run cannot be set up or completed."""


@dataclass(frozen=True, slots=True)
class HarnessCredential:
    """One credential file to copy into the run's throwaway container HOME."""

    host_path: Path
    home_relative_path: str

    def __post_init__(self) -> None:
        if not self.host_path.is_absolute():
            raise ContainerHarnessError("credential host_path must be absolute")
        relative = PurePosixPath(self.home_relative_path)
        if relative.is_absolute() or not self.home_relative_path:
            raise ContainerHarnessError(
                "credential home_relative_path must be relative to the container HOME"
            )
        if any(part in {"", ".", ".."} for part in relative.parts):
            raise ContainerHarnessError(
                "credential home_relative_path must not contain traversal segments"
            )


@dataclass(frozen=True, slots=True)
class ContainerHarnessSpec:
    """Everything one containerized harness run needs, declared up front."""

    run_id: str
    image: str
    harness_argv: tuple[str, ...]
    workspace: Path
    log_root: Path
    allow_hosts: tuple[str, ...] = ()
    allow_subdomains: tuple[str, ...] = ()
    allow_ports: tuple[int, ...] = tuple(sorted(DEFAULT_ALLOWED_PORTS))
    credentials: tuple[HarnessCredential, ...] = ()
    environment: Mapping[str, str] = field(default_factory=dict[str, str])
    container_home: str = DEFAULT_CONTAINER_HOME
    cli_name: str | None = None
    harness_entrypoint: str | None = None
    proxy_image: str | None = None
    proxy_python: str = "python3"
    proxy_port: int = DEFAULT_PROXY_PORT
    egress_network: str | None = None
    timeout_seconds: int = 900
    pids_limit: int = 512
    memory_limit: str = "4g"
    cpu_limit: str = "2"
    read_only_rootfs: bool = True

    def __post_init__(self) -> None:
        if not self.run_id or not all(
            character in _RUN_ID_CHARACTERS for character in self.run_id
        ):
            raise ContainerHarnessError(
                "run_id must be lowercase letters, digits and hyphens so it can "
                f"name a Docker network and container, got {self.run_id!r}"
            )
        require_digest_pinned_image(self.image, "image")
        if self.proxy_image is not None:
            require_digest_pinned_image(self.proxy_image, "proxy_image")
        if not self.harness_argv:
            raise ContainerHarnessError(
                "harness_argv must be fully flag-explicit; a clean container has no "
                "host config to fall back on"
            )
        if not PurePosixPath(self.container_home).is_absolute():
            raise ContainerHarnessError("container_home must be an absolute path")
        if not 1 <= self.proxy_port <= 65535:
            raise ContainerHarnessError("proxy_port is out of range")
        if self.timeout_seconds <= 0:
            raise ContainerHarnessError("timeout_seconds must be positive")
        fenced_cli_name(self)

    def allowlist(self) -> EgressAllowlist:
        """Return the validated allowlist for this run."""

        return EgressAllowlist.from_rules(
            hosts=self.allow_hosts,
            subdomains=self.allow_subdomains,
            ports=self.allow_ports,
        )

    def resolved_proxy_image(self) -> str:
        """Return the sidecar image, defaulting to the harness image itself."""

        return self.proxy_image or self.image


@dataclass(frozen=True, slots=True)
class ContainerHarnessNames:
    """The per-run Docker object names, all derived from run_id plus a token."""

    network: str
    egress_network: str
    proxy_container: str
    harness_container: str


@dataclass(frozen=True, slots=True)
class ContainerHarnessResult:
    """What one containerized harness run produced, and where it went."""

    run_id: str
    exit_code: int | None
    timed_out: bool
    duration_seconds: float
    stdout_path: Path
    stderr_path: Path
    image_id: str
    proxy_image_id: str
    allowed_hosts: tuple[str, ...]
    refused: tuple[Mapping[str, Any], ...]
    allowlist: Mapping[str, Any]

    def to_record(self) -> dict[str, Any]:
        """Return a public JSON record without attacker-controlled hostnames.

        The raw decisions remain available on this in-process result for operator
        diagnosis. The runtime's mandatory publication step replaces them with
        policy-derived public forms before writing any package.
        """

        return {
            "run_id": self.run_id,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "duration_seconds": round(self.duration_seconds, 3),
            "stdout_file": self.stdout_path.name,
            "stderr_file": self.stderr_path.name,
            "image_id": self.image_id,
            "proxy_image_id": self.proxy_image_id,
            "egress_allowlist": dict(self.allowlist),
            "egress_allowed_host_count": len(self.allowed_hosts),
            "egress_refused_count": len(self.refused),
        }


def build_run_names(run_id: str, token: str) -> ContainerHarnessNames:
    """Return collision-free Docker names for one run."""

    if len(token) < 8 or not all(
        character in "0123456789abcdef" for character in token
    ):
        raise ContainerHarnessError("run token must be at least 8 hex characters")
    stem = f"lfb-{run_id}-{token}"
    return ContainerHarnessNames(
        network=f"{stem}-net",
        egress_network=f"{stem}-out",
        proxy_container=f"{stem}-egress",
        harness_container=f"{stem}-harness",
    )


def egress_proxy_source_path() -> Path:
    """Return the on-disk path of the single-file proxy that the sidecar runs."""

    resource = files("legalforecast.multiharness.container_harness").joinpath(
        "egress_proxy.py"
    )
    path = Path(str(resource))
    if not path.is_file():
        raise ContainerHarnessError(
            "egress_proxy.py is not available as a real file; the sidecar bind-mounts "
            "it, so a zipped or namespace install is not supported"
        )
    return path


def cli_fence_source_path() -> Path:
    """Return the on-disk path of the wrapper bind-mounted into the harness."""

    resource = files("legalforecast.multiharness.container_harness").joinpath(
        "cli_fence.py"
    )
    path = Path(str(resource))
    if not path.is_file():
        raise ContainerHarnessError(
            "cli_fence.py is not available as a real file; the harness bind-mounts "
            "it, so a zipped or namespace install is not supported"
        )
    return path


def fenced_cli_name(spec: ContainerHarnessSpec) -> str:
    """Return the tools-on CLI this run fences, or fail closed."""

    if spec.cli_name is not None:
        name = spec.cli_name
    elif spec.harness_entrypoint is not None:
        name = PurePosixPath(spec.harness_entrypoint).name
    else:
        name = PurePosixPath(spec.harness_argv[0]).name
    if name not in FENCED_CLIS:
        raise ContainerHarnessError(
            f"harness CLI {name!r} is not a fenced tools-on CLI; refusing to "
            "run an unfenced nested-invocable binary"
        )
    return name


def stage_cli_fence(root: Path) -> Path:
    """Copy the wrapper to a 0755 file the container can exec as its entrypoint."""

    dest = root / "fence" / WRAPPER_NAME
    dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    dest.write_bytes(cli_fence_source_path().read_bytes())
    dest.chmod(0o755)
    return dest


def build_network_create_argv(
    backend_path: Path, names: ContainerHarnessNames
) -> tuple[str, ...]:
    """Return argv creating the per-run network with no external route."""

    return (str(backend_path), "network", "create", "--internal", names.network)


def build_egress_network_create_argv(
    backend_path: Path, names: ContainerHarnessNames
) -> tuple[str, ...]:
    """Return argv creating the per-run routable network the sidecar egresses on."""

    return (str(backend_path), "network", "create", names.egress_network)


def egress_network_name(
    spec: ContainerHarnessSpec, names: ContainerHarnessNames
) -> str:
    """Return the network the sidecar reaches the internet through.

    The default is a per-run network rather than the shared default bridge:
    the sidecar listens on every interface it has, so on a shared bridge any
    other local container could relay through it to the allowlisted hosts for
    as long as the run lasts.  A named override stays available for a host that
    must egress through a specific existing network.
    """

    return spec.egress_network or names.egress_network


def build_network_connect_argv(
    backend_path: Path, spec: ContainerHarnessSpec, names: ContainerHarnessNames
) -> tuple[str, ...]:
    """Return argv giving the sidecar -- and only the sidecar -- external reach."""

    return (
        str(backend_path),
        "network",
        "connect",
        egress_network_name(spec, names),
        names.proxy_container,
    )


def build_proxy_run_argv(
    backend_path: Path,
    spec: ContainerHarnessSpec,
    names: ContainerHarnessNames,
    *,
    proxy_source: Path,
    evidence_directory: Path,
) -> tuple[str, ...]:
    """Return argv starting the detached allowlist egress sidecar."""

    allowlist = spec.allowlist()
    argv: list[str] = [
        str(backend_path),
        "run",
        "--detach",
        "--name",
        names.proxy_container,
        "--network",
        names.network,
        "--pull=never",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=16m",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "64",
        "--memory",
        "256m",
        "--cpus=0.5",
        "--mount",
        f"type=bind,src={proxy_source},dst={PROXY_SOURCE_TARGET},readonly",
        "--mount",
        f"type=bind,src={evidence_directory},dst={PROXY_EVIDENCE_DIR}",
        "--entrypoint",
        spec.proxy_python,
        spec.resolved_proxy_image(),
        PROXY_SOURCE_TARGET,
        "--bind",
        "0.0.0.0",
        "--port",
        str(spec.proxy_port),
        "--evidence-file",
        PROXY_EVIDENCE_TARGET,
    ]
    for host in sorted(allowlist.hosts):
        argv.extend(("--allow-host", host))
    for parent in sorted(allowlist.subdomain_suffixes):
        argv.extend(("--allow-subdomains", parent))
    for port in sorted(allowlist.ports):
        argv.extend(("--allow-port", str(port)))
    return tuple(argv)


def build_harness_environment(
    spec: ContainerHarnessSpec, names: ContainerHarnessNames
) -> dict[str, str]:
    """Return the child environment: clean HOME, proxy vars, manifest additions.

    Nothing is inherited from the operator's shell.  Both the upper- and
    lower-case proxy spellings are set because Node, Python and Go clients
    disagree about which they honour, and ``HTTP_PROXY`` points at the same
    sidecar on purpose so a cleartext attempt is refused and recorded rather
    than failing silently somewhere else.
    """

    proxy_url = f"http://{names.proxy_container}:{spec.proxy_port}"
    no_proxy = "localhost,127.0.0.1,::1"
    cli = fenced_cli_name(spec)
    environment = {
        "HOME": spec.container_home,
        "HTTP_PROXY": proxy_url,
        "HTTPS_PROXY": proxy_url,
        "http_proxy": proxy_url,
        "https_proxy": proxy_url,
        "NO_PROXY": no_proxy,
        "no_proxy": no_proxy,
    }
    environment.update(spec.environment)
    environment.update(
        {
            "HOME": spec.container_home,
            "PATH": FENCE_PATH,
            "LFB_HARNESS_CLI": cli,
            "LFB_CREDENTIALS_ROOT": CREDENTIALS_TARGET,
            "HTTP_PROXY": proxy_url,
            "HTTPS_PROXY": proxy_url,
            "http_proxy": proxy_url,
            "https_proxy": proxy_url,
            "NO_PROXY": no_proxy,
            "no_proxy": no_proxy,
        }
    )
    # Never advertise the vendor binary: the agent has a shell and would
    # invoke it without the wrapper's disable flags.
    environment.pop("LFB_HARNESS_REAL_BIN", None)
    return environment


def build_harness_run_argv(
    backend_path: Path,
    spec: ContainerHarnessSpec,
    names: ContainerHarnessNames,
    *,
    credential_home: Path,
    cidfile: Path,
    fence_binary: Path | None = None,
) -> tuple[str, ...]:
    """Return argv running the harness on the internal network only."""

    fence = fence_binary if fence_binary is not None else cli_fence_source_path()
    cli = fenced_cli_name(spec)
    argv: list[str] = [
        str(backend_path),
        "run",
        "--rm",
        "--name",
        names.harness_container,
        "--network",
        names.network,
        "--pull=never",
        "--cidfile",
        str(cidfile),
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        str(spec.pids_limit),
        "--memory",
        spec.memory_limit,
        f"--cpus={spec.cpu_limit}",
        "--workdir",
        WORKSPACE_TARGET,
        "--mount",
        f"type=bind,src={spec.workspace},dst={WORKSPACE_TARGET}",
        "--mount",
        f"type=bind,src={credential_home},dst={CREDENTIALS_TARGET},readonly",
        "--mount",
        f"type=bind,src={fence},dst={FENCE_WRAPPER_TARGET},readonly",
        "--mount",
        f"type=bind,src={fence},dst={FENCE_BIN_DIR}/{cli},readonly",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=512m",
        "--tmpfs",
        f"{spec.container_home}:rw,nosuid,nodev,size=64m",
        "--entrypoint",
        FENCE_WRAPPER_TARGET,
    ]
    if spec.read_only_rootfs:
        argv.append("--read-only")
    for name, value in sorted(build_harness_environment(spec, names).items()):
        argv.extend(("--env", f"{name}={value}"))
    argv.append(spec.image)
    argv.extend(spec.harness_argv)
    return tuple(argv)


def stage_credential_home(root: Path, spec: ContainerHarnessSpec) -> Path:
    """Copy declared credentials into a fresh 0700 HOME and return it."""

    home = root / "home"
    home.mkdir(mode=0o700, parents=True, exist_ok=False)
    for credential in spec.credentials:
        if not credential.host_path.is_file():
            raise ContainerHarnessError(
                f"declared credential is not a regular file: "
                f"{credential.home_relative_path}"
            )
        target = home / credential.home_relative_path
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target.write_bytes(credential.host_path.read_bytes())
        target.chmod(0o600)
    return home
