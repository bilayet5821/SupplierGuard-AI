from __future__ import annotations

import re

from .models import CheckStatus, Decision, EvaluationResult, Evidence, RuleFinding


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
}


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
