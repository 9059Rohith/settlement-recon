import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from settlement_recon.api import create_app
from settlement_recon.domain import DomainError, FileArchive, Reconciler

TOKEN = "explanation-test-token-000000000000000000"


@pytest.fixture
def service(tmp_path):
    return Reconciler(f"sqlite:///{tmp_path / 'explain.db'}", FileArchive(tmp_path / "raw"))


def put_payment(service, identity="p1", amount="100.00", currency="USD"):
    raw = json.dumps(
        {"payments": [{"payment_id": identity, "amount": amount, "currency": currency}]}
    ).encode()
    return service.ingest("payments", "ledger", raw), raw


def put_statement(service, lines, source="bank"):
    raw = ("row_id,payment_id,currency,net_amount,fee,settled_at\n" + "\n".join(lines)).encode()
    return service.ingest("statement", source, raw), raw


def test_partial_explanation_has_exact_math_and_original_input_lineage(service):
    payment, raw_payment = put_payment(service)
    bank, raw_bank = put_statement(
        service,
        [
            "r1,p1,USD,39.25,0.75,2026-10-30T10:00:00Z",
            "r2,p1,USD,9.50,0.50,2026-10-30T11:00:00Z",
        ],
    )
    value = service.explain_payment("p1", "USD")
    assert value["status"] == "partial"
    assert value["totals"] == {
        "expected_minor": 10000,
        "net_minor": 4875,
        "fee_minor": 125,
        "settled_minor": 5000,
        "difference_minor": 5000,
    }
    assert value["currency_scale"] == 2
    assert value["rule"]["id"] == "settled-less-than-expected"
    assert value["payment"]["batch_id"] == payment["batch_id"]
    assert value["payment"]["checksum"] == hashlib.sha256(raw_payment).hexdigest()
    assert value["settlements"]["total_rows"] == 2
    assert value["settlements"]["truncated"] is False
    assert {row["batch_id"] for row in value["settlements"]["records"]} == {bank["batch_id"]}
    assert {row["checksum"] for row in value["settlements"]["records"]} == {
        hashlib.sha256(raw_bank).hexdigest()
    }
    assert value["archive_integrity_checked"] is False


@pytest.mark.parametrize("amount,expected", [("100.00", "matched"), ("101.00", "overpaid")])
def test_explanation_shares_reconciliation_status_rules(service, amount, expected):
    put_payment(service)
    put_statement(service, [f"r1,p1,USD,{amount},0,2026-10-30T10:00:00Z"])
    value = service.explain_payment("p1", "USD")
    row = service.reconcile(payment_ids=["p1"])[0]
    assert value["status"] == row["status"] == expected
    assert value["totals"]["difference_minor"] == row["difference_minor"]


def test_missing_orphan_and_currency_boundary_are_explicit(service):
    put_payment(service)
    put_statement(service, ["r1,p1,EUR,25,0,2026-10-30T10:00:00Z"])
    usd = service.explain_payment("p1", "USD")
    euro = service.explain_payment("p1", "EUR")
    assert usd["status"] == "missing" and usd["settlements"]["records"] == []
    assert euro["status"] == "orphan" and euro["payment"] is None
    assert euro["totals"]["settled_minor"] == 2500


def test_bounded_legs_do_not_change_complete_aggregate(service):
    put_payment(service)
    put_statement(service, [f"r{i:03},p1,USD,1,0,2026-10-30T10:00:00Z" for i in range(101)])
    value = service.explain_payment("p1", "USD", limit=5)
    assert value["status"] == "overpaid"
    assert value["totals"]["settled_minor"] == 10100
    assert value["settlements"]["total_rows"] == 101
    assert len(value["settlements"]["records"]) == 5
    assert value["settlements"]["truncated"] is True
    assert [r["row_id"] for r in value["settlements"]["records"]] == [f"r{i:03}" for i in range(5)]


@pytest.mark.parametrize(
    "identity,currency,limit",
    [
        ("../bad", "USD", 25),
        ("p1", "XXX", 25),
        ("p1", "USD", 0),
        ("p1", "USD", 101),
        ("p1", "USD", True),
        ("p1", [], 25),
    ],
)
def test_invalid_explanation_parameters_are_rejected(service, identity, currency, limit):
    with pytest.raises(DomainError):
        service.explain_payment(identity, currency, limit=limit)


