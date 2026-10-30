"""Build a case from actual residual obligations and unlinked SQL legs."""

import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from settlement_recon.api import create_app
from settlement_recon.domain import DomainError, FileArchive, Reconciler

TOKEN = "forensics-case-operator-000000000000000000"


@pytest.fixture
def service(tmp_path):
    value = Reconciler(f"sqlite:///{tmp_path / 'case.db'}", FileArchive(tmp_path / "raw"))
    value.ingest(
        "payments",
        "ledger",
        json.dumps(
            {
                "payments": [
                    {"payment_id": "p1", "currency": "USD", "amount": "100.00"},
                    {"payment_id": "p2", "currency": "EUR", "amount": "100.00"},
                ]
            }
        ).encode(),
    )
    value.ingest(
        "statement",
        "bank",
        b"row_id,payment_id,currency,net_amount,fee,settled_at\n"
        b"known,p1,USD,49,1,2026-10-30T10:00:00Z\n"
        b"unknown,unidentified,USD,49,1,2026-10-30T10:00:00Z\n",
    )
    return value


def extract(service, ids=None, source="bank"):
    from settlement_recon.forensics_case import extract_case

    return extract_case(service.engine, ids or ["p1"], source)


def test_residual_obligation_excludes_already_linked_bank_legs(service):
    from settlement_recon.forensics import analyze

    case = extract(service)
    assert case["case"]["payments"][0]["amount_minor"] == 5000
    assert len(case["case"]["legs"]) == 1
    assert case["provenance"]["legs"][0]["row_id"] == "unknown"
    assert case["provenance"]["payments"][0]["original_amount_minor"] == 10000
    assert case["provenance"]["payments"][0]["recorded_settled_minor"] == 5000
    assert analyze(case["case"])["suggestions"][0]["settled_minor"] == 5000
    assert service.reconcile(payment_ids=["p1"])[0]["status"] == "partial"


def test_unselected_payments_and_other_sources_are_excluded(service):
    case = extract(service, ["p2"], "other-bank")
    assert [row["payment_id"] for row in case["case"]["payments"]] == ["p2"]
    assert case["case"]["legs"] == []


def test_unknown_and_closed_obligations_are_rejected(service):
    with pytest.raises(DomainError) as error:
        extract(service, ["unknown"])
    assert error.value.code == "not_found"
    service.ingest(
        "statement",
        "bank",
        b"row_id,payment_id,currency,net_amount,fee,settled_at\n"
        b"close,p1,USD,50,0,2026-10-30T10:00:00Z\n",
    )
    with pytest.raises(DomainError, match="positive residual"):
        extract(service)


def test_missing_receipt_fails_closed_and_source_is_validated(service):
    with service.engine.begin() as connection:
        connection.execute(text("DELETE FROM ingestion_batches WHERE kind='statement'"))
    with pytest.raises(DomainError) as error:
        extract(service)
    assert error.value.code == "integrity"
    with pytest.raises(DomainError):
        extract(service, source="not a safe source")


def test_bank_capacity_cannot_silently_omit_candidates(service):
    raw = b"row_id,payment_id,currency,net_amount,fee,settled_at\n" + b"\n".join(
        f"r{i},unknown,USD,1,0,2026-10-30T10:00:00Z".encode() for i in range(33)
    )
    service.ingest("statement", "large-bank", raw)
    with pytest.raises(DomainError) as error:
        extract(service, source="large-bank")
    assert error.value.code == "size"


def test_http_case_is_protected_and_has_typed_provenance(service):
    client = TestClient(create_app(service, TOKEN))
    url = "/v1/forensics/case?payment_id=p1&source=bank"
    assert client.get(url).status_code == 401
    response = client.get(url, headers={"Authorization": "Bearer " + TOKEN})
    assert response.status_code == 200
    assert response.json()["provenance"]["snapshot"] == "sqlite-read-transaction"
    assert response.json()["provenance"]["legs"][0]["checksum"]


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="Real PostgreSQL required")
def test_postgres_residual_and_orphan_inputs_share_a_snapshot_during_concurrent_commit(tmp_path):
    identity = "forensics-" + uuid4().hex
    service = Reconciler(os.environ["TEST_DATABASE_URL"], FileArchive(tmp_path / "pg-raw"))
    service.ingest(
        "payments",
        identity,
        json.dumps(
            {"payments": [{"payment_id": identity, "currency": "USD", "amount": "100.00"}]}
        ).encode(),
    )
    committed = []

    def commit_between_reads(_conn, _cursor, statement, _params, _context, _many):
        if (
            not committed
            and statement.lstrip().startswith("SELECT")
            and "FROM payments LEFT OUTER JOIN" in statement
        ):
            committed.append(True)
            payload = (
                "row_id,payment_id,currency,net_amount,fee,settled_at\n"
                f"known,{identity},USD,50,0,2026-10-30T10:00:00Z\n"
                "orphan,unidentified,USD,50,0,2026-10-30T10:00:00Z\n"
            ).encode()
            service.ingest("statement", identity, payload)

    event.listen(service.engine, "after_cursor_execute", commit_between_reads)
    try:
        first = extract(service, [identity], identity)
    finally:
        event.remove(service.engine, "after_cursor_execute", commit_between_reads)
    assert committed and first["case"]["payments"][0]["amount_minor"] == 10000
    assert first["case"]["legs"] == []
    second = extract(service, [identity], identity)
    assert second["case"]["payments"][0]["amount_minor"] == 5000
    assert len(second["case"]["legs"]) == 1
    assert second["provenance"]["snapshot"] == "repeatable-read"
    with service.engine.connect() as connection:
        assert connection.exec_driver_sql("SHOW transaction_read_only").scalar_one() == "off"
        assert (
            connection.exec_driver_sql("SHOW transaction_isolation").scalar_one()
            == "read committed"
        )
