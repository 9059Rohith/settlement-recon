import json

import pytest
from fastapi.testclient import TestClient

from settlement_recon.api import create_app
from settlement_recon.domain import FileArchive, Reconciler

TOKEN = "test-only-token-never-use-in-production-0001"


@pytest.fixture
def client(tmp_path):
    svc = Reconciler(f"sqlite:///{tmp_path / 'api.db'}", FileArchive(tmp_path / "raw"))
    with TestClient(create_app(svc, TOKEN, "reader-token-000000000000000000000")) as value:
        yield value


def test_health_is_public_data_is_protected(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").status_code == 200
    assert client.get("/v1/reconciliation").status_code == 401
    assert client.get("/metrics").status_code == 401
    assert client.get("/docs").status_code == 200


def test_actual_api_ingestion_replay_and_reconciliation(client):
    headers = {"Authorization": f"Bearer {TOKEN}"}
    body = json.dumps({"payments": [{"payment_id": "p1", "currency": "USD", "amount": "10.00"}]})
    first = client.post("/v1/ingest/payments?source=ledger", content=body, headers=headers)
    assert first.status_code == 200
    assert client.post("/v1/ingest/payments?source=ledger", content=body, headers=headers).json()[
        "replayed"
    ]
    csv = (
        "row_id,payment_id,currency,net_amount,fee,settled_at\n"
        "r1,p1,USD,9.50,0.50,2026-10-30T10:00:00Z\n"
    )
    assert (
        client.post("/v1/ingest/statement?source=bank", content=csv, headers=headers).status_code
        == 200
    )
    assert client.get("/v1/reconciliation", headers=headers).json()[0]["status"] == "matched"
    batch = first.json()["batch_id"]
    assert client.get(f"/v1/batches/{batch}/verify", headers=headers).json()["intact"]
    assert "settlement_recon_http_requests_total" in client.get("/metrics", headers=headers).text


def test_reader_cannot_mutate(client):
    headers = {"Authorization": "Bearer reader-token-000000000000000000000"}
    assert client.get("/v1/batches", headers=headers).status_code == 200
    assert (
        client.post("/v1/ingest/payments?source=x", content="{}", headers=headers).status_code
        == 403
    )


def test_size_invalid_source_and_kind(client):
    headers = {"Authorization": f"Bearer {TOKEN}"}
    assert (
        client.post(
            "/v1/ingest/payments?source=x", content=b"x" * 2_000_001, headers=headers
        ).status_code
        == 413
    )
    assert (
        client.post("/v1/ingest/payments?source=../x", content="{}", headers=headers).status_code
        == 422
    )
    assert (
        client.post("/v1/ingest/unknown?source=x", content="{}", headers=headers).status_code == 422
    )


def test_security_headers_and_no_cross_origin_permission(client):
    response = client.get("/healthz", headers={"Origin": "https://untrusted.example"})
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers.get("Access-Control-Allow-Origin") is None
    assert len(response.headers["X-Request-ID"]) == 36


def test_unconfigured_auth_fails_closed(tmp_path):
    svc = Reconciler(f"sqlite:///{tmp_path / 'off.db'}", FileArchive(tmp_path / "raw"))
    with TestClient(create_app(svc, "", "")) as value:
        assert value.get("/v1/batches").status_code == 503


def test_missing_batch_not_found(client):
    assert (
        client.get(
            "/v1/batches/missing/verify", headers={"Authorization": f"Bearer {TOKEN}"}
        ).status_code
        == 404
    )


def test_missing_health_dependency_reports_not_ready(client, monkeypatch):
    def fail():
        raise OSError("database password should never be exposed")

    monkeypatch.setattr(client.app.state.service.engine, "connect", fail)
    response = client.get("/readyz")
    assert response.status_code == 503
    assert "password" not in response.text
