"""Real measured ingestion/query/recovery benchmark; no seeded or hardcoded timings."""

import argparse
import json
import os
import platform
import statistics
import tempfile
import time
from pathlib import Path

from settlement_recon.domain import FileArchive, Reconciler


def summary(values):
    ordered = sorted(values)

    def percentile(q):
        return round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * q))], 3)

    return {
        "n": len(values),
        "p50_ms": percentile(0.5),
        "p95_ms": percentile(0.95),
        "p99_ms": percentile(0.99),
        "mean_ms": round(statistics.mean(values), 3),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=Path("evidence/benchmark.json"))
    args = parser.parse_args()
    if not 1 <= args.rows <= 10000:
        raise SystemExit("rows must be 1..10000")
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        database_url = os.environ.get("BENCHMARK_DATABASE_URL", f"sqlite:///{root / 'bench.db'}")
        service = Reconciler(database_url, FileArchive(root / "raw"))
        prefix = str(time.time_ns())
        body = json.dumps(
            {
                "payments": [
                    {"payment_id": f"{prefix}-{i}", "currency": "USD", "amount": "100.00"}
                    for i in range(args.rows)
                ]
            }
        ).encode()
        start = time.perf_counter()
        first = service.ingest("payments", "benchmark", body)
        ingestion_ms = (time.perf_counter() - start) * 1000
        csv = "row_id,payment_id,currency,net_amount,fee,settled_at\n" + "\n".join(
            f"{prefix}-{i},{prefix}-{i},USD,99,1,2026-10-30T10:00:00Z" for i in range(args.rows)
        )
        start = time.perf_counter()
        service.ingest("statement", "benchmark-bank", csv.encode())
        statement_ms = (time.perf_counter() - start) * 1000
        queries, replays = [], []
        for _ in range(30):
            start = time.perf_counter()
            rows = service.reconcile()
            queries.append((time.perf_counter() - start) * 1000)
            start = time.perf_counter()
            assert service.ingest("payments", "benchmark", body)["replayed"]
            replays.append((time.perf_counter() - start) * 1000)
        assert (
            sum(r["status"] == "matched" and r["payment_id"].startswith(prefix) for r in rows)
            == args.rows
        )
        start = time.perf_counter()
        quarantined = service.ingest("statement", "broken-bank", b"corrupt")
        detected_ms = (time.perf_counter() - start) * 1000
        service.engine.dispose()
        recovered = Reconciler(database_url, service.archive)
        start = time.perf_counter()
        replay = recovered.ingest("payments", "benchmark", body)
        recovery_ms = (time.perf_counter() - start) * 1000
        assert replay["batch_id"] == first["batch_id"]
        assert quarantined["status"] == "quarantined"
        report = {
            "recorded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "database": recovered.engine.dialect.name,
            "rows": args.rows,
            "payment_ingestion_ms": round(ingestion_ms, 3),
            "statement_ingestion_ms": round(statement_ms, 3),
            "reconciliation": summary(queries),
            "replay": summary(replays),
            "malformed_batch_detection_ms": round(detected_ms, 3),
            "restart_replay_ms": round(recovery_ms, 3),
            "correctness": {
                "matched_rows": args.rows,
                "replay_same_batch": True,
                "bad_batch_quarantined": True,
            },
            "methodology": (
                "One local process, cold insert then 30 warm queries/replays; no network load, "
                "percentile nearest lower rank. Not a production SLA."
            ),
        }
        recovered.engine.dispose()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
