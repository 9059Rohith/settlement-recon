"""Workspace boundaries, exact reference conversion and captured-provider integration."""

from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

from settlement_recon.api import create_app
from settlement_recon.domain import FileArchive, Reconciler
from settlement_recon.workspace import PAGES, convert, validate_rates

TOKEN = "workspace-test-token-only-00000000000000"
READER = "workspace-read-token-only-0000000000000"


@pytest.fixture
def app(tmp_path):
    return create_app(
        Reconciler(f"sqlite:///{tmp_path / 'workspace.db'}", FileArchive(tmp_path / "raw")),
        TOKEN,
        READER,
    )


@pytest.mark.parametrize("page", PAGES)
def test_pages_have_distinct_titles_and_all_navigation(app, page):
    with TestClient(app) as client:
        result = client.get("/workspace/" + page)
        assert result.status_code == 200
        assert f"<h1>{PAGES[page][0]}</h1>" in result.text
        for target in PAGES:
            assert f'href="/workspace/{target}"' in result.text
        policy = result.headers["content-security-policy"]
        assert "connect-src 'self'" in policy
        assert "script-src 'self'" in policy


def test_workspace_cannot_mutate_without_writer(app, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(app) as client:
        assert client.get("/workspace/api/rates").json()["status"] == "not_connected"
        assert client.post("/workspace/api/rates/sync").status_code == 401
        assert (
            client.post(
                "/workspace/api/rates/sync", headers={"Authorization": f"Bearer {READER}"}
            ).status_code
            == 403
        )
        assert (
            client.post("/workspace/api/agent", json={"question": "Inspect rates"}).status_code
            == 401
        )
        assert (
            client.post(
                "/workspace/api/agent",
                json={"question": "Inspect rates"},
                headers={"Authorization": f"Bearer {TOKEN}"},
            ).status_code
            == 503
        )
        assert client.get("/workspace/not-a-page").status_code == 404
        assert "demo-matched" not in client.get("/").text


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "1000000000001", "abc"])
def test_conversion_rejects_invalid_amounts(value):
    with pytest.raises(ValueError):
        convert({"date": "2026-10-30", "rates": {"USD": 1.1}}, value, "EUR", "USD")


def test_cross_rate_uses_exact_decimals():
    result = convert(
        {"date": "2026-10-30", "rates": {"USD": "1.25", "GBP": "0.8"}}, "10", "USD", "GBP"
    )
    assert Decimal(result["result"]) == Decimal("6.4")


def test_operator_workspace_excludes_legacy_verification_records(app):
    import json

    for source, identity in [
        ("release-check", "legacy-check"),
        ("operator:ledger", "actual-input"),
    ]:
        app.state.service.ingest(
            "payments",
            source,
            json.dumps(
                {"payments": [{"payment_id": identity, "currency": "USD", "amount": "12.50"}]}
            ).encode(),
        )
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        for path in ["payments", "reconciliation"]:
            response = client.get("/workspace/api/" + path, headers=headers)
            assert response.status_code == 200
            assert [row["payment_id"] for row in response.json()] == ["actual-input"]
        receipts = client.get("/workspace/api/batches", headers=headers).json()
        assert len(receipts) == 1
        assert receipts[0]["source"] == "operator:ledger"


def test_provider_payload_validation():
    with pytest.raises(ValueError):
        validate_rates({"base": "USD", "rates": {}})
    with pytest.raises(ValueError):
        validate_rates({"base": "EUR", "date": "2026-10-30", "rates": {"USD": "NaN"}})


def test_gemini_roundtrip_preserves_provider_metadata_and_hides_key(app, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-placeholder-not-a-real-key")
    requests = []
    signature = {"google": {"thought_signature": "opaque-test-signature"}}

    class Provider:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            import copy

            requests.append(copy.deepcopy(kwargs["json"]))
            assert url == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            message = {
                "role": "assistant",
                "content": "The evidence reports no connected bank feed.",
            }
            if len(requests) == 1:
                message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "one",
                            "type": "function",
                            "extra_content": signature,
                            "function": {"name": "service_status", "arguments": "{}"},
                        }
                    ],
                }
            return httpx.Response(
                200, json={"choices": [{"message": message}]}, request=httpx.Request("POST", url)
            )

    with TestClient(app) as client:
        status = client.get("/workspace/api/status")
        assert status.json()["ai_model"] == "gemini-3.5-flash-lite"
        assert "unit-test-placeholder" not in status.text
        monkeypatch.setattr("settlement_recon.workspace.httpx.Client", Provider)
        result = client.post(
            "/workspace/api/agent",
            json={"question": "Inspect the service status"},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        assert result.status_code == 200
        assert result.json()["tools"][0]["name"] == "service_status"
        assert requests[0]["tool_choice"] == "required"
        assert requests[1]["messages"][2]["tool_calls"][0]["extra_content"] == signature
        assert "unit-test-placeholder" not in result.text


def test_gemini_quota_failure_is_explicit_without_paid_fallback(app, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-placeholder-not-a-real-key")

    class Limited:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            return httpx.Response(429, json={"error": "quota"}, request=httpx.Request("POST", url))

    with TestClient(app) as client:
        monkeypatch.setattr("settlement_recon.workspace.httpx.Client", Limited)
        response = client.post(
            "/workspace/api/agent",
            json={"question": "Inspect rates"},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        assert response.status_code == 429
        assert "No paid fallback" in response.json()["detail"]


def test_capture_persists_provenance_and_reuses_digest(app, monkeypatch):
    # Controlled provider response is a test fixture, never a runtime fallback.
    class Provider:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            return httpx.Response(
                200,
                json={"base": "EUR", "date": "2026-10-30", "rates": {"USD": 1.1}},
                request=httpx.Request("GET", url),
            )

    with TestClient(app) as client:
        monkeypatch.setattr("settlement_recon.workspace.httpx.Client", Provider)
        result = client.post(
            "/workspace/api/rates/sync", headers={"Authorization": f"Bearer {TOKEN}"}
        )
        assert result.status_code == 200
        assert len(result.json()["digest"]) == 64
        assert result.json()["observation"]["date"] == "2026-10-30"
        assert client.get("/workspace/api/rates").json()["digest"] == result.json()["digest"]
        assert (
            client.post(
                "/workspace/api/rates/sync", headers={"Authorization": f"Bearer {TOKEN}"}
            ).status_code
            == 429
        )
        assert (
            client.post(
                "/workspace/api/convert", json={"amount": "10", "source": "EUR", "target": "USD"}
            ).json()["result"]
            == "11.0"
        )
