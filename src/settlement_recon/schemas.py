"""Machine-readable operational evidence contracts; domain logic stays independent."""

from typing import Literal

from pydantic import BaseModel, Field


class PaymentEvidence(BaseModel):
    amount_minor: int
    batch_id: str
    source: str
    checksum: str


class SettlementEvidence(BaseModel):
    source: str
    row_id: str
    net_minor: int
    fee_minor: int
    settled_at: str
    batch_id: str
    checksum: str


class RuleEvidence(BaseModel):
    id: str
    description: str


class ReconciliationTotals(BaseModel):
    expected_minor: int
    net_minor: int
    fee_minor: int
    settled_minor: int
    difference_minor: int


class SettlementEvidencePage(BaseModel):
    total_rows: int = Field(ge=0)
    returned_rows: int = Field(ge=0, le=100)
    truncated: bool
    records: list[SettlementEvidence] = Field(max_length=100)


class ReconciliationExplanation(BaseModel):
    payment_id: str
    currency: str
    currency_scale: int
    status: Literal["matched", "partial", "missing", "overpaid", "orphan"]
    rule: RuleEvidence
    totals: ReconciliationTotals
    payment: PaymentEvidence | None
    settlements: SettlementEvidencePage
    snapshot: Literal["repeatable-read", "sqlite-read-transaction"]
    archive_integrity_checked: Literal[False]
