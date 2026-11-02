from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

import pytest

from supplierguard.extraction import extract_supplier_pack
from supplierguard.inputs import load_purchase_request
from supplierguard.models import CheckStatus, Decision
from supplierguard.pdf import extract_pdf_pages
from supplierguard.validation import validate_pack


def _baseline(task_data):
    pack = extract_supplier_pack(extract_pdf_pages(task_data / "supplier-pack-02.pdf"))
    request = load_purchase_request(task_data / "purchase-request.csv")
    return pack, request


def _rebalance(pack) -> None:
    item = pack.items[0]
    item.amount_bdt = item.quantity * item.unit_price_bdt
    pack.subtotal_bdt = item.amount_bdt
    pack.vat_percent = Decimal("15")
    pack.vat_amount_bdt = pack.subtotal_bdt * Decimal("0.15")
    pack.total_bdt = pack.subtotal_bdt + pack.vat_amount_bdt


def _status(result, rule_id: str) -> CheckStatus:
    return next(finding.status for finding in result.findings if finding.rule_id == rule_id)


@pytest.mark.parametrize(
    ("unit_price", "expected"),
    [
        (Decimal("39.14"), CheckStatus.HUMAN_REVIEW),  # exactly 3% above 38.00
        (Decimal("39.15"), CheckStatus.REJECT),
    ],
)
def test_price_three_percent_boundary(task_data, unit_price, expected):
    pack, request = _baseline(task_data)
    pack.items[0].unit_price_bdt = unit_price
    _rebalance(pack)
    assert _status(validate_pack(pack, request), "PRICE-001") == expected


def test_quantity_exactly_five_percent_passes(task_data):
    pack, request = _baseline(task_data)
    pack.items[0].quantity = Decimal("21000")
    _rebalance(pack)
    result = validate_pack(pack, request)
    assert _status(result, "QTY-001") == CheckStatus.PASS
    assert result.decision == Decision.APPROVE


@pytest.mark.parametrize(
    ("advance", "expected"),
    [
        (Decimal("20"), CheckStatus.PASS),
        (Decimal("20.01"), CheckStatus.REJECT),
    ],
)
def test_advance_twenty_percent_boundary(task_data, advance, expected):
    pack, request = _baseline(task_data)
    pack.terms.advance_percent = advance
    assert _status(validate_pack(pack, request), "PAY-ADV-001") == expected


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (30, CheckStatus.PASS),
        (31, CheckStatus.HUMAN_REVIEW),
        (45, CheckStatus.HUMAN_REVIEW),
        (46, CheckStatus.REJECT),
    ],
)
def test_delivery_boundaries(task_data, days, expected):
    pack, request = _baseline(task_data)
    pack.terms.delivery_days = days
    assert _status(validate_pack(pack, request), "DELIVERY-001") == expected


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (30, CheckStatus.PASS),
        (60, CheckStatus.PASS),
        (61, CheckStatus.HUMAN_REVIEW),
    ],
)
def test_payment_day_boundaries(task_data, days, expected):
    pack, request = _baseline(task_data)
    pack.terms.payment_days_min = days
    pack.terms.payment_days_max = days
    pack.terms.payment_is_clear = True
    assert _status(validate_pack(pack, request), "PAY-TERM-001") == expected


@pytest.mark.parametrize(
    ("rate", "expected"),
    [
        (Decimal("0.5"), CheckStatus.PASS),
        (Decimal("0.49"), CheckStatus.REJECT),
    ],
)
def test_penalty_rate_boundary(task_data, rate, expected):
    pack, request = _baseline(task_data)
    pack.terms.late_penalty_clause_present = True
    pack.terms.late_penalty_mentions_order_value = True
    pack.terms.late_penalty_percent_per_week = rate
    assert _status(validate_pack(pack, request), "PENALTY-001") == expected


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (29, CheckStatus.HUMAN_REVIEW),
        (30, CheckStatus.PASS),
    ],
)
def test_validity_boundary(task_data, days, expected):
    pack, request = _baseline(task_data)
    pack.terms.validity_days = days
    assert _status(validate_pack(pack, request), "VALIDITY-001") == expected


def test_reject_precedes_multiple_review_conditions(task_data):
    pack, request = _baseline(task_data)
    pack.terms.advance_percent = Decimal("21")  # reject
    pack.items[0].unit_price_bdt = Decimal("39.00")  # review
    pack.items[0].quantity = Decimal("22000")  # review
    pack.terms.payment_days_min = pack.terms.payment_days_max = 61  # review
    pack.terms.delivery_days = 31  # review
    pack.terms.validity_days = 29  # review
    pack.vat_percent = None  # review
    pack.vat_amount_bdt = None
    _rebalance(pack)
    pack.vat_percent = None
    pack.vat_amount_bdt = None

    result = validate_pack(pack, request)
    assert result.decision == Decision.REJECT
    assert _status(result, "PAY-ADV-001") == CheckStatus.REJECT
    assert sum(f.status == CheckStatus.HUMAN_REVIEW for f in result.findings) >= 5
