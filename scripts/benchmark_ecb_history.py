"""Benchmark fixed ECB source bytes and verify every replayed rate against raw CSV."""

import argparse
import csv
import io
import json
import math
import platform
import statistics
import sys
import time
import zipfile
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from settlement_recon.history import ARCHIVE_PATH, ARCHIVE_SHA256, parse_archive, replay  # noqa: E402

PAIRS = (
    ("EUR", "USD"),
    ("USD", "INR"),
    ("GBP", "JPY"),
    ("CHF", "USD"),
    ("USD", "GBP"),
    ("USD", "JPY"),
    ("USD", "CHF"),
    ("CAD", "USD"),
)


def measure() -> dict:
    raw = ARCHIVE_PATH.read_bytes()
    parse_ms = []
    for _ in range(5):
        started = time.perf_counter()
        archive = parse_archive(raw, ARCHIVE_SHA256)
        parse_ms.append((time.perf_counter() - started) * 1000)
    with zipfile.ZipFile(io.BytesIO(raw)) as source_zip:
        text = source_zip.read("eurofxref-hist.csv").decode("ascii")
    published = sorted(csv.DictReader(io.StringIO(text)), key=lambda row: row["Date"])
    calendar_years = range(archive.dates[0].year, archive.dates[-1].year + 1)
    replay_ms, pair_counts = [], {}
    for left, right in PAIRS:
        pair = f"{left}/{right}"
        pair_counts[pair] = 0
        for year in calendar_years:
            expected = {}
            for row in published:
                if not row["Date"].startswith(str(year)):
                    continue
                x = "1" if left == "EUR" else row[left]
                y = "1" if right == "EUR" else row[right]
                if x != "N/A" and y != "N/A":
                    expected[row["Date"]] = (x, y)
            if not expected:
                continue
            started = time.perf_counter()
            result = replay(archive, left, right, date(year, 1, 1), date(year, 12, 31))
            replay_ms.append((time.perf_counter() - started) * 1000)
            observed = result["observations"]
            assert [row["date"] for row in observed] == list(expected), (pair, year)
            with localcontext() as context:
                context.prec = 80
                for row in observed:
                    x, y = expected[row["date"]]
                    assert row["source_units_per_eur"] == x and row["target_units_per_eur"] == y
                    assert row["numerator"] * Decimal(x) == row["denominator"] * Decimal(y)
            pair_counts[pair] += len(observed)
    return {
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor(),
        "archive": archive.source(),
        "archive_zip_bytes": len(raw),
        "verified_pair_observations": sum(pair_counts.values()),
        "per_pair_observation_counts": pair_counts,
        "archive_parse_samples": len(parse_ms),
        "archive_parse_p50_ms": statistics.median(parse_ms),
        "replay_window_samples": len(replay_ms),
        "replay_window_p50_ms": statistics.median(replay_ms),
        "replay_window_p95_ms": sorted(replay_ms)[math.ceil(len(replay_ms) * 0.95) - 1],
        "replay_window_max_ms": max(replay_ms),
        "timing_scope": "Local in-process engine; excludes network, source download and oracle.",
        "oracle": "Independent CSV parse, matching dates and quotes, and exact cross-products.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    evidence = json.dumps(measure(), indent=2) + "\n"
    if args.output:
        args.output.write_text(evidence, encoding="utf-8")
    print(evidence, end="")
