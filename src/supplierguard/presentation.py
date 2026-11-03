from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal

from .models import (
    CheckStatus,
    Decision,
    EvaluationResult,
    Evidence,
    PurchaseRequestLine,
    RuleFinding,
)


RULE_LABELS = {
    "SAFE-001": "Extraction certainty",
    "PR-001": "Purchase request match",
    "PRICE-001": "Unit price limit",
    "QTY-001": "Quoted quantity",
    "PAY-ADV-001": "Advance payment",
    "PAY-TERM-001": "Payment timing",
    "PENALTY-001": "Late-delivery protection",
    "ID-001": "Supplier tax registrations",
    "DELIVERY-001": "Delivery lead time",
    "VAT-001": "VAT presentation",
    "MATH-001": "Quote arithmetic",
    "VALIDITY-001": "Quotation validity",
    "UPLOAD-MULTI-ITEM": "Uploaded document structure",
}


@dataclass(frozen=True)
class IssueDetail:
    rule_id: str
    status: CheckStatus
    issue_name: str
    actual_value: str
    policy_requirement: str
    measured_difference: str
    action: str

    def as_dict(self) -> dict[str, str]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


def decision_status(result: EvaluationResult) -> CheckStatus:
    return {
        Decision.APPROVE: CheckStatus.PASS,
        Decision.REJECT: CheckStatus.REJECT,
        Decision.HUMAN_REVIEW: CheckStatus.HUMAN_REVIEW,
    }[result.decision]


def decision_drivers(
    result: EvaluationResult,
    limit: int = 2,
) -> list[RuleFinding]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    status = decision_status(result)
    return [finding for finding in result.findings if finding.status == status][:limit]


def business_summary(result: EvaluationResult) -> str:
    if result.decision == Decision.APPROVE:
        return "All required compliance checks passed. No rejection or manual-review conditions were found."

    drivers = decision_drivers(result, limit=2)
    lead = "Rejected" if result.decision == Decision.REJECT else "Manual review required"
    reasons = "; ".join(business_explanation(finding).rstrip(".") for finding in drivers)
    same_status_count = sum(
        finding.status == decision_status(result) for finding in result.findings
    )
    remainder = same_status_count - len(drivers)
    suffix = f" Plus {remainder} additional decision driver(s)." if remainder else "."
    return f"{lead}: {reasons}{suffix}"


def recommended_next_action(decision: Decision) -> str:
    return {
        Decision.APPROVE: (
            "Continue the normal purchase-order authorization process and complete the usual "
            "commercial and quality checks. This system result is not a recorded human approval."
        ),
        Decision.REJECT: (
            "Do not issue a purchase order against this quotation. Ask the supplier or sourcing "
            "team for a corrected document, then run the revised document through SupplierGuard again."
        ),
        Decision.HUMAN_REVIEW: (
            "Pause purchase-order processing. A purchasing or compliance reviewer should verify "
            "every flagged issue against the supplier document before deciding whether to proceed."
        ),
    }[decision]


