import json
import os
import subprocess
import sys


def test_cli_explains_real_demo_without_mutating_receipts(tmp_path):
    env = dict(os.environ, DATA_DIR=str(tmp_path), PYTHONPATH="src")
    subprocess.run(
        [sys.executable, "-m", "settlement_recon.cli", "demo"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "settlement_recon.cli",
            "explain",
            "demo-partial",
            "INR",
            "--limit",
            "5",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "partial"
    assert evidence["totals"]["difference_minor"] == 40000
    assert evidence["settlements"]["total_rows"] == 1


def test_cli_demo_and_replay_survive_process_restart(tmp_path):
    env = dict(os.environ, DATA_DIR=str(tmp_path), PYTHONPATH="src")
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-m", "settlement_recon.cli", "demo"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        assert report["matched"] == 1
        assert report["partial"] == 1
        assert report["quarantined_batches"] == 1


def test_cli_rejects_bad_file_without_business_effects(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not-json")
    env = dict(os.environ, DATA_DIR=str(tmp_path), PYTHONPATH="src")
    result = subprocess.run(
        [sys.executable, "-m", "settlement_recon.cli", "ingest", "payments", "ledger", str(path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "quarantined"
