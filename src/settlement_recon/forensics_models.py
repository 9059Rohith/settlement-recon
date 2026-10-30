"""Strict, bounded contracts for advisory unlinked-settlement investigations."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Currency = Literal["USD", "EUR", "GBP", "INR", "JPY"]
Identifier = Annotated[
    str, Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
]
Minor = Annotated[int, Field(ge=0, le=10**15)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ObservedRecord(StrictModel):
    currency: Currency
    reference: str | None = Field(default=None, max_length=96, pattern=r"^[A-Za-z0-9 ._:/-]+$")

    @field_validator("reference")
    @classmethod
    def meaningful_reference(cls, value):
        if value is not None and not any(character.isalnum() for character in value):
            raise ValueError("Reference must contain an ASCII letter or digit")
        return value

    @staticmethod
    def calendar_date(value):
        if value is None or type(value) is date:
            return value
        if isinstance(value, datetime) or not isinstance(value, str):
            raise ValueError("Use a canonical calendar date")
        try:
            result = date.fromisoformat(value)
        except ValueError:
            raise ValueError("Use a canonical calendar date") from None
        if result.isoformat() != value:
            raise ValueError("Use a canonical calendar date")
        return result


class PaymentClaim(ObservedRecord):
    payment_id: Identifier
    amount_minor: int = Field(ge=1, le=10**15)
    expected_on: date | None = None

    @field_validator("expected_on", mode="before")
    @classmethod
    def parse_date(cls, value):
        return cls.calendar_date(value)


class UnlinkedLeg(ObservedRecord):
    leg_id: Identifier
    net_minor: Minor
    fee_minor: Minor
    settled_on: date | None = None

    @field_validator("settled_on", mode="before")
    @classmethod
    def parse_date(cls, value):
        return cls.calendar_date(value)

    @model_validator(mode="after")
    def positive_total(self):
        if not 1 <= self.net_minor + self.fee_minor <= 10**15:
            raise ValueError("A bank leg must have a positive bounded total")
        return self


class ForensicsPolicy(StrictModel):
    tolerance_minor: int = Field(default=0, ge=0, le=10_000)
    max_split: int = Field(default=2, ge=1, le=3)
    max_lag_days: int = Field(default=7, ge=0, le=31)
    require_reference_agreement: bool = True
    require_complete_reference: bool = False
    require_date_evidence: bool = False
    max_states: int = Field(default=50_000, ge=1, le=50_000)


class ForensicsRequest(StrictModel):
    payments: list[PaymentClaim] = Field(min_length=1, max_length=24)
    legs: list[UnlinkedLeg] = Field(max_length=32)
    policy: ForensicsPolicy = Field(default_factory=ForensicsPolicy)

    @model_validator(mode="after")
    def unique_identifiers(self):
        if len({row.payment_id for row in self.payments}) != len(self.payments):
            raise ValueError("Duplicate payment identifier")
        if len({row.leg_id for row in self.legs}) != len(self.legs):
            raise ValueError("Duplicate bank-leg identifier")
        return self


ReferenceEvidence = Literal["exact", "missing", "conflict_allowed"]
DecisionStatus = Literal["unique", "ambiguous", "unmatched", "capacity_exceeded", "budget_exceeded"]


class AllocationSuggestion(StrictModel):
    payment_id: Identifier
    currency: Currency
    leg_ids: list[Identifier] = Field(min_length=1, max_length=3)
    expected_minor: int
    settled_minor: int
    difference_minor: int
    reference_evidence: ReferenceEvidence
    max_lag_days: int | None
    date_evidence_complete: bool


class AllocationDecision(StrictModel):
    payment_id: Identifier
    status: DecisionStatus
    candidates: int = Field(ge=0)
    alternatives: list[list[Identifier] | None] = Field(max_length=5)
    alternatives_truncated: bool


class ComponentCertificate(StrictModel):
    payment_ids: list[Identifier] = Field(max_length=24)
    leg_ids: list[Identifier] = Field(max_length=32)
    status: Literal["complete", "capacity_exceeded", "budget_exceeded"]
    objective: list[int] | None
    optimal_allocations: int | None
    allocation_count_capped: bool


class ForensicsReport(StrictModel):
    version: Literal["settlement-forensics-v1"]
    advisory_only: Literal[True]
    complete: bool
    request_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    policy_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    objective_order: list[str]
    candidates_considered: int
    combination_checks: int
    search_states: int
    elapsed_ms: float
    components: list[ComponentCertificate]
    decisions: list[AllocationDecision]
    suggestions: list[AllocationSuggestion]
    limitations: list[str]


class PaymentResidualProvenance(StrictModel):
    payment_id: Identifier
    original_amount_minor: int
    recorded_settled_minor: int
    batch_id: str
    checksum: str


class BankLegProvenance(StrictModel):
    leg_id: Identifier
    source: Identifier
    row_id: Identifier
    batch_id: str
    checksum: str


class CaseProvenance(StrictModel):
    snapshot: Literal["repeatable-read", "sqlite-read-transaction"]
    source: Identifier
    payments: list[PaymentResidualProvenance]
    legs: list[BankLegProvenance]
    archive_integrity_checked: Literal[False]


class ForensicsCase(StrictModel):
    case: ForensicsRequest
    provenance: CaseProvenance
    warnings: list[str]
