"""Bounded, reproducible cash-flow stress analysis; no trades or data writes.

Quotes are currency units per EUR. A shock changes a currency's value in
reporting units, not the inverse published quote. No probability is inferred.
"""

import hashlib
import json
from collections import defaultdict
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from fractions import Fraction
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$", strict=True)]
Money = Annotated[str, Field(pattern=r"^(0|[1-9][0-9]{0,12})(\.[0-9]{1,6})?$", strict=True)]
BasisPoints = Annotated[int, Field(strict=True, ge=-9000, le=9000)]


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,32}$", strict=True)
    currency: Currency
    direction: Literal["receivable", "payable"]
    amount: Money

    @field_validator("amount")
    @classmethod
    def bounded_amount(cls, value):
        if not 0 < Decimal(value) <= Decimal("1000000000000"):
            raise ValueError("Amount must be positive and at most one trillion")
        return value


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=40, strict=True)
    shocks_bps: dict[Currency, BasisPoints] = Field(min_length=1, max_length=30)

    @field_validator("name")
    @classmethod
    def visible_name(cls, value):
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("Scenario name must be visible text")
        return value.strip()


class StressRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reporting_currency: Currency = "EUR"
    positions: list[Position] = Field(min_length=1, max_length=50)
    scenarios: list[Scenario] = Field(min_length=1, max_length=8)
    net_limit: Money | None = None

    @field_validator("net_limit")
    @classmethod
    def bounded_limit(cls, value):
        if value is not None and Decimal(value) > Decimal("1000000000000"):
            raise ValueError("Limit must be at most one trillion")
        return value

    @model_validator(mode="after")
    def unique_identifiers(self):
        if len({row.id for row in self.positions}) != len(self.positions):
            raise ValueError("Cash-flow IDs must be unique")
        if len({row.name for row in self.scenarios}) != len(self.scenarios):
            raise ValueError("Scenario names must be unique")
        return self


