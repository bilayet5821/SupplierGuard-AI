from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Decision(str, Enum):
    APPROVE = "Approve"
    REJECT = "Reject"
    HUMAN_REVIEW = "Needs Human Review"


class CheckStatus(str, Enum):
    PASS = "Pass"
    REJECT = "Reject"
    HUMAN_REVIEW = "Needs Human Review"


class Evidence(BaseModel):
    page: int = Field(ge=1)
    quote: str = Field(min_length=1)


class PageText(BaseModel):
    page: int = Field(ge=1)
    text: str


class PdfDocument(BaseModel):
    source_path: str
    source_file: str
    pages: list[PageText]


class PurchaseRequestLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    pr_number: str
    item_code: str
    description: str
    unit: str
    quantity_requested: Decimal
    maximum_unit_price_bdt: Decimal


class QuotedItem(BaseModel):
    item_code: str
    description: str
    quantity: Decimal
    unit: str
    unit_price_bdt: Decimal
    amount_bdt: Decimal


class Terms(BaseModel):
    advance_percent: Decimal | None = None
    payment_days_min: int | None = None
    payment_days_max: int | None = None
    payment_is_clear: bool = False
    delivery_days: int | None = None
    late_penalty_percent_per_week: Decimal | None = None
    late_penalty_mentions_order_value: bool = False
    late_penalty_clause_present: bool = False
    validity_days: int | None = None


class ExtractedSupplierPack(BaseModel):
    source_file: str
    supplier_name: str | None = None
    quotation_number: str | None = None
    quotation_date: str | None = None
    reference: str | None = None
    items: list[QuotedItem] = Field(default_factory=list)
    subtotal_bdt: Decimal | None = None
    vat_percent: Decimal | None = None
    vat_amount_bdt: Decimal | None = None
    total_bdt: Decimal | None = None
    tin: str | None = None
    bin: str | None = None
    terms: Terms = Field(default_factory=Terms)
    evidence: dict[str, list[Evidence]] = Field(default_factory=dict)
    uncertainties: list[str] = Field(default_factory=list)


class RuleFinding(BaseModel):
    rule_id: str
    rule: str
    status: CheckStatus
    explanation: str
    evidence: list[Evidence] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    source_file: str
    decision: Decision
    decision_reason: str
    extracted: ExtractedSupplierPack
    findings: list[RuleFinding]

    @property
    def exceptions(self) -> list[RuleFinding]:
        return [finding for finding in self.findings if finding.status != CheckStatus.PASS]
