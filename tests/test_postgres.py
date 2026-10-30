import json
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url

from settlement_recon.database_archive import DatabaseArchive
from settlement_recon.domain import FileArchive, Reconciler


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL to real PostgreSQL"
)
def test_postgres_concurrency_and_exact_reconciliation(tmp_path):
    service = Reconciler(os.environ["TEST_DATABASE_URL"], FileArchive(tmp_path / "raw"))
    pid = str(uuid4())
    body = json.dumps(
        {"payments": [{"payment_id": pid, "currency": "USD", "amount": "100.01"}]}
    ).encode()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: service.ingest("payments", "postgres-test", body), range(8))
        )
    assert len({r["batch_id"] for r in results}) == 1
    csv = (
        "row_id,payment_id,currency,net_amount,fee,settled_at\n"
        f"{pid},{pid},USD,99.01,1.00,2026-10-30T10:00:00Z\n"
    )
    service.ingest("statement", "postgres-test", csv.encode())
    rows = [r for r in service.reconcile() if r["payment_id"] == pid]
    assert len(rows) == 1
    assert rows[0]["status"] == "matched"
    assert rows[0]["settled_minor"] == 10001
    service.engine.dispose()


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL")
def test_postgres_raw_archive_concurrent_writes_and_restart():
    archive = DatabaseArchive(os.environ["TEST_DATABASE_URL"])
    raw = ("synthetic-archive-" + uuid4().hex).encode()
    with ThreadPoolExecutor(max_workers=4) as pool:
        checksums = list(pool.map(lambda _: archive.put(raw), range(8)))
    assert len(set(checksums)) == 1
    recreated = DatabaseArchive(os.environ["TEST_DATABASE_URL"])
    assert recreated.read(checksums[0]) == raw
    recreated.ready()
    archive.engine.dispose()
    recreated.engine.dispose()


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL")
def test_postgres_concurrent_cold_schema_initialization():
    schema = "cold_start_" + uuid4().hex
    database_url = os.environ["TEST_DATABASE_URL"]
    admin = create_engine(database_url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(database_url).update_query_dict({"options": f"-csearch_path={schema}"})

    def start(_index):
        archive = DatabaseArchive(scoped)
        service = Reconciler(scoped, archive)
        archive.ready()
        assert service.batches() == []
        service.engine.dispose()
        archive.engine.dispose()

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(start, range(8)))
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL")
def test_postgres_explanation_pins_snapshot_and_resets_read_only_state(tmp_path):
    service = Reconciler(os.environ["TEST_DATABASE_URL"], FileArchive(tmp_path / "raw"))
    identity = "explanation-" + uuid4().hex
    payment = json.dumps(
        {"payments": [{"payment_id": identity, "currency": "USD", "amount": "10.00"}]}
    ).encode()
    service.ingest("payments", "explanation-test", payment)
    committed = False

    def write_during_read(_connection, _cursor, sql, _parameters, _context, _many):
        nonlocal committed
        if not committed and sql.lstrip().upper().startswith("SELECT") and "FROM payments" in sql:
            committed = True
            raw = (
                "row_id,payment_id,currency,net_amount,fee,settled_at\n"
                f"{identity},{identity},USD,9.50,0.50,2026-10-30T10:00:00Z\n"
            ).encode()
            service.ingest("statement", "explanation-test-bank", raw)

    event.listen(service.engine, "after_cursor_execute", write_during_read)
    try:
        evidence = service.explain_payment(identity, "USD")
    finally:
        event.remove(service.engine, "after_cursor_execute", write_during_read)
    assert committed and evidence["status"] == "missing"
    assert evidence["snapshot"] == "repeatable-read"
    assert evidence["settlements"]["total_rows"] == 0
    assert evidence["settlements"]["records"] == []
    assert service.explain_payment(identity, "USD")["status"] == "matched"
    with service.engine.connect() as connection:
        assert connection.exec_driver_sql("SHOW transaction_read_only").scalar() == "off"
        assert connection.get_isolation_level() == "READ COMMITTED"
    service.engine.dispose()
