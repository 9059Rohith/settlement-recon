import json
import os
import subprocess
import sys

from settlement_recon.domain import FileArchive, Reconciler, payment_table


def test_benchmark_scopes_correctness_to_its_own_workload(tmp_path):
    url = f"sqlite:///{tmp_path / 'shared.db'}"
    service = Reconciler(url, FileArchive(tmp_path / "raw"))
    with service.engine.begin() as connection:
        connection.execute(
            payment_table.insert(),
            [
                {
                    "payment_id": f"0-old-{i:05}",
                    "currency": "USD",
                    "amount_minor": 100,
                    "batch_id": "unrelated-existing-workload",
                }
                for i in range(10001)
            ],
        )
    service.engine.dispose()
    output = tmp_path / "measurement.json"
    result = subprocess.run(
        [sys.executable, "scripts/evaluate.py", "--rows", "5", "--output", str(output)],
        env=dict(os.environ, BENCHMARK_DATABASE_URL=url, PYTHONPATH="src"),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text())
    assert report["rows"] == report["correctness"]["matched_rows"] == 5
    assert report["reconciliation"]["n"] == 30
