import json

from sqlalchemy import event

from settlement_recon.domain import FileArchive, Reconciler


def test_ingestion_has_constant_query_count_not_per_row(tmp_path):
    service = Reconciler(f"sqlite:///{tmp_path / 'test.db'}", FileArchive(tmp_path / "raw"))
    statements = []

    def observed(_connection, _cursor, sql, _parameters, _context, _executemany):
        statements.append(sql)

    event.listen(service.engine, "before_cursor_execute", observed)
    body = json.dumps(
        {
            "payments": [
                {"payment_id": f"p-{i}", "currency": "USD", "amount": "1"} for i in range(200)
            ]
        }
    ).encode()
    assert service.ingest("payments", "budget-test", body)["accepted_rows"] == 200
    assert len(statements) <= 8, len(statements)
