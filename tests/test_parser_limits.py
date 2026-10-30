from settlement_recon.domain import MAX_ROWS, FileArchive, Reconciler


def test_deep_json_is_auditable_quarantine(tmp_path):
    service = Reconciler(f"sqlite:///{tmp_path / 'test.db'}", FileArchive(tmp_path / "raw"))
    content = b'{"payments":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}"
    assert service.ingest("payments", "deep-json", content)["status"] == "quarantined"
    assert len(service.batches()) == 1


def test_csv_reader_stops_at_row_bound(tmp_path, monkeypatch):
    service = Reconciler(f"sqlite:///{tmp_path / 'test.db'}", FileArchive(tmp_path / "raw"))

    class BoundedReader:
        fieldnames = ["row_id", "payment_id", "currency", "net_amount", "fee", "settled_at"]

        def __iter__(self):
            for i in range(MAX_ROWS + 1):
                yield {
                    "row_id": f"r{i}",
                    "payment_id": "p1",
                    "currency": "USD",
                    "net_amount": "1",
                    "fee": "0",
                    "settled_at": "2026-10-30T10:00:00Z",
                }
            raise AssertionError("Parser consumed more than its row budget")

    monkeypatch.setattr("settlement_recon.domain.csv.DictReader", lambda *a, **kw: BoundedReader())
    assert service.ingest("statement", "row-budget", b"bounded input")["status"] == "quarantined"
