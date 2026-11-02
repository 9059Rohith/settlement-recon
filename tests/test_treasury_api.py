"""Public analysis remains isolated from every persisted financial record."""

import json

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from settlement_recon.api import create_app
from settlement_recon.domain import FileArchive, Reconciler
from settlement_recon.workspace import observations


def client_for(tmp_path, captured=True):
    service = Reconciler(f"sqlite:///{tmp_path / 'treasury.db'}", FileArchive(tmp_path / "raw"))
    app = create_app(service, "test-treasury-token-00000000000000000000")
    if captured:
        with service.engine.begin() as connection:
            connection.execute(
                observations.insert().values(
                    digest="a" * 64,
                    captured_at="2026-11-01T18:13:31Z",
                    payload=json.dumps({"base": "EUR", "date": "2026-10-30", "rates": {"USD": 2}}),
                )
            )
    return TestClient(app), service


def body():
    return {
        "reporting_currency": "EUR",
        "positions": [
            {"id": "visitor", "currency": "USD", "direction": "receivable", "amount": "100"}
        ],
        "scenarios": [{"name": "Down", "shocks_bps": {"USD": -1000}}],
    }


def test_anonymous_analysis_is_real_read_only_and_downloadable(tmp_path):
    client, service = client_for(tmp_path)
    with client:
        response = client.post("/workspace/api/treasury", json=body())
        assert response.status_code == 200
        assert response.json()["baseline"]["net"] == "50"
        assert response.json()["scenarios"][0]["net"] == "45"
        assert response.json()["worst_loss"] == "5"
        assert response.json()["source"]["digest"] == "a" * 64
        assert client.get("/workspace/treasury").status_code == 200
        assert client.get("/workspace/api/payments").status_code == 401
        assert client.post("/workspace/api/rates/sync").status_code == 401
        assert response.headers["cache-control"] == "no-store"
    with service.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(observations)) == 1
        assert connection.execute(select(observations.c.payload)).scalar_one() == json.dumps(
            {"base": "EUR", "date": "2026-10-30", "rates": {"USD": 2}}
        )


def test_no_capture_fails_closed(tmp_path):
    client, _ = client_for(tmp_path, captured=False)
    with client:
        assert client.post("/workspace/api/treasury", json=body()).status_code == 503


def test_cross_site_and_large_bodies_rejected_without_reflecting_values(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        assert (
            client.post(
                "/workspace/api/treasury",
                json=body(),
                headers={"origin": "https://untrusted.example"},
            ).status_code
            == 403
        )
        assert client.post("/workspace/api/treasury", content="x" * 32769).status_code == 413
        response = client.post("/workspace/api/treasury", json={"private": "do-not-reflect-this"})
        assert response.status_code == 422
        assert "do-not-reflect-this" not in response.text
        assert client.post("/workspace/api/treasury", content="not-json").status_code == 422


def test_maximum_typed_workload_exceeds_ai_limit_but_remains_bounded(tmp_path):
    client, _ = client_for(tmp_path)
    request = body()
    request["positions"] = [
        {"id": f"p{i}", "currency": "USD", "direction": "receivable", "amount": "100"}
        for i in range(50)
    ]
    request["scenarios"] = [
        {"name": f"Scenario{i}", "shocks_bps": {"USD": -1000}} for i in range(8)
    ]
    with client:
        response = client.post("/workspace/api/treasury", json=request)
        assert response.status_code == 200
        assert response.json()["baseline"]["net"] == "2500"
        assert response.json()["worst_loss"] == "250"


def test_duplicate_keys_and_deep_json_are_rejected_unambiguously(tmp_path):
    client, _ = client_for(tmp_path)
    raw = json.dumps(body()).replace('"USD": -1000', '"USD": -1000, "USD": 1000')
    with client:
        assert client.post("/workspace/api/treasury", content=raw).status_code == 422
        assert (
            client.post("/workspace/api/treasury", content="[" * 3000 + "]" * 3000).status_code
            == 422
        )
