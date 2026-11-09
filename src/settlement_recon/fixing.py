"""Bounded historical reference valuation with exact arithmetic and no look-ahead."""

import json
import re
from bisect import bisect_right
from datetime import date
from fractions import Fraction

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from settlement_recon.history import Archive
from settlement_recon.treasury import Currency, Money, decimal_text, fingerprint


class FixingRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$", strict=True)
    currency: Currency
    amount: Money
    date: date

    @field_validator("date", mode="before")
    @classmethod
    def iso_date(cls, value):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("Use an ISO calendar date")
        return date.fromisoformat(value)

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, value):
        if not 0 < Fraction(value) <= 10**12:
            raise ValueError("Amount must be positive and at most one trillion")
        return value


class FixingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_currency: Currency
    rounding_places: int = Field(ge=0, le=6, strict=True)
    max_quote_age_days: int = Field(ge=0, le=10, strict=True)
    records: list[FixingRecord] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def distinct_ids(self):
        if len({row.id for row in self.records}) != len(self.records):
            raise ValueError("Record IDs must be unique")
        return self


def parse_fixing(raw: bytes | bytearray) -> FixingRequest:
    def unique_keys(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("Duplicate JSON key")
            obj[key] = value
        return obj

    def invalid_constant(_value):
        raise ValueError("Nonfinite JSON constant")

    return FixingRequest.model_validate(
        json.loads(raw, object_pairs_hook=unique_keys, parse_constant=invalid_constant)
    )


def rounded_units(value: Fraction, places: int) -> int:
    """Half-even rounding on integers, including exact ties of recurring fractions."""
    units, remainder = divmod(abs(value.numerator) * 10**places, value.denominator)
    if remainder * 2 > value.denominator or (remainder * 2 == value.denominator and units % 2):
        units += 1
    return units if value >= 0 else -units


def fixed_units(units: int, places: int) -> str:
    sign = "-" if units < 0 else ""
    digits = str(abs(units)).zfill(places + 1)
    return sign + (digits if not places else digits[:-places] + "." + digits[-places:])


def value_at_fixing(archive: Archive, request: FixingRequest) -> dict:
    """Compute visitor-authored amounts against immutable actual published quotes.

    No estimate is made for missing/stale rates. A partial subtotal can never be
    mistaken for a complete total. Fingerprints identify content, not authenticity.
    """
    used = {row.currency for row in request.records} | {request.target_currency}
    if not used.issubset(archive.currencies):
        raise ValueError("Currency unavailable in the fixed ECB archive")
    columns = {code: archive.currencies.index(code) for code in used}
    results, subtotal, rounded_sum, valued = [], Fraction(0), 0, 0
    for record in request.records:
        row = record.model_dump(mode="json")
        identity = record.currency == request.target_currency
        rate, chosen = (Fraction(1) if identity else None), None
        if not identity:
            last = bisect_right(archive.dates, record.date) - 1
            for index in range(last, -1, -1):
                quotes = archive.rows[index]
                source, target = (
                    quotes[columns[record.currency]],
                    quotes[columns[request.target_currency]],
                )
                if source != "N/A" and target != "N/A":
                    chosen = archive.dates[index]
                    rate = Fraction(target) / Fraction(source)
                    row.update(source_units_per_eur=source, target_units_per_eur=target)
                    break
        row.update(
            quote_date=chosen.isoformat() if chosen else None,
            quote_age_days=(record.date - chosen).days if chosen else None,
            method="identity"
            if identity
            else "latest published paired quote on or before record date",
        )
        if rate is None:
            row.update(status="unavailable", reason="No prior paired quote in the retained archive")
        elif chosen and (record.date - chosen).days > request.max_quote_age_days:
            row.update(
                status="stale",
                reason="Last available paired quote exceeds the chosen calendar-day age limit",
            )
        else:
            exact = Fraction(record.amount) * rate
            units = rounded_units(exact, request.rounding_places)
            row.update(
                status="valued",
                rate=decimal_text(rate),
                rate_numerator=rate.numerator,
                rate_denominator=rate.denominator,
                value_numerator=exact.numerator,
                value_denominator=exact.denominator,
                rounded_value=fixed_units(units, request.rounding_places),
            )
            subtotal += exact
            rounded_sum += units
            valued += 1
        results.append(row)
    exact_units = rounded_units(subtotal, request.rounding_places)
    complete = valued == len(results)
    result = {
        "schema_version": 1,
        "status": "complete" if complete else "incomplete",
        "source": archive.source(),
        "input": request.model_dump(mode="json"),
        "target_currency": request.target_currency,
        "valued_count": valued,
        "unvalued_count": len(results) - valued,
        "complete_total": fixed_units(exact_units, request.rounding_places) if complete else None,
        "rounded_exact_subtotal": fixed_units(exact_units, request.rounding_places),
        "sum_rounded_rows": fixed_units(rounded_sum, request.rounding_places),
        "rounding_difference": fixed_units(exact_units - rounded_sum, request.rounding_places),
        "records": results,
        "policy": {
            "rounding": "ROUND_HALF_EVEN using exact integer division",
            "rounding_places": request.rounding_places,
            "max_quote_age_days": request.max_quote_age_days,
            "date_basis": "Calendar days; no holiday calendar or missing-date fill",
            "amounts": "Visitor-authored inputs; not imported customer payments",
            "precision": "Visitor-chosen reporting precision, not a regulatory currency rule",
            "boundary": "Historical ECB reference observations, not executable rates "
            "or evidence of bank settlement",
        },
    }
    result["report_sha256"] = fingerprint(result)
    return result