def issue_details(
    result: EvaluationResult,
    purchase_request: dict[str, PurchaseRequestLine],
) -> list[IssueDetail]:
    """Build evidence-grounded procurement actions without changing compliance logic."""
    pack = result.extracted
    item = pack.items[0] if len(pack.items) == 1 else None
    requested = purchase_request.get(item.item_code) if item else None
    details: list[IssueDetail] = []

    for finding in result.exceptions:
        actual = finding.explanation
        policy = finding.rule
        difference = "See finding explanation."
        action = "A purchasing or compliance reviewer should verify this issue before proceeding."

        if finding.rule_id == "PRICE-001" and item and requested:
            delta = item.unit_price_bdt - requested.maximum_unit_price_bdt
            percent = delta / requested.maximum_unit_price_bdt * Decimal("100")
            actual = f"Quoted unit price BDT {item.unit_price_bdt:,.2f}"
            policy = (
                f"Maximum BDT {requested.maximum_unit_price_bdt:,.2f}; more than 3% "
                "above the maximum is rejected."
            )
            difference = f"BDT {delta:,.2f} above maximum ({percent:.2f}%)."
            action = (
                f"Ask the supplier for a revised unit price at or below BDT "
                f"{requested.maximum_unit_price_bdt:,.2f}."
                if finding.status == CheckStatus.REJECT
                else (
                    f"Ask a purchasing officer to accept or decline the {percent:.2f}% price "
                    "exception before issuing the purchase order."
                )
            )
        elif finding.rule_id == "QTY-001" and item and requested:
            delta = item.quantity - requested.quantity_requested
            variance = abs(delta) / requested.quantity_requested * Decimal("100")
            actual = f"Quoted quantity {item.quantity:,.0f} {item.unit}"
            policy = (
                f"Requested quantity {requested.quantity_requested:,.0f} {requested.unit}; "
                "variance above 5% requires review."
            )
            difference = f"{abs(delta):,.0f} {item.unit} ({variance:.2f}% variance)."
            action = (
                f"Ask procurement to confirm the {item.quantity:,.0f} quoted quantity or "
                f"request a corrected quotation for {requested.quantity_requested:,.0f} {requested.unit}."
            )
        elif finding.rule_id == "PAY-ADV-001":
            advance = pack.terms.advance_percent
            actual = "Advance percentage unclear" if advance is None else f"{advance}% advance"
            policy = "Advance payment must not exceed 20%."
            difference = (
                "Cannot be calculated from the document."
                if advance is None
                else f"{max(advance - Decimal('20'), Decimal('0'))}% above the limit."
            )
            action = (
                "Ask the supplier to state the advance percentage clearly."
                if advance is None
                else "Ask the supplier to revise the advance payment to 20% or less."
            )
        elif finding.rule_id == "PAY-TERM-001":
            if pack.terms.payment_days_min is None:
                actual = "Payment timing unclear"
            else:
                actual = (
                    f"{pack.terms.payment_days_min}-{pack.terms.payment_days_max} days after delivery"
                )
            policy = "Payment must be clearly due 30-60 days after delivery."
            difference = "Terms are unclear or extend outside the permitted range."
            action = "Request clarified payment terms within 30-60 days after delivery."
        elif finding.rule_id == "PENALTY-001":
            rate = pack.terms.late_penalty_percent_per_week
            if not pack.terms.late_penalty_clause_present:
                actual = "No late-delivery penalty clause found"
            elif rate is None:
                actual = "Penalty clause found, but the weekly rate is unclear"
            else:
                basis = "of order value" if pack.terms.late_penalty_mentions_order_value else "basis unclear"
                actual = f"{rate}% per week ({basis})"
            policy = "At least 0.5% of order value per week of delay is required."
            difference = finding.explanation
            action = (
                "Request a late-delivery clause stating at least 0.5% of order value per week of delay."
            )
        elif finding.rule_id == "ID-001":
            missing = [name for name, value in (("TIN", pack.tin), ("BIN", pack.bin)) if not value]
            actual = f"Missing {' and '.join(missing)}"
            policy = "Both supplier TIN and BIN must be shown."
            difference = f"{len(missing)} required registration identifier(s) missing."
            action = f"Request and verify the supplier {' and '.join(missing)} before proceeding."
        elif finding.rule_id == "DELIVERY-001":
            days = pack.terms.delivery_days
            actual = "Delivery lead time unclear" if days is None else f"{days} days after PO"
            policy = "Up to 30 days passes; 31-45 days requires review; over 45 days is rejected."
            difference = (
                "Cannot be calculated from the document."
                if days is None
                else f"{max(days - 45, 0)} day(s) beyond the rejection threshold."
            )
            action = (
                "Ask the supplier for a revised delivery lead time of 45 days or less."
                if days is not None and days > 45
                else "Ask a purchasing officer to confirm whether the stated delivery lead time is acceptable."
            )
        elif finding.rule_id == "VAT-001":
            actual = (
                "VAT not separately shown"
                if pack.vat_percent is None or pack.vat_amount_bdt is None
                else f"VAT shown at {pack.vat_percent}%"
            )
            policy = "VAT must be separately itemized at 15%."
            difference = finding.explanation
            action = "Request a revised quotation with 15% VAT shown as a separate amount."
        elif finding.rule_id == "MATH-001":
            actual = finding.explanation
            policy = "Line amount, subtotal, VAT, and total must add up correctly."
            difference = finding.explanation
            action = "Ask the supplier for a corrected quotation with internally consistent calculations."
        elif finding.rule_id == "VALIDITY-001":
            days = pack.terms.validity_days
            actual = "Validity unclear" if days is None else f"Valid for {days} days"
            policy = "Quotation validity must be at least 30 days."
            difference = (
                "Cannot be calculated from the document."
                if days is None
                else f"{max(30 - days, 0)} day(s) below the requirement."
            )
            action = "Request a quotation validity period of at least 30 days."
        elif finding.rule_id == "PR-001":
            codes = ", ".join(quoted.item_code for quoted in pack.items) or "No item extracted"
            actual = f"Quoted item code(s): {codes}"
            policy = "Every quoted item must match an item in PR-2026-114."
            difference = finding.explanation
            action = "Ask a purchasing officer to identify the correct purchase-request item before proceeding."
        elif finding.rule_id == "SAFE-001":
            actual = finding.explanation
            policy = "Required values must be extracted reliably; uncertain values are never guessed."
            difference = "Reliable comparison was not possible."
            action = "Escalate the original document to a human reviewer and verify all missing or ambiguous fields."
        elif finding.rule_id == "UPLOAD-MULTI-ITEM":
            count_match = re.search(r"(\d+) line items", finding.explanation)
            count = int(count_match.group(1)) if count_match else len(pack.items)
            actual = f"{count} line items detected"
            policy = "The upload path supports one supplier-pack item per document."
            difference = "Uploaded structure is outside the verified single-item format."
            action = "Split the quotation into one item per document or ask a human reviewer to assess every line item."

        details.append(
            IssueDetail(
                rule_id=finding.rule_id,
                status=finding.status,
                issue_name=rule_label(finding.rule_id),
                actual_value=actual,
                policy_requirement=policy,
                measured_difference=difference,
                action=action,
            )
        )
    return details


