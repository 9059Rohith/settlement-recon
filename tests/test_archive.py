import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest

from settlement_recon.domain import FileArchive


def test_failed_flush_cannot_publish_raw_object(tmp_path, monkeypatch):
    archive = FileArchive(tmp_path)

    def fail(_):
        raise OSError("injected durable flush failure")

    monkeypatch.setattr("settlement_recon.domain.os.fsync", fail)
    with pytest.raises(OSError):
        archive.put(b"uncommitted input")
    assert not (tmp_path / hashlib.sha256(b"uncommitted input").hexdigest()).exists()


def test_concurrent_large_archive_writes_are_atomic(tmp_path):
    archive = FileArchive(tmp_path)
    content = b"x" * 1_000_000
    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(lambda _: archive.put(content), range(12)))
    assert len(set(values)) == 1
    assert archive.read(values[0]) == content
