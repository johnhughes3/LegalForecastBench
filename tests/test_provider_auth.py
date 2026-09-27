"""Network-free SDK exchange and managed-run authentication regressions."""

from __future__ import annotations

import asyncio
import json
import traceback
from typing import Any

import httpx
import httpx2
import pytest
from legalforecast.runner.ledger import RunValidationError
from legalforecast.runner.managed_receipt import add_managed_cost_evidence
from legalforecast.runner.provider_auth import select_provider_authentication


def _environment(provider: str) -> dict[str, str]:
    prefix = f"LEGALFORECAST_{provider.upper()}"
    return {
        f"{prefix}_AUTH_MODE": "workload_identity",
        f"{prefix}_WIF_AUDIENCE": "benchmark-audience",
        f"{prefix}_WIF_PROVIDER_ID": "provider-id",
        f"{prefix}_WIF_SERVICE_ACCOUNT_ID": "service-account-id",
        f"{prefix}_WIF_ORGANIZATION_ID": "organization-id",
        f"{prefix}_WIF_WORKSPACE_ID": "workspace-id",
        "ACTIONS_ID_TOKEN_REQUEST_URL": (
            "https://run.actions.githubusercontent.com/token?audience=old&job=1"
        ),
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "secret-github-credential",
        "OPENAI_API_KEY": "secret-openai-legacy",
        "ANTHROPIC_API_KEY": "secret-anthropic-legacy",
    }


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_sdk_exchanges_refreshes_and_uses_only_bearer(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    # Exercise the installed SDK, not an imitation exchange implementation.
    values = _environment(provider)
    monkeypatch.setenv("OPENAI_API_KEY", values["OPENAI_API_KEY"])
    monkeypatch.setenv("ANTHROPIC_API_KEY", values["ANTHROPIC_API_KEY"])
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "secret-other-bearer")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://untrusted.invalid")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://untrusted.invalid")
    monkeypatch.delenv("OPENAI_CUSTOM_HEADERS", raising=False)
    monkeypatch.delenv("ANTHROPIC_CUSTOM_HEADERS", raising=False)
    auth = select_provider_authentication(provider, values)
    requests: list[httpx2.Request] = []
    exchanges: list[dict[str, Any]] = []
    assertions: list[str] = []

    def github_get(_self: object, url: str, **kwargs: Any) -> httpx.Response:
        request = httpx.Request("GET", url, headers=kwargs["headers"])
        assert request.url.params["audience"] == "benchmark-audience"
        assert request.url.params["job"] == "1"
        assert request.headers["Authorization"] == "Bearer secret-github-credential"
        assertions.append(f"secret-assertion-{len(assertions)}")
        return httpx.Response(200, json={"value": assertions[-1]}, request=request)

    def exchange(_self: object, url: str, **kwargs: Any) -> httpx2.Response:
        assert url in (
            "https://auth.openai.com/oauth/token",
            "https://api.anthropic.com/v1/oauth/token",
        )
        body = kwargs.get("json") or json.loads(kwargs["content"])
        exchanges.append(body)
        assert body["service_account_id"] == "service-account-id"
        if provider == "openai":
            assert body["subject_token"] == assertions[-1]
            assert body["subject_token_type"] == "urn:ietf:params:oauth:token-type:jwt"
            assert body["identity_provider_id"] == "provider-id"
        else:
            assert body["assertion"] == assertions[-1]
            assert body["federation_rule_id"] == "provider-id"
            assert body["organization_id"] == "organization-id"
            assert body["workspace_id"] == "workspace-id"
        return httpx2.Response(
            200,
            json={
                "access_token": f"secret-access-{len(exchanges)}",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            request=httpx2.Request("POST", url),
        )

    async def send(
        _self: object, request: httpx2.Request, **_kwargs: Any
    ) -> httpx2.Response:
        requests.append(request)
        assert request.url.host in {"api.openai.com", "api.anthropic.com"}
        assert (
            request.headers["Authorization"] == f"Bearer secret-access-{len(exchanges)}"
        )
        assert "x-api-key" not in request.headers
        if provider == "openai":
            body = {
                "id": "resp_test",
                "object": "response",
                "created_at": 1,
                "model": "test-model",
                "output": [],
                "status": "completed",
            }
        else:
            body = {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "test-model",
                "content": [],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        return httpx2.Response(200, json=body, request=request)

    monkeypatch.setattr(httpx.Client, "get", github_get)
    monkeypatch.setattr(httpx2.Client, "post", exchange)
    monkeypatch.setattr(httpx2.AsyncClient, "_send_single_request", send)

    # The SDK reads custom headers during construction, separately from its
    # credential options. Even an override introduced after selection must be
    # rejected before it can suppress token exchange and send a static bearer.
    header_variable = f"{provider.upper()}_CUSTOM_HEADERS"
    monkeypatch.setenv(header_variable, "Authorization: Bearer secret-header-override")
    with pytest.raises(RunValidationError) as refused:
        if provider == "openai":
            auth.openai_client()
        else:
            auth.anthropic_client()
    assert "secret-" not in "".join(traceback.format_exception(refused.value))
    assert requests == exchanges == assertions == []
    monkeypatch.delenv(header_variable)

    async def run() -> None:
        if provider == "openai":
            async with auth.openai_client() as client:
                await client.responses.create(model="test-model", input="test")
                await client.responses.create(model="test-model", input="test")
                assert len(exchanges) == 1
                client._workload_identity_auth._cached_token_expires_at_monotonic = 0
                await client.responses.create(model="test-model", input="test")
        else:
            async with auth.anthropic_client() as client:
                for _ in range(2):
                    await client.messages.create(
                        model="test-model",
                        max_tokens=1,
                        messages=[{"role": "user", "content": "test"}],
                    )
                assert len(exchanges) == 1
                from anthropic.lib.credentials import AccessToken

                client._token_cache._cached = AccessToken("expired", 0)
                await client.messages.create(
                    model="test-model",
                    max_tokens=1,
                    messages=[{"role": "user", "content": "test"}],
                )

    asyncio.run(run())
    assert len(requests) == 3
    assert len(exchanges) == len(assertions) == 2
    assert "secret-" not in repr(auth)
    assert "secret-" not in json.dumps(auth.provenance())


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_failed_github_identity_does_not_fall_back_or_leak(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    auth = select_provider_authentication(provider, _environment(provider))

    def failure(_self: object, url: str, **_kwargs: object) -> httpx.Response:
        return httpx.Response(
            403, text="secret-assertion", request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(httpx.Client, "get", failure)
    with pytest.raises(RunValidationError) as failure_info:
        auth.subject_token()
    assert "secret-" not in "".join(traceback.format_exception(failure_info.value))


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_missing_federation_configuration_does_not_use_present_api_key(
    provider: str,
) -> None:
    values = _environment(provider)
    del values[f"LEGALFORECAST_{provider.upper()}_WIF_AUDIENCE"]
    with pytest.raises(RunValidationError, match="WIF_AUDIENCE is required"):
        select_provider_authentication(provider, values)


def test_explicit_static_selection_is_provider_isolated() -> None:
    values = _environment("openai")
    values["LEGALFORECAST_OPENAI_AUTH_MODE"] = "api_key"
    selected = select_provider_authentication("openai", values)
    assert selected.api_key.get_secret_value() == "secret-openai-legacy"
    assert selected.mode == "api_key"
    assert select_provider_authentication("anthropic", values).mode == "api_key"
    with pytest.raises(RunValidationError, match="GEMINI_API_KEY"):
        select_provider_authentication("google", values)


def test_authentication_is_projected_into_receipt_without_credentials() -> None:
    auth = select_provider_authentication("openai", _environment("openai"))
    receipt: dict[str, object] = {"usage": {"estimated_cost_microusd": 100}}
    add_managed_cost_evidence(
        receipt,
        {
            "cost_basis": "registry_estimate",
            "cost_method": "test",
            "rate_provenance": "test",
            "service_tier": "default",
            **auth.provenance(),
        },
    )
    assert receipt["authentication"] == {
        "mode": "workload_identity",
        "provider": "openai",
        "endpoint": "direct",
        "issuer": "https://token.actions.githubusercontent.com",
    }
    assert "secret-" not in json.dumps(receipt)
    values = _environment("google")
    values["LEGALFORECAST_GOOGLE_AUTH_MODE"] = "workload_identity"
    with pytest.raises(RunValidationError, match="unsupported"):
        select_provider_authentication("google", values)


@pytest.mark.parametrize(
    "endpoint",
    ["https://evil.invalid/token", "http://run.actions.githubusercontent.com/token"],
)
def test_rejects_non_github_identity_endpoint(endpoint: str) -> None:
    values = _environment("openai")
    values["ACTIONS_ID_TOKEN_REQUEST_URL"] = endpoint
    with pytest.raises(RunValidationError, match="invalid GitHub"):
        select_provider_authentication("openai", values)


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
@pytest.mark.parametrize("source", ["supplied", "ambient"])
def test_workload_identity_rejects_custom_auth_headers(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    source: str,
) -> None:
    values = _environment(provider)
    header_variable = f"{provider.upper()}_CUSTOM_HEADERS"
    monkeypatch.delenv(header_variable, raising=False)
    if source == "supplied":
        values[header_variable] = "Authorization: Bearer secret-header-override"
    else:
        monkeypatch.setenv(
            header_variable, "Authorization: Bearer secret-header-override"
        )
    with pytest.raises(RunValidationError, match=r"custom .* headers") as refused:
        select_provider_authentication(provider, values)
    assert "secret-" not in "".join(traceback.format_exception(refused.value))


@pytest.mark.parametrize(
    "token,expires_in", [("", 3600), ("token", -1), ("token", 0), (42, 3600)]
)
def test_anthropic_rejects_unusable_exchange_tokens(
    monkeypatch: pytest.MonkeyPatch, token: object, expires_in: int
) -> None:
    monkeypatch.setattr(
        "legalforecast.runner.provider_auth.ProviderAuthentication.subject_token",
        lambda _self: "secret-assertion",
    )
    monkeypatch.setattr(
        httpx2.Client,
        "post",
        lambda _self, url, **_kw: httpx2.Response(
            200,
            json={"access_token": token, "expires_in": expires_in},
            request=httpx2.Request("POST", url),
        ),
    )
    client = select_provider_authentication(
        "anthropic", _environment("anthropic")
    ).anthropic_client()
    try:
        with pytest.raises(RunValidationError, match="exchange failed"):
            client.credentials()
    finally:
        asyncio.run(client.close())


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"access_token": "token", "expires_in": "invalid"},
        {"access_token": "token", "expires_in": -1},
        {"access_token": "token", "expires_in": 0},
    ],
)
def test_openai_rejects_unusable_exchange_tokens_without_inference(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]
) -> None:
    monkeypatch.setattr(
        "legalforecast.runner.provider_auth.ProviderAuthentication.subject_token",
        lambda _self: "secret-assertion",
    )
    monkeypatch.setattr(
        httpx2.Client,
        "post",
        lambda _self, url, **_kw: httpx2.Response(
            200, json=payload, request=httpx2.Request("POST", url)
        ),
    )

    async def refuse_inference(*_args: object, **_kwargs: object) -> None:
        pytest.fail("an unusable exchanged token must not reach inference")

    monkeypatch.setattr(httpx2.AsyncClient, "_send_single_request", refuse_inference)

    async def run() -> None:
        from openai import OpenAIError

        auth = select_provider_authentication("openai", _environment("openai"))
        async with auth.openai_client() as client:
            with pytest.raises((OpenAIError, RuntimeError)):
                await client.responses.create(model="test-model", input="test")

    asyncio.run(run())
