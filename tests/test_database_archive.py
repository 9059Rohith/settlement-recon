import hashlib

import pytest
from sqlalchemy import text

from settlement_recon.database_archive import DatabaseArchive
from settlement_recon.domain import DomainError, Reconciler


def test_archive_survives_recreation_and_replay(tmp_path):
    url = f"sqlite:///{tmp_path / 'durable.db'}"
    archive = DatabaseArchive(url)
    checksum = archive.put(b"original input")
    assert checksum == hashlib.sha256(b"original input").hexdigest()
    assert archive.put(b"original input") == checksum
    recreated = DatabaseArchive(url)
    assert recreated.read(checksum) == b"original input"
    recreated.ready()
    with pytest.raises(DomainError):
        recreated.read("../unsafe")
    with pytest.raises(FileNotFoundError):
        recreated.read("0" * 64)


def test_archive_detects_corruption(tmp_path):
    archive = DatabaseArchive(f"sqlite:///{tmp_path / 'corrupt.db'}")
    checksum = archive.put(b"original")
    with archive.engine.begin() as connection:
        connection.execute(text("UPDATE raw_archive SET payload = :payload"), {"payload": b"bad"})
    with pytest.raises(OSError, match="corruption"):
        archive.put(b"original")
    with pytest.raises(OSError, match="corruption"):
        archive.read(checksum)


def test_reconciliation_uses_durable_archive(tmp_path):
    url = f"sqlite:///{tmp_path / 'recon.db'}"
    service = Reconciler(url, DatabaseArchive(url))
    raw = b'{"payments":[{"payment_id":"p1","currency":"USD","amount":"1.00"}]}'
    first = service.ingest("payments", "test", raw)
    recreated = Reconciler(url, DatabaseArchive(url))
    assert recreated.verify_archive(first["batch_id"])
    assert recreated.ingest("payments", "test", raw)["replayed"]
