from __future__ import annotations

from datetime import date

from legalforecast.openai_transport import (
    OPENAI_RESPONSES_URL,
    VERCEL_AI_GATEWAY_RESPONSES_URL,
    resolve_openai_transport,
)


def test_sol_uses_openai_only_vercel_route_through_promotion_last_date() -> None:
    route = resolve_openai_transport(
        "gpt-5.6-sol",
        on_date_utc=date(2026, 9, 18),
    )

    assert route.responses_url == VERCEL_AI_GATEWAY_RESPONSES_URL
    assert route.request_model_id == "openai/gpt-5.6-sol"
    assert route.gateway_extra_body() == {
        "providerOptions": {"gateway": {"only": ["openai"]}}
    }


def test_sol_reverts_to_direct_openai_after_promotion() -> None:
    route = resolve_openai_transport(
        "gpt-5.6-sol",
        on_date_utc=date(2026, 9, 19),
    )

    assert route.responses_url == OPENAI_RESPONSES_URL
    assert route.request_model_id == "gpt-5.6-sol"
    assert route.gateway_extra_body() == {}


def test_other_openai_models_never_use_the_temporary_gateway_route() -> None:
    route = resolve_openai_transport(
        "gpt-5.6-terra",
        on_date_utc=date(2026, 8, 26),
    )

    assert route.responses_url == OPENAI_RESPONSES_URL
    assert route.request_model_id == "gpt-5.6-terra"
    assert route.gateway_extra_body() == {}
