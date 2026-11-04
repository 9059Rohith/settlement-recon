"""Replay actual ECB reference quotes from an immutable source archive."""

import csv
import hashlib
import io
import re
import zipfile
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

from settlement_recon.treasury import decimal_text, fingerprint

SOURCE_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"
ARCHIVE_SHA256 = "c790546ee569ee4461356cc36b76e312d8f3ca0a4ff9990094ecaeb8f3de5f0c"
ARCHIVE_PATH = Path(__file__).with_name("assets") / "ecb-historical.zip"
MAX_DAYS = 366


@dataclass(frozen=True, slots=True)
class Archive:
    dates: tuple[date, ...]
    currencies: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    archive_sha256: str
    csv_sha256: str

    def source(self) -> dict:
        return {
            "attribution": "Source: ECB statistics.",
            "url": SOURCE_URL,
            "archive_sha256": self.archive_sha256,
            "csv_sha256": self.csv_sha256,
            "publication_dates": len(self.dates),
            "first_date": self.dates[0].isoformat(),
            "last_date": self.dates[-1].isoformat(),
            "currencies": self.currencies,
            "max_calendar_days": MAX_DAYS,
        }


def parse_archive(raw: bytes, expected_sha256: str) -> Archive:
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("ECB archive fingerprint mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        member = archive.getinfo("eurofxref-hist.csv")
        if member.file_size > 3_000_000:
            raise ValueError("ECB CSV exceeds size bound")
        payload = archive.read(member)
    reader = csv.reader(io.StringIO(payload.decode("ascii"), newline=""))
    header = next(reader)
    currencies = ("EUR", *header[1:-1])
    if (
        header[0] != "Date"
        or header[-1] != ""
        or len(set(currencies)) != len(currencies)
        or any(not re.fullmatch(r"[A-Z]{3}", code) for code in currencies)
    ):
        raise ValueError("Unexpected ECB CSV header")
    number = re.compile(r"[0-9]{1,12}(?:\.[0-9]{1,12})?")
    records = []
    for row in reader:
        if len(row) != len(header) or row[-1] != "":
            raise ValueError("Unexpected ECB CSV row")
        quotes = ("1", *row[1:-1])
        if any(
            value != "N/A" and (not number.fullmatch(value) or not value.strip("0."))
            for value in quotes
        ):
            raise ValueError("Invalid ECB reference quote")
        records.append((date.fromisoformat(row[0]), quotes))
    records.sort()
    dates = tuple(item[0] for item in records)
    if not dates or len(set(dates)) != len(dates):
        raise ValueError("Empty ECB archive or duplicate publication date")
    return Archive(
        dates,
        currencies,
        tuple(item[1] for item in records),
        digest,
        hashlib.sha256(payload).hexdigest(),
    )


@lru_cache(maxsize=1)
def load_archive() -> Archive:
    return parse_archive(ARCHIVE_PATH.read_bytes(), ARCHIVE_SHA256)


def replay(archive: Archive, source: str, target: str, start: date, end: date) -> dict:
    if end < start or (end - start).days >= MAX_DAYS:
        raise ValueError("Choose an ordered range of at most 366 calendar days")
    if source not in archive.currencies or target not in archive.currencies:
        raise ValueError("Unknown currency in this ECB archive")
    source_column, target_column = (archive.currencies.index(code) for code in (source, target))
    first, last = bisect_left(archive.dates, start), bisect_right(archive.dates, end)
    observations, moves, values = [], [], []
    previous_rate = previous_date = None
    for index in range(first, last):
        row = archive.rows[index]
        source_eur, target_eur = row[source_column], row[target_column]
        if "N/A" in (source_eur, target_eur):
            continue
        day = archive.dates[index]
        rate = Fraction(target_eur) / Fraction(source_eur)
        change = (rate / previous_rate - 1) * 100 if previous_rate is not None else None
        observations.append(
            {
                "date": day.isoformat(),
                "rate": decimal_text(rate),
                "source_units_per_eur": source_eur,
                "target_units_per_eur": target_eur,
                "numerator": rate.numerator,
                "denominator": rate.denominator,
                "change_percent": decimal_text(change) if change is not None else None,
                "days_since_previous": (day - previous_date).days if previous_date else None,
            }
        )
        if change is not None:
            moves.append((change, day.isoformat()))
        values.append(rate)
        previous_rate, previous_date = rate, day
    if not observations:
        raise ValueError("No observations for these currencies in the requested dates")
    result = {
        "source": archive.source(),
        "from_currency": source,
        "to_currency": target,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "observation_count": len(observations),
        "publication_dates_without_both_quotes": last - first - len(observations),
        "range_change_percent": decimal_text((values[-1] / values[0] - 1) * 100),
        "minimum_rate": decimal_text(min(values)),
        "maximum_rate": decimal_text(max(values)),
        "largest_absolute_move": None,
        "method": "Derived cross-rate: target units per EUR divided by source units per EUR. "
        "Changes compare successive available observations; missing dates are not filled.",
        "observations": observations,
    }
    if moves:
        change, move_date = max(moves, key=lambda item: abs(item[0]))
        result["largest_absolute_move"] = {"date": move_date, "percent": decimal_text(change)}
    result["report_sha256"] = fingerprint(result)
    return result
