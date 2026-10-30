import json

import pytest
from fastapi.testclient import TestClient

from settlement_recon.api import create_app, from_environment
from settlement_recon.domain import FileArchive, Reconciler

TOKEN = "test-token-00000000000000000000000000"


def test_demo_is_opt_in_and_uses_actual_ingestion(tmp_path):
    service = Reconciler(f"sqlite:///{tmp_path / 'demo.db'}", FileArchive(tmp_path / "raw"))
    with TestClient(create_app(service, TOKEN)) as client:
        assert client.get("/demo/summary").status_code == 404
    from settlement_recon.demo import seed_demo

    seed_demo(service)
    seed_demo(service)
    with TestClient(create_app(service, TOKEN, public_demo=True)) as client:
        result = client.get("/demo/summary")
        assert result.status_code == 200
        assert result.json()["outcomes"] == {"matched": 1, "partial": 1, "missing": 1}
        assert result.json()["archive_verified"] is True
        assert result.json()["quarantined_batches"] == 1
        assert len(service.batches()) == 3
        assert client.get("/demo").status_code == 200
        assert client.get("/v1/batches").status_code == 401
        assert client.post("/v1/ingest/payments?source=x", content="{}").status_code == 401


def test_ephemeral_host_profile_preserves_raw_data(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "ephemeral"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'persistent.db'}")
    monkeypatch.setenv("RAW_STORE", "database")
    monkeypatch.setenv("SEED_DEMO", "true")
    monkeypatch.setenv("PUBLIC_DEMO", "true")
    monkeypatch.setenv("API_TOKEN", TOKEN)
    monkeypatch.setenv("ALLOWED_HOSTS", "testserver")
    with TestClient(from_environment()) as client:
        assert client.get("/demo/summary").json()["archive_verified"]
        assert client.get("/demo", headers={"Host": "evil.example"}).status_code == 400
    with TestClient(from_environment()) as client:
        assert client.get("/demo/summary").json()["archive_verified"]


def test_unknown_raw_store_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAW_STORE", "typo")
    with pytest.raises(ValueError, match="RAW_STORE"):
        from_environment()


def test_database_mode_does_not_require_local_data_directory(tmp_path, monkeypatch):
    readonly_root = tmp_path / "not-a-directory"
    readonly_root.write_text("local writes unavailable")
    monkeypatch.setenv("DATA_DIR", str(readonly_root))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'remote-equivalent.db'}")
    monkeypatch.setenv("RAW_STORE", "database")
    with TestClient(from_environment()) as client:
        assert client.get("/readyz").status_code == 200


def test_public_summary_scopes_fixture_before_global_query_limit(tmp_path):
    from settlement_recon.demo import seed_demo, summary

    service = Reconciler(f"sqlite:///{tmp_path / 'scoped.db'}", FileArchive(tmp_path / "raw"))
    seed_demo(service)
    for start, stop in [(0, 10000), (10000, 10001)]:
        service.ingest(
            "payments",
            "unrelated",
            json.dumps(
                {
                    "payments": [
                        {"payment_id": f"a{index:05}", "currency": "USD", "amount": "0.01"}
                        for index in range(start, stop)
                    ]
                }
            ).encode(),
        )
    service.ingest(
        "statement",
        "unrelated-bank",
        (
            b"row_id,payment_id,currency,net_amount,fee,settled_at\n"
            b"other-row,demo-matched-v1,USD,999.00,1.00,2026-10-30T10:00:00Z\n"
        ),
    )
    assert not any(row["payment_id"].startswith("demo-") for row in service.reconcile())
    assert summary(service)["outcomes"] == {"matched": 1, "partial": 1, "missing": 1}
