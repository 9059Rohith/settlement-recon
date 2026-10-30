"""Airflow 3 DAG: bounded HTTP tasks retry the same immutable daily inputs."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from airflow.sdk import dag, task


@dag(
    schedule="0 2 * * *",
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(seconds=15),
        "execution_timeout": timedelta(minutes=2),
    },
)
def reconciliation():
    @task
    def ingest(kind, filename, ds=None):
        # ds comes from Airflow's data interval, never wall-clock "latest".
        root = Path(os.environ.get("RECON_INPUT_ROOT", "/opt/airflow/input"))
        path = root / ds / filename
        with path.open("rb") as handle:
            content = handle.read(2_000_001)
        if len(content) > 2_000_000:
            raise ValueError("Input exceeds documented limit")
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            response = client.post(
                f"{os.environ['RECON_API_URL']}/v1/ingest/{kind}",
                params={"source": "daily-ledger" if kind == "payments" else "daily-bank"},
                content=content,
                headers={"Authorization": f"Bearer {os.environ['RECON_API_TOKEN']}"},
            )
            response.raise_for_status()
            result = response.json()
            if result["status"] != "accepted":
                raise ValueError("Input quarantined; inspect operator API before replay")
        return result["batch_id"]

    ingest("payments", "payments.json") >> ingest("statement", "statement.csv")


reconciliation()
