"""Public recruiter execution is bounded, persistent and isolated from private APIs."""

from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from starlette.requests import Request

from settlement_recon.api import create_app
from settlement_recon.domain import FileArchive, Reconciler

TOKEN = "public-demo-tests-only-secret-000000000000"


def test_anonymous_recruiter_can_use_real_tool_loop(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-unit-test-key")
    app = create_app(
        Reconciler(f"sqlite:///{tmp_path / 'db'}", FileArchive(tmp_path / "raw")), TOKEN
    )
    calls = []

    class Provider:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            calls.append(kwargs["json"])
            message = {"role": "assistant", "content": "The public service has no bank feed."}
            if len(calls) % 2:
                message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "one",
                            "type": "function",
                            "function": {"name": "service_status", "arguments": "{}"},
                        }
                    ],
                }
            return httpx.Response(
                200, json={"choices": [{"message": message}]}, request=httpx.Request("POST", url)
            )

    with TestClient(app) as client:
        monkeypatch.setattr("settlement_recon.workspace.httpx.Client", Provider)
        for _ in range(2):
            result = client.post(
                "/workspace/api/agent/demo", json={"question": "Inspect public service status"}
            )
            assert result.status_code == 200, result.text
            assert result.json()["tools"][0]["name"] == "service_status"
        blocked = client.post(
            "/workspace/api/agent/demo", json={"question": "Inspect public service status"}
        )
        assert blocked.status_code == 429
        assert int(blocked.headers["retry-after"]) > 0
        assert len(calls) == 4
        assert (
            client.post("/workspace/api/agent", json={"question": "Inspect service"}).status_code
            == 401
        )
        assert client.post("/workspace/api/rates/sync").status_code == 401
        assert client.get("/workspace/api/payments").status_code == 401


def test_limiter_is_atomic_persistent_and_stores_no_raw_ip(tmp_path):
    from settlement_recon.public_demo import DemoBudget, buckets

    path = f"sqlite:///{tmp_path / 'limits.db'}"
    budget = DemoBudget(create_engine(path), TOKEN)

    def take(_):
        try:
            DemoBudget(create_engine(path), TOKEN).consume("203.0.113.4", now=1800000001)
            return True
        except HTTPException as exc:
            assert exc.status_code == 429
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(take, range(8))) == 2
    with budget.engine.connect() as conn:
        rows = list(conn.execute(select(buckets)).mappings())
    assert "203.0.113.4" not in str(rows)
    assert all(row["count"] <= 2 for row in rows)
    # Minute counter resets; persistent per-client budget still permits only one more.
    budget.consume("203.0.113.4", now=1800000061)
    with pytest.raises(HTTPException) as exc:
        DemoBudget(create_engine(path), TOKEN).consume("203.0.113.4", now=1800000121)
    assert exc.value.status_code == 429


def test_peer_identity_ignores_spoofed_headers_outside_vercel(monkeypatch):
    from settlement_recon.public_demo import client_identity

    request = Request(
        {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"1.2.3.4")],
            "client": ("203.0.113.7", 1234),
        }
    )
    monkeypatch.delenv("VERCEL", raising=False)
    assert client_identity(request) == "203.0.113.7"
    monkeypatch.setenv("VERCEL", "1")
    assert client_identity(request) == "1.2.3.4"


def test_public_validation_precedes_inference(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-unit-test-key")
    app = create_app(
        Reconciler(f"sqlite:///{tmp_path / 'db'}", FileArchive(tmp_path / "raw")), TOKEN
    )
    with TestClient(app) as client:
        assert (
            client.post("/workspace/api/agent/demo", json={"question": "x" * 601}).status_code
            == 422
        )
        assert (
            client.post(
                "/workspace/api/agent/demo",
                json={"question": "Inspect service", "model": "expensive"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/workspace/api/agent/demo",
                json={"question": "Inspect service"},
                headers={"Origin": "https://evil.example"},
            ).status_code
            == 403
        )


def test_daily_limit_applies_across_different_addresses(tmp_path):
    from settlement_recon.public_demo import DemoBudget

    budget = DemoBudget(create_engine(f"sqlite:///{tmp_path / 'limits'}"), TOKEN)
    start = 86400 * 20000 + 1
    for index in range(30):
        budget.consume(f"198.51.100.{index}", now=start + index * 60)
    with pytest.raises(HTTPException) as exc:
        budget.consume("203.0.113.200", now=start + 31 * 60)
    assert exc.value.status_code == 429
    assert int(exc.value.headers["Retry-After"]) > 60


def test_budget_fails_closed_when_database_is_unavailable(tmp_path, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from settlement_recon.public_demo import DemoBudget

    engine = create_engine(f"sqlite:///{tmp_path / 'limits'}")
    budget = DemoBudget(engine, TOKEN)

    def unavailable():
        raise OperationalError("redacted", {}, Exception("unavailable"))

    monkeypatch.setattr(engine, "begin", unavailable)
    with pytest.raises(HTTPException) as exc:
        budget.consume("203.0.113.1")
    assert exc.value.status_code == 503