def fingerprint(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def parse_request(raw: bytes | bytearray) -> StressRequest:
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(_value):
        raise ValueError("Nonfinite JSON constant")

    return StressRequest.model_validate(
        json.loads(raw, object_pairs_hook=unique_keys, parse_constant=invalid_constant)
    )


def decimal_text(value):
    # Rational valuation remains exact internally; only display division is rounded.
    if isinstance(value, Fraction):
        with localcontext() as context:
            context.prec = 50
            context.rounding = ROUND_HALF_EVEN
            value = Decimal(value.numerator) / Decimal(value.denominator)
    # Fixed-point strings, never scientific notation or binary floating point.
    return (
        "0"
        if value == 0
        else format(value, "f").rstrip("0").rstrip(".")
        if "." in format(value, "f")
        else format(value, "f")
    )


def analyze(snapshot: dict, request: StressRequest) -> dict:
    """Value supplied assumptions using one immutable reference observation.

    Valuations and differences use exact rational arithmetic from decimal inputs.
    Recurring report values are rendered to 50 significant digits, half-even.
    Report fingerprints identify content; they are not a digital signature.
    """
    if snapshot.get("status") != "captured":
        raise ValueError("Capture public reference rates before analysis")
    observation = snapshot["observation"]
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        quotes = {
            "EUR": Fraction(1),
            **{code: Fraction(Decimal(str(value))) for code, value in observation["rates"].items()},
        }
        used = {row.currency for row in request.positions} | {request.reporting_currency}
        used |= {code for scenario in request.scenarios for code in scenario.shocks_bps}
        if not used.issubset(quotes) or any(q <= 0 for q in quotes.values()):
            raise ValueError("Currency unavailable or reference quote invalid")
        if any(s.shocks_bps.get(request.reporting_currency, 0) for s in request.scenarios):
            raise ValueError("The reporting currency cannot be shocked against itself")
        groups = defaultdict(lambda: {"receivable": Fraction(0), "payable": Fraction(0), "ids": []})
        for position in request.positions:
            group = groups[position.currency]
            group[position.direction] += Fraction(Decimal(position.amount))
            group["ids"].append(position.id)
        rates = {code: quotes[request.reporting_currency] / quotes[code] for code in groups}
        receivables = sum(
            (group["receivable"] * rates[code] for code, group in groups.items()), Fraction(0)
        )
        payables = sum(
            (group["payable"] * rates[code] for code, group in groups.items()), Fraction(0)
        )
        gross, net = receivables + payables, receivables - payables
        limit = None if request.net_limit is None else Fraction(Decimal(request.net_limit))
        exposures, hhi = [], Fraction(0)
        for code, group in sorted(groups.items()):
            native = group["receivable"] - group["payable"]
            gross_value = (group["receivable"] + group["payable"]) * rates[code]
            share = gross_value / gross
            hhi += share * share
            exposures.append(
                {
                    "currency": code,
                    "position_ids": group["ids"],
                    "receivable_native": decimal_text(group["receivable"]),
                    "payable_native": decimal_text(group["payable"]),
                    "net_native": decimal_text(native),
                    "valuation_rate": decimal_text(rates[code]),
                    "net_reporting": decimal_text(native * rates[code]),
                    "gross_reporting": decimal_text(gross_value),
                    "gross_share": decimal_text(share),
                }
            )
        scenarios, losses = [], []
        for scenario in request.scenarios:
            contributions, total = [], Fraction(0)
            for code, group in sorted(groups.items()):
                baseline = (group["receivable"] - group["payable"]) * rates[code]
                shock = scenario.shocks_bps.get(code, 0)
                stressed = baseline * (1 + Fraction(shock, 10000))
                total += stressed
                contributions.append(
                    {
                        "currency": code,
                        "shock_bps": shock,
                        "baseline": decimal_text(baseline),
                        "stressed": decimal_text(stressed),
                        "delta": decimal_text(stressed - baseline),
                    }
                )
            losses.append(max(Fraction(0), net - total))
            scenarios.append(
                {
                    "name": scenario.name,
                    "shocks_bps": dict(sorted(scenario.shocks_bps.items())),
                    "net": decimal_text(total),
                    "delta": decimal_text(total - net),
                    "limit_breached": limit is not None and abs(total) > limit,
                    "contributions": contributions,
                }
            )
        report = {
            "schema_version": 1,
            "reporting_currency": request.reporting_currency,
            "position_count": len(request.positions),
            "source": {key: snapshot[key] for key in ("source", "digest", "captured_at")},
            "observation_date": observation["date"],
            "request_digest": fingerprint(request.model_dump()),
            "assumptions": request.model_dump(),
            "baseline": {
                "receivables": decimal_text(receivables),
                "payables": decimal_text(payables),
                "gross": decimal_text(gross),
                "net": decimal_text(net),
                "gross_concentration_hhi": decimal_text(hhi),
                "net_limit": request.net_limit,
                "limit_breached": limit is not None and abs(net) > limit,
            },
            "exposures": exposures,
            "scenarios": scenarios,
            "worst_loss": decimal_text(max(losses)),
            "method": {
                "kind": "deterministic_hypothetical_stress",
                "precision_digits": 50,
                "shock_definition": (
                    "Change in currency value measured in reporting-currency units; 100bps = 1%"
                ),
                "concentration": "HHI of gross absolute cash flows by currency, not net portfolio",
                "limitations": [
                    "User-authored assumptions; no actual payment or bank-feed data",
                    "One dated reference observation; not a forecast, VaR or execution price",
                    "No fees, maturity buckets, hedges, correlation or liquidity modeling",
                    "Exact rational valuation; recurring output rounded to 50 significant digits",
                    "Content hashes are reproducibility checks, not digital signatures",
                    "Inputs and reports are not persisted or sent to an AI provider",
                ],
            },
        }
        report["report_digest"] = fingerprint(report)
        return report
