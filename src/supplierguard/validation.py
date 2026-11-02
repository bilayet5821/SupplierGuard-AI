from __future__ import annotations

from decimal import Decimal

from .models import (
    CheckStatus,
    Decision,
    EvaluationResult,
    Evidence,
    ExtractedSupplierPack,
    PurchaseRequestLine,
    RuleFinding,
)


ZERO = Decimal("0")
HUNDRED = Decimal("100")


def _finding(
    rule_id: str,
    rule: str,
    status: CheckStatus,
    explanation: str,
    evidence: list[Evidence],
) -> RuleFinding:
    return RuleFinding(
        rule_id=rule_id,
        rule=rule,
        status=status,
        explanation=explanation,
        evidence=evidence,
    )


def _e(pack: ExtractedSupplierPack, key: str) -> list[Evidence]:
    return pack.evidence.get(key, [])


def evaluate_rules(
    pack: ExtractedSupplierPack,
    purchase_request: dict[str, PurchaseRequestLine],
) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    if pack.uncertainties:
        findings.append(
            _finding(
                "SAFE-001",
                "Uncertain required extraction must be reviewed",
                CheckStatus.HUMAN_REVIEW,
                "; ".join(pack.uncertainties),
                _e(pack, "header") + _e(pack, "items"),
            )
        )

    if not pack.items:
        findings.append(
            _finding(
                "PR-001",
                "Quoted items must match the purchase request",
                CheckStatus.HUMAN_REVIEW,
                "No complete item was available for price and quantity comparison.",
                _e(pack, "items"),
            )
        )
    for item in pack.items:
        requested = purchase_request.get(item.item_code)
        item_evidence = _e(pack, "items")
        if requested is None:
            findings.append(
                _finding(
                    "PR-001",
                    "Quoted item must exist in the purchase request",
                    CheckStatus.HUMAN_REVIEW,
                    f"Item {item.item_code} is not in the purchase request.",
                    item_evidence,
                )
            )
            continue

        price_delta = item.unit_price_bdt - requested.maximum_unit_price_bdt
        price_pct = (price_delta / requested.maximum_unit_price_bdt) * HUNDRED
        if price_pct > Decimal("3"):
            price_status = CheckStatus.REJECT
            price_explanation = (
                f"BDT {item.unit_price_bdt} is {price_pct.quantize(Decimal('0.01'))}% "
                f"above the BDT {requested.maximum_unit_price_bdt} maximum (>3%)."
            )
        elif price_delta > ZERO:
            price_status = CheckStatus.HUMAN_REVIEW
            price_explanation = (
                f"BDT {item.unit_price_bdt} is {price_pct.quantize(Decimal('0.01'))}% "
                f"above the BDT {requested.maximum_unit_price_bdt} maximum (at most 3%)."
            )
        else:
            price_status = CheckStatus.PASS
            price_explanation = (
                f"BDT {item.unit_price_bdt} does not exceed the BDT "
                f"{requested.maximum_unit_price_bdt} maximum."
            )
        findings.append(
            _finding(
                "PRICE-001",
                "Apply the maximum unit-price thresholds",
                price_status,
                price_explanation,
                item_evidence,
            )
        )

        quantity_variance = abs(item.quantity - requested.quantity_requested) / requested.quantity_requested
        quantity_status = (
            CheckStatus.HUMAN_REVIEW
            if quantity_variance > Decimal("0.05")
            else CheckStatus.PASS
        )
        findings.append(
            _finding(
                "QTY-001",
                "Quantity variance over 5% needs review",
                quantity_status,
                f"Quoted {item.quantity}; requested {requested.quantity_requested}; "
                f"variance {(quantity_variance * HUNDRED).quantize(Decimal('0.01'))}%.",
                item_evidence,
            )
        )

    terms = pack.terms
    payment_evidence = _e(pack, "payment")
    if terms.advance_percent is None:
        advance_status = CheckStatus.HUMAN_REVIEW
        advance_explanation = "Advance-payment percentage is not clear."
    elif terms.advance_percent > Decimal("20"):
        advance_status = CheckStatus.REJECT
        advance_explanation = f"Advance is {terms.advance_percent}%, above 20%."
    else:
        advance_status = CheckStatus.PASS
        advance_explanation = f"Advance is {terms.advance_percent}%, not above 20%."
    findings.append(
        _finding(
            "PAY-ADV-001",
            "Advance payment must not exceed 20%",
            advance_status,
            advance_explanation,
            payment_evidence,
        )
    )

    payment_in_range = bool(
        terms.payment_is_clear
        and terms.payment_days_min is not None
        and terms.payment_days_max is not None
        and 30 <= terms.payment_days_min <= 60
        and 30 <= terms.payment_days_max <= 60
    )
    payment_status = CheckStatus.PASS if payment_in_range else CheckStatus.HUMAN_REVIEW
    if payment_in_range:
        payment_explanation = (
            f"Payment is due {terms.payment_days_min}–{terms.payment_days_max} days "
            "after delivery, within the inclusive 30–60 day range."
        )
    else:
        payment_explanation = "Payment timing is unclear or extends outside 30–60 days after delivery."
    findings.append(
        _finding(
            "PAY-TERM-001",
            "Payment must be clear and 30–60 days after delivery",
            payment_status,
            payment_explanation,
            payment_evidence,
        )
    )

    delay_evidence = _e(pack, "delay")
    if not terms.late_penalty_clause_present:
        penalty_status = CheckStatus.REJECT
        penalty_explanation = "No late-delivery penalty clause is present."
        delay_evidence = _e(pack, "delivery") + _e(pack, "validity")
    elif (
        terms.late_penalty_percent_per_week is not None
        and terms.late_penalty_percent_per_week < Decimal("0.5")
    ):
        penalty_status = CheckStatus.REJECT
        penalty_explanation = (
            f"Penalty is {terms.late_penalty_percent_per_week}% per week, below 0.5%."
        )
    elif terms.late_penalty_percent_per_week is None:
        penalty_status = CheckStatus.HUMAN_REVIEW
        penalty_explanation = "A penalty clause exists, but its weekly percentage is unclear."
    elif not terms.late_penalty_mentions_order_value:
        penalty_status = CheckStatus.HUMAN_REVIEW
        penalty_explanation = "Penalty percentage is stated, but the order-value basis is unclear."
    else:
        penalty_status = CheckStatus.PASS
        penalty_explanation = (
            f"Penalty is {terms.late_penalty_percent_per_week}% of order value per week."
        )
    findings.append(
        _finding(
            "PENALTY-001",
            "Late-delivery penalty must be at least 0.5% of order value per week",
            penalty_status,
            penalty_explanation,
            delay_evidence,
        )
    )

    if not pack.tin or not pack.bin:
        identifier_status = CheckStatus.REJECT
        missing_names = [name for name, value in (("TIN", pack.tin), ("BIN", pack.bin)) if not value]
        missing = " and ".join(missing_names)
        verb = "are" if len(missing_names) > 1 else "is"
        identifier_explanation = f"Supplier {missing} {verb} missing."
    else:
        identifier_status = CheckStatus.PASS
        identifier_explanation = f"TIN {pack.tin} and BIN {pack.bin} are shown."
    findings.append(
        _finding(
            "ID-001",
            "Supplier TIN and BIN must both be present",
            identifier_status,
            identifier_explanation,
            _e(pack, "identifiers"),
        )
    )

    delivery_evidence = _e(pack, "delivery")
    if terms.delivery_days is None:
        delivery_status = CheckStatus.HUMAN_REVIEW
        delivery_explanation = "Delivery duration after PO is unclear."
    elif terms.delivery_days > 45:
        delivery_status = CheckStatus.REJECT
        delivery_explanation = f"Delivery is {terms.delivery_days} days after PO, later than 45 days."
    elif terms.delivery_days >= 31:
        delivery_status = CheckStatus.HUMAN_REVIEW
        delivery_explanation = f"Delivery is {terms.delivery_days} days after PO (31–45 days)."
    else:
        delivery_status = CheckStatus.PASS
        delivery_explanation = f"Delivery is {terms.delivery_days} days after PO (at most 30 days)."
    findings.append(
        _finding(
            "DELIVERY-001",
            "Delivery over 45 days rejects; 31–45 days needs review",
            delivery_status,
            delivery_explanation,
            delivery_evidence,
        )
    )

    vat_ok = pack.vat_percent == Decimal("15") and pack.vat_amount_bdt is not None
    findings.append(
        _finding(
            "VAT-001",
            "VAT must be shown separately at 15%",
            CheckStatus.PASS if vat_ok else CheckStatus.HUMAN_REVIEW,
            "VAT is separately shown at 15%." if vat_ok else "VAT is not separately shown at 15%.",
            _e(pack, "totals") + _e(pack, "items"),
        )
    )

    arithmetic_errors: list[str] = []
    for item in pack.items:
        expected_amount = item.quantity * item.unit_price_bdt
        if item.amount_bdt != expected_amount:
            arithmetic_errors.append(
                f"Item {item.item_code} amount {item.amount_bdt} != {expected_amount}."
            )
    item_sum = sum((item.amount_bdt for item in pack.items), ZERO)
    if pack.subtotal_bdt is not None and pack.subtotal_bdt != item_sum:
        arithmetic_errors.append(f"Subtotal {pack.subtotal_bdt} != line sum {item_sum}.")
    if pack.subtotal_bdt is not None and pack.vat_amount_bdt is not None:
        expected_vat = pack.subtotal_bdt * Decimal("0.15")
        if pack.vat_amount_bdt != expected_vat:
            arithmetic_errors.append(f"VAT {pack.vat_amount_bdt} != 15% ({expected_vat}).")
    if (
        pack.subtotal_bdt is not None
        and pack.vat_amount_bdt is not None
        and pack.total_bdt is not None
        and pack.total_bdt != pack.subtotal_bdt + pack.vat_amount_bdt
    ):
        arithmetic_errors.append(
            f"Total {pack.total_bdt} != subtotal plus VAT {pack.subtotal_bdt + pack.vat_amount_bdt}."
        )
    findings.append(
        _finding(
            "MATH-001",
            "Quoted numbers must add up",
            CheckStatus.HUMAN_REVIEW if arithmetic_errors else CheckStatus.PASS,
            " ".join(arithmetic_errors) if arithmetic_errors else "Line, subtotal, VAT, and total arithmetic is consistent where shown.",
            _e(pack, "items") + _e(pack, "totals"),
        )
    )

    validity_evidence = _e(pack, "validity")
    if terms.validity_days is None:
        validity_status = CheckStatus.HUMAN_REVIEW
        validity_explanation = "Quotation validity duration is unclear."
    elif terms.validity_days < 30:
        validity_status = CheckStatus.HUMAN_REVIEW
        validity_explanation = f"Quotation is valid for only {terms.validity_days} days."
    else:
        validity_status = CheckStatus.PASS
        validity_explanation = f"Quotation is valid for {terms.validity_days} days (at least 30)."
    findings.append(
        _finding(
            "VALIDITY-001",
            "Quotation validity under 30 days needs review",
            validity_status,
            validity_explanation,
            validity_evidence,
        )
    )

    return findings


def aggregate_decision(
    pack: ExtractedSupplierPack,
    findings: list[RuleFinding],
) -> EvaluationResult:
    """Apply the rules-file precedence: Reject > Human Review > Approve."""
    if any(finding.status == CheckStatus.REJECT for finding in findings):
        decision = Decision.REJECT
        decisive = [finding for finding in findings if finding.status == CheckStatus.REJECT]
    elif any(finding.status == CheckStatus.HUMAN_REVIEW for finding in findings):
        decision = Decision.HUMAN_REVIEW
        decisive = [finding for finding in findings if finding.status == CheckStatus.HUMAN_REVIEW]
    else:
        decision = Decision.APPROVE
        decisive = findings
    decision_reason = " ".join(f"{finding.rule_id}: {finding.explanation}" for finding in decisive)
    return EvaluationResult(
        source_file=pack.source_file,
        decision=decision,
        decision_reason=decision_reason,
        extracted=pack,
        findings=findings,
    )


def validate_pack(
    pack: ExtractedSupplierPack,
    purchase_request: dict[str, PurchaseRequestLine],
) -> EvaluationResult:
    return aggregate_decision(pack, evaluate_rules(pack, purchase_request))
