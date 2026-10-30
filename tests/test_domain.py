import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from settlement_recon.domain import DomainError, FileArchive, Reconciler, money


@pytest.fixture
def service(tmp_path):
    return Reconciler(f"sqlite:///{tmp_path / 'test.db'}", FileArchive(tmp_path / "raw"))


def payment(pid="p1", amount="100.00", currency="USD"):
    return {"payment_id": pid, "amount": amount, "currency": currency}


def payments(*items):
    return json.dumps({"payments": list(items)}).encode()


def statement(*lines):
    return ("row_id,payment_id,currency,net_amount,fee,settled_at\n" + "\n".join(lines)).encode()


def test_exact_minor_unit_conversion():
    assert money("10.01", "USD") == 1001
    assert money("123", "JPY") == 123


@pytest.mark.parametrize(
    "amount,currency",
    [
        ("1.001", "USD"),
        ("NaN", "USD"),
        ("Infinity", "USD"),
        ("-1", "USD"),
        ("1.1", "JPY"),
        ("1", "XXX"),
        ("1e2", "USD"),
    ],
)
def test_rejects_invalid_money(amount, currency):
    with pytest.raises(DomainError):
        money(amount, currency)


@given(st.integers(min_value=0, max_value=10**10))
def test_money_roundtrip_without_float_loss(minor):
    assert money(str(Decimal(minor) / 100), "USD") == minor


def test_full_match_with_fee_and_replay(service):
    service.ingest("payments", "ledger", payments(payment()))
    raw = statement("r1,p1,USD,99.00,1.00,2026-10-30T10:00:00Z")
    first = service.ingest("statement", "bank-a", raw)
    second = service.ingest("statement", "bank-a", raw)
    assert first["status"] == "accepted"
    assert first["accepted_rows"] == 1
    assert second["replayed"] is True
    assert second["batch_id"] == first["batch_id"]
    row = service.reconcile()[0]
    assert row["status"] == "matched"
    assert row["settled_minor"] == row["expected_minor"] == 10000


def test_partial_then_complete_across_batches(service):
    service.ingest("payments", "ledger", payments(payment()))
    service.ingest("statement", "bank", statement("r1,p1,USD,59,1,2026-10-30T10:00:00Z"))
    assert service.reconcile()[0]["status"] == "partial"
    service.ingest("statement", "bank", statement("r2,p1,USD,40,0,2026-10-30T11:00:00Z"))
    assert service.reconcile()[0]["status"] == "matched"


def test_overpaid_missing_orphan_and_currency_mismatch(service):
    service.ingest("payments", "ledger", payments(payment(), payment("p2"), payment("p3")))
    service.ingest(
        "statement",
        "bank",
        statement(
            "r1,p1,USD,101,0,2026-10-30T10:00:00Z",
            "r2,unknown,USD,10,0,2026-10-30T10:00:00Z",
            "r3,p3,EUR,100,0,2026-10-30T10:00:00Z",
        ),
    )
    statuses = {(r["payment_id"], r["currency"]): r["status"] for r in service.reconcile()}
    assert statuses == {
        ("p1", "USD"): "overpaid",
        ("p2", "USD"): "missing",
        ("p3", "USD"): "missing",
        ("unknown", "USD"): "orphan",
        ("p3", "EUR"): "orphan",
    }


def test_changed_duplicate_payment_quarantines_whole_batch(service):
    service.ingest("payments", "ledger", payments(payment()))
    result = service.ingest("payments", "ledger", payments(payment("p2"), payment(amount="50")))
    assert result["status"] == "quarantined"
    assert result["accepted_rows"] == 0
    assert result["errors"][0]["code"] == "conflict"
    assert len(service.reconcile()) == 1


def test_repeated_row_across_different_files_has_single_effect(service):
    row = "r1,p1,USD,99,1,2026-10-30T10:00:00Z"
    service.ingest("payments", "ledger", payments(payment()))
    service.ingest("statement", "bank", statement(row))
    service.ingest("statement", "bank", statement(row, row))
    assert service.reconcile()[0]["settled_minor"] == 10000


def test_conflicting_statement_row_quarantines(service):
    service.ingest("statement", "bank", statement("r1,p1,USD,10,0,2026-10-30T10:00:00Z"))
    result = service.ingest("statement", "bank", statement("r1,p1,USD,11,0,2026-10-30T10:00:00Z"))
    assert result["status"] == "quarantined"
    assert service.reconcile()[0]["settled_minor"] == 1000


@pytest.mark.parametrize(
    "raw",
    [
        b"not,json",
        b'{"payments":[{"payment_id":"p1"}]}',
        payments(payment(amount="0.001")),
        b"[]",
        b"null",
    ],
)
def test_invalid_payment_batch_has_auditable_quarantine(service, raw):
    result = service.ingest("payments", "ledger", raw)
    assert result["status"] == "quarantined"
    assert result["errors"]
    assert service.reconcile() == []
    assert service.verify_archive(result["batch_id"])


def test_csv_validation_blocks_naive_timestamps(service):
    result = service.ingest("statement", "bank", statement("r1,p1,USD,10,0,2026-10-30T10:00:00"))
    assert result["status"] == "quarantined"


def test_path_traversal_source_rejected(service):
    with pytest.raises(DomainError):
        service.ingest("payments", "../../secret", payments(payment()))


def test_archive_error_never_commits_business_rows(service, monkeypatch):
    def fail(_):
        raise OSError("unavailable")

    monkeypatch.setattr(service.archive, "put", fail)
    with pytest.raises(OSError):
        service.ingest("payments", "ledger", payments(payment()))
    assert service.reconcile() == []
    assert service.batches() == []


def test_restart_replay_is_durable(service):
    raw = payments(payment())
    first = service.ingest("payments", "ledger", raw)
    fresh = Reconciler(str(service.engine.url), service.archive)
    assert fresh.ingest("payments", "ledger", raw)["batch_id"] == first["batch_id"]
    assert len(fresh.reconcile()) == 1


def test_concurrent_identical_ingestion_has_single_effect(service):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: service.ingest("payments", "ledger", payments(payment())), range(8))
        )
    assert len({r["batch_id"] for r in results}) == 1
    assert len(service.reconcile()) == 1


def test_archive_corruption_detected(service):
    result = service.ingest("payments", "ledger", payments(payment()))
    (service.archive.root / result["checksum"]).write_bytes(b"corrupt")
    assert not service.verify_archive(result["batch_id"])
