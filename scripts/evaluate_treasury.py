"""Benchmark exact valuation over generated assumptions and a supplied real capture.

Usage: python scripts/evaluate_treasury.py capture.json output.json
The workload is controlled, not actual customer cash flows. No network or writes
other than the explicitly selected output artifact are performed.
"""

import json
import statistics
import sys
import time
from pathlib import Path

from settlement_recon.treasury import StressRequest, analyze


def main():
    snapshot = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    codes = sorted(snapshot["observation"]["rates"])
    request = StressRequest.model_validate(
        {
            "reporting_currency": "EUR",
            "positions": [
                {
                    "id": f"controlled_{index}",
                    "currency": codes[index % len(codes)],
                    "direction": "receivable" if index % 3 else "payable",
                    "amount": "1000000.000001",
                }
                for index in range(50)
            ],
            "scenarios": [
                {"name": f"Controlled {index}", "shocks_bps": {c: (index - 4) * 500 for c in codes}}
                for index in range(8)
            ],
        }
    )
    started = time.perf_counter()
    report = analyze(snapshot, request)
    cold_ms = (time.perf_counter() - started) * 1000
    samples = []
    for _ in range(200):
        started = time.perf_counter()
        repeated = analyze(snapshot, request)
        samples.append((time.perf_counter() - started) * 1000)
        if repeated["report_digest"] != report["report_digest"]:
            raise RuntimeError("Analysis was not deterministic")
    ordered = sorted(samples)
    result = {
        "scope": (
            "Local pure engine, controlled assumptions, real captured reference rates; "
            "excludes HTTP/DB/network"
        ),
        "positions": 50,
        "scenarios": 8,
        "currencies": len(codes),
        "iterations": len(samples),
        "first_ms": cold_ms,
        "p50_ms": statistics.median(samples),
        "p95_ms": ordered[189],
        "p99_ms": ordered[197],
        "source_digest": snapshot["digest"],
        "report_digest": report["report_digest"],
        "request_digest": report["request_digest"],
        "runtime": sys.version,
    }
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
