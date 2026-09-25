"""Pure launch data for the model-gateway sidecar.

The gateway is deliberately a separate process from the Claude harness.  The
harness receives one per-run capability, while any upstream credential stays
in the gateway process environment. The Docker launch subprocess receives the
credential only in its private environment and passes the variable name (never
the value) to Docker. The gateway source is bind-mounted from the installed
package so the Claude image remains provider-free.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

PROXY_EVIDENCE_DIR = "/var/legalforecast-egress"


class ModelGatewayPlanError(ValueError):
    """Raised when a gateway sidecar launch cannot be made safe."""


def model_gateway_source_path() -> Path:
    """Return the bind-mountable gateway module installed with the harness."""

    path = Path(
        str(
            files("legalforecast.multiharness.container_harness").joinpath(
                "model_gateway.py"
            )
        )
    )
    if not path.is_file():
        raise ModelGatewayPlanError(
            "model_gateway.py is not available as a real file; the sidecar bind-"
            "mount requires a source checkout or unpacked package"
        )
    return path


MODEL_GATEWAY_HOST = "lfb-model-gateway"
MODEL_GATEWAY_PORT = 8080
MODEL_GATEWAY_PROXY_HOST = "lfb-model-egress"
MODEL_GATEWAY_PROXY_PORT = 3128
MODEL_GATEWAY_PROXY_BASE_URL = (
    f"http://{MODEL_GATEWAY_PROXY_HOST}:{MODEL_GATEWAY_PROXY_PORT}"
)
# Retained as a compatibility export for callers that imported the old plan
# constant.  The gateway has no log-based readiness protocol; runtime probes
# its bound socket instead.
MODEL_GATEWAY_READY_MARKER = "lfb-model-gateway-ready"
MODEL_GATEWAY_SOURCE_TARGET = "/opt/legalforecast/model_gateway.py"
MODEL_GATEWAY_PACKAGE_ROOT_TARGET = "/opt/legalforecast/gateway-package"
MODEL_GATEWAY_PACKAGE_TARGET = (
    f"{MODEL_GATEWAY_PACKAGE_ROOT_TARGET}/legalforecast/multiharness/container_harness"
)
MODEL_GATEWAY_MODULE = "legalforecast.multiharness.container_harness.model_gateway"
MODEL_GATEWAY_CONFIG_TARGET = "/etc/legalforecast/model-gateway-policy.json"
MODEL_GATEWAY_PAID_CONFIG_TARGET = "/etc/legalforecast/model-gateway-paid.json"
MODEL_GATEWAY_MODEL_REGISTRY_TARGET = "/etc/legalforecast/model-registry.json"
MODEL_GATEWAY_ENV_TARGET = "/run/legalforecast/model-gateway.env"
MODEL_GATEWAY_EVIDENCE_TARGET = f"{PROXY_EVIDENCE_DIR}/egress-evidence.json"
MODEL_GATEWAY_USAGE_EVIDENCE_TARGET = f"{PROXY_EVIDENCE_DIR}/gateway-usage.json"
MODEL_GATEWAY_CAPABILITY_TOKEN_ENV = "LFB_MODEL_GATEWAY_CAPABILITY_TOKEN"
# This alias avoids breaking an out-of-tree caller while the canonical name
# matches model_gateway.py's actual launch contract.
MODEL_GATEWAY_RUN_CAPABILITY_ENV = MODEL_GATEWAY_CAPABILITY_TOKEN_ENV
MODEL_GATEWAY_UPSTREAM_KEY_ENV = "LFB_MODEL_GATEWAY_UPSTREAM_API_KEY"
MODEL_GATEWAY_PAID_CONFIG_ENV = "LFB_MODEL_GATEWAY_PAID_CONFIG_PATH"
MODEL_GATEWAY_MODEL_REGISTRY_ENV = "LFB_MODEL_GATEWAY_MODEL_REGISTRY_PATH"
MODEL_GATEWAY_REQUEST_ID_ENV = "LFB_MODEL_GATEWAY_REQUEST_ID"
MODEL_GATEWAY_PROTECTED_UPSTREAM_BASE_URL = "https://api.anthropic.com:443"

# These names are projected into the gateway container only in protected paid
# mode. Their values live in the Docker-client environment; no value appears
# in argv or in the harness environment. Endpoint overrides are intentionally
# absent so AWS CLI resolves the region's ordinary DynamoDB endpoint, which is
# then enforced by the relay allowlist.
MODEL_GATEWAY_AUTHORITY_ENV = (
    "GITHUB_ACTIONS",
    "LFB_PROTECTED_TERMINAL_RELEASE",
    "LFB_PROVIDER_AUTHORITY_TABLE",
    "LFB_AWS_REGION",
    "LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256",
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
)
MODEL_GATEWAY_RELAY_ENV = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "NO_PROXY",
    "no_proxy",
)


@dataclass(frozen=True, slots=True)
class ModelGatewayRequest:
    """One fixture or brokered upstream route for a single harness run."""

    upstream_base_url: str
    model_key: str
    run_capability: str
    upstream_api_key: str | None = None
    paid_config_path: Path | None = None
    model_registry_path: Path | None = None
    request_id: str | None = None
    host: str = MODEL_GATEWAY_HOST
    port: int = MODEL_GATEWAY_PORT

    def __post_init__(self) -> None:
        parsed = urlsplit(self.upstream_base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname is None
            or parsed.port is None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ModelGatewayPlanError(
                "model gateway upstream_base_url must be an HTTP(S) origin with an "
                "explicit port"
            )
        if not self.model_key or any(char.isspace() for char in self.model_key):
            raise ModelGatewayPlanError("model gateway model_key must be non-empty")
        if not self.run_capability or any(
            char in self.run_capability for char in "\r\n"
        ):
            raise ModelGatewayPlanError("model gateway run capability is invalid")
        paid_mode = self.paid_config_path is not None
        if not paid_mode and (
            self.upstream_api_key is None
            or any(char in self.upstream_api_key for char in "\r\n")
        ):
            raise ModelGatewayPlanError(
                "model gateway upstream key must be supplied to the sidecar"
            )
        if paid_mode and self.upstream_api_key is not None:
            raise ModelGatewayPlanError(
                "paid gateway upstream key must come from the protected workflow"
            )
        if paid_mode and (
            self.request_id is None
            or not self.request_id
            or any(char in self.request_id for char in "\r\n")
        ):
            raise ModelGatewayPlanError(
                "paid gateway requires a stable per-case request_id"
            )
        if (self.paid_config_path is None) != (self.model_registry_path is None):
            raise ModelGatewayPlanError(
                "paid gateway requires both paid_config_path and model_registry_path"
            )
        for field_name, path in (
            ("paid_config_path", self.paid_config_path),
            ("model_registry_path", self.model_registry_path),
        ):
            if path is not None and (not path.is_absolute() or not path.is_file()):
                raise ModelGatewayPlanError(
                    f"{field_name} must be an absolute regular file"
                )
        if self.host != MODEL_GATEWAY_HOST:
            raise ModelGatewayPlanError(
                f"model gateway host must be {MODEL_GATEWAY_HOST!r}"
            )
        if self.port != MODEL_GATEWAY_PORT:
            raise ModelGatewayPlanError(
                f"model gateway port must be {MODEL_GATEWAY_PORT}"
            )


@dataclass(frozen=True, slots=True)
class ModelGatewayLaunch:
    """Host paths staged for one detached gateway sidecar."""

    source_path: Path | None = None
    config_path: Path | None = None
    package_path: Path | None = None
    paid_config_path: Path | None = None
    model_registry_path: Path | None = None
    host: str = MODEL_GATEWAY_HOST
    port: int = MODEL_GATEWAY_PORT
    python: str = "python3"

    def __post_init__(self) -> None:
        for field_name, path in (("config_path", self.config_path),):
            if path is None:
                raise ModelGatewayPlanError(f"{field_name} is required")
            if not path.is_absolute():
                raise ModelGatewayPlanError(f"{field_name} must be absolute")
            if not path.is_file():
                raise ModelGatewayPlanError(f"{field_name} is not a regular file")
        fixture_mode = self.source_path is not None
        paid_mode = (
            self.paid_config_path is not None or self.model_registry_path is not None
        )
        if fixture_mode == paid_mode:
            raise ModelGatewayPlanError(
                "gateway launch must select exactly one of fixture or paid mode"
            )
        if fixture_mode:
            assert self.source_path is not None
            if not self.source_path.is_absolute() or not self.source_path.is_file():
                raise ModelGatewayPlanError(
                    "source_path must be an absolute regular file"
                )
            if self.package_path is not None:
                if (
                    not self.package_path.is_absolute()
                    or not self.package_path.is_dir()
                ):
                    raise ModelGatewayPlanError(
                        "package_path must be an absolute directory"
                    )
        else:
            if self.package_path is not None:
                raise ModelGatewayPlanError(
                    "paid gateway must use its installed package"
                )
            for field_name, path in (
                ("paid_config_path", self.paid_config_path),
                ("model_registry_path", self.model_registry_path),
            ):
                if path is None:
                    raise ModelGatewayPlanError(
                        "paid gateway requires config and registry paths"
                    )
                if not path.is_absolute() or not path.is_file():
                    raise ModelGatewayPlanError(
                        f"{field_name} must be an absolute regular file"
                    )
        if self.host != MODEL_GATEWAY_HOST or self.port != MODEL_GATEWAY_PORT:
            raise ModelGatewayPlanError("model gateway launch identity is invalid")
        if not self.python or any(char.isspace() for char in self.python):
            raise ModelGatewayPlanError("model gateway python executable is invalid")


class _HarnessNames(Protocol):
    @property
    def network(self) -> str: ...

    @property
    def model_gateway_container(self) -> str: ...


class _HarnessSpec(Protocol):
    def resolved_proxy_image(self) -> str: ...


def build_model_gateway_run_argv(
    backend_path: Path,
    spec: _HarnessSpec,
    names: _HarnessNames,
    launch: ModelGatewayLaunch,
    *,
    evidence_directory: Path,
) -> tuple[str, ...]:
    """Return a hardened detached gateway container command.

    The gateway starts on the harness's ``--internal`` network.  Runtime code
    connects it to the per-run fixture/provider network only after creation;
    the harness itself is never connected to that network.
    """

    if launch.config_path is None:
        raise ModelGatewayPlanError("gateway launch config is required")
    paid_mode = launch.paid_config_path is not None
    argv: list[str] = [
        str(backend_path),
        "run",
        "--detach",
        "--name",
        names.model_gateway_container,
        "--network",
        names.network,
        "--network-alias",
        MODEL_GATEWAY_HOST,
        "--user",
        "0:0",
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
        f"type=bind,src={launch.config_path},dst={MODEL_GATEWAY_CONFIG_TARGET},readonly",
        "--mount",
        f"type=bind,src={evidence_directory},dst={PROXY_EVIDENCE_DIR}",
        # Values are supplied through the subprocess environment at launch;
        # only variable names appear in argv and the container definition.
        "--env",
        MODEL_GATEWAY_CAPABILITY_TOKEN_ENV,
        "--env",
        MODEL_GATEWAY_UPSTREAM_KEY_ENV,
        "--entrypoint",
        launch.python,
        spec.resolved_proxy_image(),
        "-m",
        MODEL_GATEWAY_MODULE,
        "--config",
        MODEL_GATEWAY_CONFIG_TARGET,
    ]
    if paid_mode:
        assert launch.paid_config_path is not None
        assert launch.model_registry_path is not None
        # The paid image contains the complete installed package. Only its
        # immutable paid descriptor and registry are mounted; staged fixture
        # source and PYTHONPATH would shadow protected modules.
        insertion = argv.index("--entrypoint")
        argv[insertion:insertion] = [
            "--mount",
            f"type=bind,src={launch.paid_config_path},dst={MODEL_GATEWAY_PAID_CONFIG_TARGET},readonly",
            "--mount",
            f"type=bind,src={launch.model_registry_path},dst={MODEL_GATEWAY_MODEL_REGISTRY_TARGET},readonly",
            "--env",
            f"{MODEL_GATEWAY_PAID_CONFIG_ENV}={MODEL_GATEWAY_PAID_CONFIG_TARGET}",
            "--env",
            f"{MODEL_GATEWAY_MODEL_REGISTRY_ENV}={MODEL_GATEWAY_MODEL_REGISTRY_TARGET}",
            "--env",
            MODEL_GATEWAY_REQUEST_ID_ENV,
        ]
        for name in MODEL_GATEWAY_AUTHORITY_ENV + MODEL_GATEWAY_RELAY_ENV:
            argv[insertion:insertion] = ["--env", name]
    else:
        assert launch.source_path is not None
        package_path = launch.package_path or launch.source_path.parent
        insertion = argv.index("--mount", argv.index("--mount") + 1)
        argv[insertion:insertion] = [
            "--mount",
            f"type=bind,src={launch.source_path},dst={MODEL_GATEWAY_SOURCE_TARGET},readonly",
            "--mount",
            f"type=bind,src={package_path},dst={MODEL_GATEWAY_PACKAGE_TARGET},readonly",
        ]
        insertion = argv.index("--entrypoint")
        argv[insertion:insertion] = [
            "--env",
            f"PYTHONPATH={MODEL_GATEWAY_PACKAGE_ROOT_TARGET}",
        ]
    return tuple(argv)


def model_gateway_environment_names() -> tuple[str, str]:
    """Return the only two capability-bearing variables accepted by the sidecar."""

    return MODEL_GATEWAY_CAPABILITY_TOKEN_ENV, MODEL_GATEWAY_UPSTREAM_KEY_ENV


__all__ = [
    "MODEL_GATEWAY_AUTHORITY_ENV",
    "MODEL_GATEWAY_CAPABILITY_TOKEN_ENV",
    "MODEL_GATEWAY_CONFIG_TARGET",
    "MODEL_GATEWAY_ENV_TARGET",
    "MODEL_GATEWAY_EVIDENCE_TARGET",
    "MODEL_GATEWAY_HOST",
    "MODEL_GATEWAY_MODEL_REGISTRY_ENV",
    "MODEL_GATEWAY_MODEL_REGISTRY_TARGET",
    "MODEL_GATEWAY_MODULE",
    "MODEL_GATEWAY_PACKAGE_ROOT_TARGET",
    "MODEL_GATEWAY_PACKAGE_TARGET",
    "MODEL_GATEWAY_PAID_CONFIG_ENV",
    "MODEL_GATEWAY_PAID_CONFIG_TARGET",
    "MODEL_GATEWAY_PORT",
    "MODEL_GATEWAY_PROTECTED_UPSTREAM_BASE_URL",
    "MODEL_GATEWAY_PROXY_BASE_URL",
    "MODEL_GATEWAY_PROXY_HOST",
    "MODEL_GATEWAY_PROXY_PORT",
    "MODEL_GATEWAY_READY_MARKER",
    "MODEL_GATEWAY_RELAY_ENV",
    "MODEL_GATEWAY_REQUEST_ID_ENV",
    "MODEL_GATEWAY_RUN_CAPABILITY_ENV",
    "MODEL_GATEWAY_SOURCE_TARGET",
    "MODEL_GATEWAY_UPSTREAM_KEY_ENV",
    "MODEL_GATEWAY_USAGE_EVIDENCE_TARGET",
    "ModelGatewayLaunch",
    "ModelGatewayPlanError",
    "ModelGatewayRequest",
    "build_model_gateway_run_argv",
    "model_gateway_environment_names",
    "model_gateway_source_path",
]
