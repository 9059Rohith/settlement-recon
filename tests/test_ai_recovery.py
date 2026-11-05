"""Controlled provider faults must not fabricate grounded success or leak secrets."""

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from settlement_recon.api import create_app
from settlement_recon.domain import FileArchive, Reconciler


def provider_client(post):
    class Provider:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    Provider.post = post
    return Provider


@pytest.mark.parametrize("fault", [500, 502, 503, 504, "timeout"])
def test_readonly_agent_recovers_one_transient_fault(tmp_path, monkeypatch, fault):
    from settlement_recon import workspace

    monkeypatch.setenv("GEMINI_API_KEY", "unit-recovery-key-never-sent")
    monkeypatch.setattr(workspace.time, "sleep", lambda _: None)
    calls = []

    def post(_client, url, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            if fault == "timeout":
                raise httpx.ReadTimeout("secret-provider-body")
            return httpx.Response(fault, request=httpx.Request("POST", url))
        message = {"role": "assistant", "content": "The observed service has no live bank feed."}
        if len(calls) == 2:
            message = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "read",
                        "type": "function",
                        "function": {"name": "service_status", "arguments": "{}"},
                    }
                ],
            }
        return httpx.Response(
            200, json={"choices": [{"message": message}]}, request=httpx.Request("POST", url)
        )

    app = create_app(
        Reconciler(f"sqlite:///{tmp_path / 'db'}", FileArchive(tmp_path / "raw")),
        "unit-test-token-000000000000000000000",
    )
    with TestClient(app) as client:
        monkeypatch.setattr(workspace.httpx, "Client", provider_client(post))
        response = client.post(
            "/workspace/api/agent/demo", json={"question": "Inspect public service status"}
        )
    assert response.status_code == 200, response.text
    assert response.json()["tools"][0]["name"] == "service_status"
    assert len(calls) == 3
    assert all(call["json"]["reasoning_effort"] == "minimal" for call in calls)
    assert all(call["timeout"] <= 20 for call in calls)


@pytest.mark.parametrize("status,expected,attempts", [(503, 503, 2), (400, 502, 1)])
def test_provider_failures_are_bounded_and_redacted(
    tmp_path, monkeypatch, caplog, status, expected, attempts
):
    from settlement_recon import workspace

    monkeypatch.setenv("GEMINI_API_KEY", "unit-recovery-key-never-sent")
    monkeypatch.setattr(workspace.time, "sleep", lambda _: None)
    calls = []

    def post(_client, url, **kwargs):
        calls.append(1)
        return httpx.Response(
            status, text="secret-provider-body", request=httpx.Request("POST", url)
        )

    app = create_app(
        Reconciler(f"sqlite:///{tmp_path / 'db'}", FileArchive(tmp_path / "raw")),
        "unit-test-token-000000000000000000000",
    )
    with TestClient(app) as client:
        monkeypatch.setattr(workspace.httpx, "Client", provider_client(post))
        response = client.post(
            "/workspace/api/agent/demo", json={"question": "Inspect public service status"}
        )
    assert response.status_code == expected
    assert len(calls) == attempts
    if expected == 503:
        assert response.headers["retry-after"] == "60"
    assert "status=" + str(status) in caplog.text
    assert "secret-provider-body" not in caplog.text + response.text
    assert "unit-recovery-key-never-sent" not in caplog.text + response.text


def test_expired_model_budget_never_sends_request():
    from settlement_recon.workspace import model_request

    with pytest.raises(HTTPException) as error:
        model_request(None, {}, {}, {"deadline": 0, "requests": 0, "retry_available": True})
    assert error.value.status_code == 503


@pytest.mark.parametrize("delay", ["1", "120", "Wed, 01 Jan 2031 00:00:00 GMT"])
def test_provider_retry_after_is_not_ignored(monkeypatch, delay):
    from settlement_recon import workspace

    calls = []

    class Client:
        def post(self, url, **kwargs):
            calls.append(1)
            return httpx.Response(
                503, headers={"Retry-After": delay}, request=httpx.Request("POST", url)
            )

    with pytest.raises(HTTPException) as error:
        workspace.model_request(
            Client(),
            {"endpoint": "https://example.invalid", "key": "unit-only"},
            {},
            {"deadline": workspace.time.monotonic() + 60, "requests": 0, "retry_available": True},
        )
    assert error.value.status_code == 503
    assert error.value.headers["Retry-After"] == delay
    assert len(calls) == 1
