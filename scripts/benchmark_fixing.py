"""Measure bounded as-of valuation; independently check original ECB CSV values."""

import csv
import io
import json
import statistics
import time
import zipfile
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from fractions import Fraction
from pathlib import Path

from settlement_recon.fixing import FixingRequest, value_at_fixing
from settlement_recon.history import ARCHIVE_PATH, load_archive


def main():
    archive = load_archive()
    with zipfile.ZipFile(ARCHIVE_PATH) as zipped:
        records = list(
            csv.DictReader(io.StringIO(zipped.read("eurofxref-hist.csv").decode("ascii")))
        )
    original = {row["Date"]: row for row in records}
    times, verified, hashes = [], 0, []
    # Unit amounts are analytical conversions, not fabricated payment records.
    codes = ("USD", "GBP", "JPY", "CHF", "AUD", "CAD")
    for start in range(0, 4000, 50):
        rows = [
            {
                "id": f"source-{i}",
                "currency": codes[i % len(codes)],
                "amount": "1",
                "date": archive.dates[i].isoformat(),
            }
            for i in range(start, start + 50)
        ]
        request = FixingRequest.model_validate(
            {
                "target_currency": "EUR",
                "rounding_places": 6,
                "max_quote_age_days": 0,
                "records": rows,
            }
        )
        before = time.perf_counter()
        result = value_at_fixing(archive, request)
        times.append((time.perf_counter() - before) * 1000)
        assert result["status"] == "complete"
        for source, row in zip(rows, result["records"], strict=True):
            quote = original[source["date"]][source["currency"]]
            assert Fraction(row["rate_numerator"], row["rate_denominator"]) == 1 / Fraction(quote)
            with localcontext() as context:
                context.prec = 80
                expected = (1 / Decimal(quote)).quantize(
                    Decimal("0.000001"), rounding=ROUND_HALF_EVEN
                )
            assert row["rounded_value"] == format(expected, "f")
            assert date.fromisoformat(row["quote_date"]) <= date.fromisoformat(source["date"])
            verified += 1
        hashes.append(result["report_sha256"])
    result = {
        "source": archive.source(),
        "verified_records": verified,
        "batches": len(times),
        "batch_size": 50,
        "p50_ms": statistics.median(times),
        "p95_ms": sorted(times)[int(len(times) * 0.95) - 1],
        "maximum_ms": max(times),
        "scope": "Local in-process warm-archive valuation; excludes file load, network, HTTP "
        "and oracle checks. Analytical one-unit conversions, not customer payments.",
        "oracle": "Independent original CSV parse and Decimal precision-80 half-even quantization",
        "report_fingerprints": hashes,
    }
    output = Path("evidence/fixing-benchmark.json")
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({k: v for k, v in result.items() if k not in {"source", "report_fingerprints"}})
    )


if __name__ == "__main__":
    main()