def recommendations_for_result(
    result: EvaluationResult,
    purchase_request: dict[str, PurchaseRequestLine],
) -> list[str]:
    details = issue_details(result, purchase_request)
    if not details:
        return [recommended_next_action(Decision.APPROVE)]
    priority = {CheckStatus.REJECT: 0, CheckStatus.HUMAN_REVIEW: 1, CheckStatus.PASS: 2}
    return [detail.action for detail in sorted(details, key=lambda detail: priority[detail.status])]


def rule_label(rule_id: str) -> str:
    return RULE_LABELS.get(rule_id, rule_id.replace("-", " ").title())


def status_label(status: CheckStatus) -> str:
    return {
        CheckStatus.PASS: "PASS — Meets policy",
        CheckStatus.REJECT: "REJECT — Blocks purchase",
        CheckStatus.HUMAN_REVIEW: "REVIEW — Human check needed",
    }[status]


def business_explanation(finding: RuleFinding) -> str:
    """Convert terse validation output into plain procurement language for the UI only."""
    text = finding.explanation
    if finding.rule_id == "PRICE-001":
        match = re.search(
            r"BDT ([\d.]+) is ([\d.]+)% above the BDT ([\d.]+) maximum", text
        )
        if match:
            quoted, percentage, maximum = match.groups()
            return (
                f"Quoted unit price BDT {DecimalText.money(quoted)} is {percentage}% above "
                f"the allowed BDT {DecimalText.money(maximum)} maximum."
            )
    elif finding.rule_id == "QTY-001":
        match = re.search(
            r"Quoted ([\d.]+); requested ([\d.]+); variance ([\d.]+)%", text
        )
        if match:
            quoted, requested, variance = match.groups()
            return (
                f"Quoted quantity {DecimalText.quantity(quoted)} differs from the requested "
                f"{DecimalText.quantity(requested)} by {variance}%."
            )
    elif finding.rule_id == "PAY-ADV-001" and "above 20%" in text:
        match = re.search(r"Advance is ([\d.]+)%", text)
        if match:
            return f"Supplier requests a {match.group(1)}% advance, above the 20% limit."
    elif finding.rule_id == "DELIVERY-001" and "later than 45 days" in text:
        match = re.search(r"Delivery is (\d+) days", text)
        if match:
            return (
                f"Promised delivery is {match.group(1)} days after the purchase order, "
                "beyond the 45-day limit."
            )
    return text


class DecimalText:
    """Small formatting helpers kept independent from compliance calculations."""

    @staticmethod
    def money(value: str) -> str:
        return f"{float(value):,.2f}"

    @staticmethod
    def quantity(value: str) -> str:
        number = float(value)
        return f"{number:,.0f}" if number.is_integer() else f"{number:,.2f}"


def unique_pages(finding: RuleFinding) -> list[int]:
    return sorted({evidence.page for evidence in finding.evidence})


def unique_evidence(finding: RuleFinding) -> list[Evidence]:
    seen: set[tuple[int, str]] = set()
    result: list[Evidence] = []
    for evidence in finding.evidence:
        key = (evidence.page, evidence.quote)
        if key not in seen:
            seen.add(key)
            result.append(evidence)
    return result
