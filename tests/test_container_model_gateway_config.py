from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import cast

import pytest
from legalforecast.multiharness.container_harness.model_gateway import (
    CAPABILITY_TOKEN_ENV,
    UPSTREAM_API_KEY_ENV,
    UPSTREAM_KEY_FILE_ENV,
    ModelGatewayError,
    load_model_gateway_launch_config,
)


class _FakeUpstream:
    def __init__(self, *, body: bytes) -> None:
        self._body = body
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                self.rfile.read(length)
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(owner._body)))
                self.end_headers()
                self.wfile.write(owner._body)

            def log_message(self, format: str, *args: object) -> None:
                del format, args

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self) -> str:
        host, port = cast(tuple[str, int], self.server.server_address)
        return f"http://{host}:{port}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@contextmanager
def _upstream(*, body: bytes) -> Generator[_FakeUpstream]:
    upstream = _FakeUpstream(body=body)
    try:
        yield upstream
    finally:
        upstream.close()


def _success_response() -> bytes:
    return json.dumps({"ok": True}, separators=(",", ":")).encode("utf-8")


def _launch_policy_document(
    upstream: _FakeUpstream,
    *,
    evidence_path: Path = Path("/run/legalforecast/model-gateway/usage.json"),
    **overrides: object,
) -> dict[str, object]:
    value: dict[str, object] = {
        "bind_host": "127.0.0.1",
        "bind_port": 3129,
        "upstream_base_url": upstream.base_url,
        "allowed_models": ["claude-fixture"],
        "allowed_ingress_hosts": ["127.0.0.1"],
        "usage_evidence_path": str(evidence_path),
    }
    value.update(overrides)
    return value


def _write_owner_only_json(path: Path, value: object, mode: int = 0o600) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(mode)


def test_sidecar_loader_keeps_credentials_out_of_policy_file(tmp_path: Path) -> None:
    with _upstream(body=_success_response()) as upstream:
        config_path = tmp_path / "policy.json"
        _write_owner_only_json(config_path, _launch_policy_document(upstream))

        launch = load_model_gateway_launch_config(
            config_path,
            environment={
                UPSTREAM_API_KEY_ENV: "provider-sentinel",
                CAPABILITY_TOKEN_ENV: "run-capability-sentinel",
            },
        )

        assert launch.bind_host == "127.0.0.1"
        assert launch.bind_port == 3129
        assert launch.policy.upstream_api_key == "provider-sentinel"
        assert launch.policy.capability_token == "run-capability-sentinel"
        assert launch.usage_evidence_path == Path(
            "/run/legalforecast/model-gateway/usage.json"
        )


def test_sidecar_loader_accepts_owner_only_key_file(tmp_path: Path) -> None:
    with _upstream(body=_success_response()) as upstream:
        config_path = tmp_path / "policy.json"
        key_path = tmp_path / "upstream.key"
        _write_owner_only_json(config_path, _launch_policy_document(upstream), 0o400)
        key_path.write_text("provider-file-sentinel\n", encoding="utf-8")
        key_path.chmod(0o400)

        launch = load_model_gateway_launch_config(
            config_path,
            environment={
                UPSTREAM_KEY_FILE_ENV: str(key_path),
                CAPABILITY_TOKEN_ENV: "run-capability-sentinel",
            },
        )

        assert launch.policy.upstream_api_key == "provider-file-sentinel"


def test_sidecar_loader_rejects_permissive_or_credential_bearing_config(
    tmp_path: Path,
) -> None:
    with _upstream(body=_success_response()) as upstream:
        config_path = tmp_path / "policy.json"
        document = _launch_policy_document(
            upstream,
            upstream_api_key="must-not-be-filed",
        )
        _write_owner_only_json(config_path, document)
        with pytest.raises(ModelGatewayError, match="must not contain credentials"):
            load_model_gateway_launch_config(
                config_path,
                environment={
                    UPSTREAM_API_KEY_ENV: "provider-sentinel",
                    CAPABILITY_TOKEN_ENV: "run-capability-sentinel",
                },
            )

        _write_owner_only_json(config_path, _launch_policy_document(upstream), 0o644)
        with pytest.raises(ModelGatewayError, match="owner-only"):
            load_model_gateway_launch_config(
                config_path,
                environment={
                    UPSTREAM_API_KEY_ENV: "provider-sentinel",
                    CAPABILITY_TOKEN_ENV: "run-capability-sentinel",
                },
            )


def test_sidecar_loader_rejects_multiple_upstream_key_sources(tmp_path: Path) -> None:
    with _upstream(body=_success_response()) as upstream:
        config_path = tmp_path / "policy.json"
        key_path = tmp_path / "upstream.key"
        _write_owner_only_json(config_path, _launch_policy_document(upstream))
        key_path.write_text("provider-file-sentinel", encoding="utf-8")
        key_path.chmod(0o400)

        with pytest.raises(ModelGatewayError, match="exactly one"):
            load_model_gateway_launch_config(
                config_path,
                environment={
                    UPSTREAM_API_KEY_ENV: "provider-sentinel",
                    UPSTREAM_KEY_FILE_ENV: str(key_path),
                    CAPABILITY_TOKEN_ENV: "run-capability-sentinel",
                },
            )
