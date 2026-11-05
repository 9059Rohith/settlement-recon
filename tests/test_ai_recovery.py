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
@pytest.mark.parametrize("failures", [1, 2])
def test_readonly_agent_recovers_transient_faults(tmp_path, monkeypatch, fault, failures):
    from settlement_recon import workspace

    monkeypatch.setenv("GEMINI_API_KEY", "unit-recovery-key-never-sent")
    monkeypatch.setattr(workspace.time, "sleep", lambda _: None)
    calls = []

    def post(_client, url, **kwargs):
        calls.append(kwargs)
        if len(calls) <= failures:
            if fault == "timeout":
                raise httpx.ReadTimeout("secret-provider-body")
            return httpx.Response(fault, request=httpx.Request("POST", url))
        message = {"role": "assistant", "content": "The observed service has no live bank feed."}
        if len(calls) == failures + 1:
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
    assert len(calls) == failures + 2
    assert all(call["json"]["reasoning_effort"] == "minimal" for call in calls)
    assert all(call["timeout"] <= 20 for call in calls)


@pytest.mark.parametrize("status,expected,attempts", [(503, 503, 3), (400, 502, 1)])
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


def test_retry_capacity_is_shared_across_model_turns(monkeypatch):
    from settlement_recon import workspace

    statuses = iter([503, 200, 503, 200, 503])
    sent, waits = [], []
    monkeypatch.setattr(workspace.time, "sleep", waits.append)

    def handle(request):
        sent.append(request)
        return httpx.Response(next(statuses), json={"ok": True})

    budget = {"deadline": workspace.time.monotonic() + 60, "requests": 0, "retry_available": True}
    provider = {"endpoint": "https://example.invalid", "key": "not-a-real-key"}
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert workspace.model_request(client, provider, {}, budget).status_code == 200
        assert workspace.model_request(client, provider, {}, budget).status_code == 200
        with pytest.raises(HTTPException) as error:
            workspace.model_request(client, provider, {}, budget)
    assert error.value.status_code == 503
    assert len(sent) == 5
    assert len(waits) == 2
    assert 1 <= waits[0] <= 1.1
    assert 2 <= waits[1] <= 2.1


def test_short_deadline_does_not_sleep_and_retry(monkeypatch):
    from settlement_recon import workspace

    waits, sent = [], []
    monkeypatch.setattr(workspace.time, "sleep", waits.append)

    def handle(request):
        sent.append(request)
        return httpx.Response(503)

    budget = {"deadline": workspace.time.monotonic() + 0.5, "requests": 0, "retry_available": True}
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(HTTPException) as error:
            workspace.model_request(
                client, {"endpoint": "https://example.invalid", "key": "x"}, {}, budget
            )
    assert error.value.status_code == 503
    assert len(sent) == 1
    assert not waits


def test_late_provider_success_cannot_escape_deadline(monkeypatch):
    from settlement_recon import workspace

    clock = [0.0]
    monkeypatch.setattr(workspace.time, "monotonic", lambda: clock[0])

    def handle(request):
        clock[0] = 61.0
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(HTTPException) as error:
            workspace.model_request(
                client,
                {"endpoint": "https://example.invalid", "key": "x"},
                {},
                {"deadline": 60.0, "requests": 0, "retry_available": True},
            )
    assert error.value.status_code == 503