def test_unknown_currency_group_is_not_found(service):
    with pytest.raises(DomainError) as error:
        service.explain_payment("absent", "USD")
    assert error.value.code == "not_found"


def test_missing_lineage_fails_closed(service):
    batch, _ = put_payment(service)
    with service.engine.begin() as connection:
        connection.execute(
            text("DELETE FROM ingestion_batches WHERE id=:id"), {"id": batch["batch_id"]}
        )
    with pytest.raises(DomainError) as error:
        service.explain_payment("p1", "USD")
    assert error.value.code == "integrity"


def test_missing_lineage_outside_returned_evidence_still_fails_closed(service):
    put_payment(service)
    put_statement(service, ["r1,p1,USD,10,0,2026-10-30T10:00:00Z"], source="bank-a")
    hidden, _ = put_statement(service, ["r2,p1,USD,10,0,2026-10-30T10:00:00Z"], source="bank-z")
    with service.engine.begin() as connection:
        connection.execute(
            text("DELETE FROM ingestion_batches WHERE id=:id"), {"id": hidden["batch_id"]}
        )
    with pytest.raises(DomainError) as error:
        service.explain_payment("p1", "USD", limit=1)
    assert error.value.code == "integrity"


def test_explanation_snapshot_does_not_mix_concurrently_committed_rows(service):
    put_payment(service)
    with service.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode=WAL").scalar() == "wal"
    committed = False

    def insert_after_snapshot(_connection, _cursor, sql, _parameters, _context, _many):
        nonlocal committed
        if not committed and sql.lstrip().upper().startswith("SELECT") and "FROM payments" in sql:
            committed = True
            put_statement(service, ["r1,p1,USD,100,0,2026-10-30T10:00:00Z"])

    event.listen(service.engine, "after_cursor_execute", insert_after_snapshot)
    try:
        evidence = service.explain_payment("p1", "USD")
    finally:
        event.remove(service.engine, "after_cursor_execute", insert_after_snapshot)
    assert committed
    assert evidence["status"] == "missing"
    assert evidence["settlements"]["total_rows"] == 0
    assert evidence["settlements"]["records"] == []
    assert service.reconcile(payment_ids=["p1"])[0]["status"] == "matched"


def test_explanation_uses_constant_number_of_selects(service):
    put_payment(service)
    put_statement(service, [f"r{i},p1,USD,1,0,2026-10-30T10:00:00Z" for i in range(30)])
    queries = []

    def capture(_connection, _cursor, sql, _parameters, _context, _many):
        if sql.lstrip().upper().startswith("SELECT"):
            queries.append(sql)

    event.listen(service.engine, "before_cursor_execute", capture)
    try:
        service.explain_payment("p1", "USD")
    finally:
        event.remove(service.engine, "before_cursor_execute", capture)
    assert len(queries) == 3


def test_explanation_api_is_authenticated_and_read_only(service):
    put_payment(service)
    with TestClient(create_app(service, TOKEN, "reader-token-000000000000000000000")) as client:
        route = "/v1/reconciliation/p1/USD/explanation"
        assert client.get(route).status_code == 401
        value = client.get(
            route, headers={"Authorization": "Bearer reader-token-000000000000000000000"}
        )
        assert value.status_code == 200 and value.json()["status"] == "missing"
        assert (
            client.get(
                route + "?limit=101", headers={"Authorization": f"Bearer {TOKEN}"}
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/v1/reconciliation/absent/USD/explanation",
                headers={"Authorization": f"Bearer {TOKEN}"},
            ).status_code
            == 404
        )
    assert len(service.batches()) == 1


def test_explanation_contract_is_described_in_openapi(service):
    with TestClient(create_app(service, TOKEN)) as client:
        schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/v1/reconciliation/{payment_id}/{currency}/explanation"]["get"]
    response = operation["responses"]["200"]["content"]["application/json"]["schema"]
    model = schema["components"]["schemas"][response["$ref"].rsplit("/", 1)[-1]]
    assert {"status", "rule", "totals", "payment", "settlements", "snapshot"} <= set(
        model["properties"]
    )
