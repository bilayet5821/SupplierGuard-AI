from copy import deepcopy
from decimal import Decimal

from supplierguard.extraction import extract_supplier_pack
from supplierguard.inputs import load_purchase_request
from supplierguard.models import CheckStatus, Decision
from supplierguard.pdf import extract_pdf_pages
from supplierguard.validation import validate_pack


def _load(task_data, number):
    pack = extract_supplier_pack(
        extract_pdf_pages(task_data / f"supplier-pack-{number:02d}.pdf")
    )
    request = load_purchase_request(task_data / "purchase-request.csv")
    return pack, request


def test_exact_three_percent_price_is_review_not_reject(task_data):
    pack, request = _load(task_data, 1)
    pack.items[0].unit_price_bdt = request["A"].maximum_unit_price_bdt * Decimal("1.03")
    pack.items[0].amount_bdt = pack.items[0].quantity * pack.items[0].unit_price_bdt
    pack.subtotal_bdt = pack.items[0].amount_bdt
    pack.vat_amount_bdt = pack.subtotal_bdt * Decimal("0.15")
    pack.total_bdt = pack.subtotal_bdt + pack.vat_amount_bdt
    result = validate_pack(pack, request)
    price = next(f for f in result.findings if f.rule_id == "PRICE-001")
    assert price.status == CheckStatus.HUMAN_REVIEW
    assert result.decision == Decision.HUMAN_REVIEW


def test_reject_precedes_review(task_data):
    pack, request = _load(task_data, 10)
    result = validate_pack(pack, request)
    assert any(f.status == CheckStatus.REJECT for f in result.findings)
    assert any(f.status == CheckStatus.HUMAN_REVIEW for f in result.findings)
    assert result.decision == Decision.REJECT


def test_arithmetic_mismatch_needs_review(task_data):
    pack, request = _load(task_data, 2)
    changed = deepcopy(pack)
    changed.items[0].amount_bdt += Decimal("1")
    result = validate_pack(changed, request)
    math = next(f for f in result.findings if f.rule_id == "MATH-001")
    assert math.status == CheckStatus.HUMAN_REVIEW
    assert result.decision == Decision.HUMAN_REVIEW
