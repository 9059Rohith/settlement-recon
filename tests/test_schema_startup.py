from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from settlement_recon.database_archive import DatabaseArchive
from settlement_recon.domain import Reconciler


def test_concurrent_empty_database_bootstrap(tmp_path):
    url = f"sqlite:///{tmp_path / 'cold.db'}"
    barrier = Barrier(8)

    def start(_index):
        barrier.wait()
        archive = DatabaseArchive(url)
        service = Reconciler(url, archive)
        archive.ready()
        assert service.batches() == []
        service.engine.dispose()
        archive.engine.dispose()

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(start, range(8)))
