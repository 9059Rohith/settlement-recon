from fastapi.testclient import TestClient
from sqlalchemy import event

from settlement_recon.api import create_app
from settlement_recon.domain import FileArchive, Reconciler


def service(tmp_path):
    return Reconciler(f"sqlite:///{tmp_path / 'test.db'}", FileArchive(tmp_path / "raw"))


def test_truncated_csv_row_is_quarantined_not_a_server_error(tmp_path):
    svc = service(tmp_path)
    raw = b"row_id,payment_id,currency,net_amount,fee,settled_at\nr1,p1,USD,10,0\n"
    result = svc.ingest("statement", "bank", raw)
    assert result["status"] == "quarantined"
    assert svc.batches()[0]["batch_id"] == result["batch_id"]
    assert svc.reconcile() == []


def test_non_ascii_bearer_is_unauthorized_not_server_error(tmp_path):
    with TestClient(
        create_app(service(tmp_path), "test-token-000000000000000000000000000")
    ) as client:
        result = client.get("/v1/batches", headers={b"Authorization": b"Bearer \xff\xfe"})
        assert result.status_code == 401


def test_blank_token_configuration_fails_closed(tmp_path):
    with TestClient(create_app(service(tmp_path), " " * 40)) as client:
        assert client.get("/v1/batches").status_code == 503


def test_cumulative_money_limit_prevents_sqlite_integer_overflow(tmp_path):
    svc = service(tmp_path)
    header = "row_id,payment_id,currency,net_amount,fee,settled_at\n"
    raw = header + "\n".join(
        f"r{i},p1,USD,9999999999999.99,9999999999999.99,2026-10-30T10:00:00Z" for i in range(5000)
    )
    result = svc.ingest("statement", "bank", raw.encode())
    assert result["status"] == "quarantined"
    assert svc.reconcile() == []


def test_cumulative_bound_across_sources_and_batches(tmp_path):
    svc = service(tmp_path)
    header = "row_id,payment_id,currency,net_amount,fee,settled_at\n"
    assert (
        svc.ingest(
            "statement",
            "bank1",
            (header + "r1,p1,USD,9999999999999.99,0,2026-10-30T10:00:00Z").encode(),
        )["status"]
        == "accepted"
    )
    result = svc.ingest(
        "statement", "bank2", (header + "r2,p1,USD,1,0,2026-10-30T10:00:00Z").encode()
    )
    assert result["status"] == "quarantined"
    assert svc.reconcile()[0]["settled_minor"] == 999999999999999


def test_duplicate_json_fields_do_not_silently_override(tmp_path):
    svc = service(tmp_path)
    content = '{"payments":[{"payment_id":"p1","currency":"USD","amount":"1","amount":"2"}]}'
    assert svc.ingest("payments", "ledger", content.encode())["status"] == "quarantined"


def test_reconciliation_is_a_consistent_statement_snapshot(tmp_path):
    svc = service(tmp_path)
    raw = (
        b"row_id,payment_id,currency,net_amount,fee,settled_at\n"
        b"r1,p1,USD,10,0,2026-10-30T10:00:00Z\n"
    )
    svc.ingest("statement", "bank", raw)
    selects = []

    def interleave(connection, _cursor, sql, _params, _context, _many):
        if sql.lstrip().upper().startswith("SELECT"):
            selects.append(sql)
            if len(selects) == 1:
                connection.exec_driver_sql(
                    "INSERT INTO payments(payment_id,currency,amount_minor,batch_id) "
                    "VALUES ('p1','USD',1000,'test-interleave')"
                )

    event.listen(svc.engine, "after_cursor_execute", interleave)
    rows = svc.reconcile()
    event.remove(svc.engine, "after_cursor_execute", interleave)
    assert len(rows) == 1  # Either pre- or post-insert snapshot must contain p1.
    assert rows[0]["payment_id"] == "p1"
