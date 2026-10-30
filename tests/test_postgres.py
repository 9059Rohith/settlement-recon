import json
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

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
