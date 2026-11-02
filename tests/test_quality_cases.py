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


def _status(result, rule_id: str) -> CheckStatus:
    return next(finding.status for finding in result.findings if finding.rule_id == rule_id)


@pytest.mark.parametrize("field", ["advance", "payment", "delivery", "penalty", "validity"])
def test_missing_or_ambiguous_terms_never_pass_silently(task_data, field):
    pack, request = _baseline(task_data)
    if field == "advance":
        pack.terms.advance_percent = None
        rule = "PAY-ADV-001"
    elif field == "payment":
        pack.terms.payment_days_min = None
        pack.terms.payment_days_max = None
        pack.terms.payment_is_clear = False
        rule = "PAY-TERM-001"
    elif field == "delivery":
        pack.terms.delivery_days = None
        rule = "DELIVERY-001"
    elif field == "penalty":
        pack.terms.late_penalty_clause_present = True
        pack.terms.late_penalty_percent_per_week = None
        rule = "PENALTY-001"
    else:
        pack.terms.validity_days = None
        rule = "VALIDITY-001"

    result = validate_pack(pack, request)
    assert _status(result, rule) == CheckStatus.HUMAN_REVIEW
    assert result.decision == Decision.HUMAN_REVIEW


def test_line_arithmetic_error_requires_review(task_data):
    pack, request = _baseline(task_data)
    pack.items[0].amount_bdt += Decimal("1")
    result = validate_pack(pack, request)
    assert _status(result, "MATH-001") == CheckStatus.HUMAN_REVIEW
    assert result.decision == Decision.HUMAN_REVIEW


@pytest.mark.parametrize("vat_percent", [None, Decimal("14")])
def test_missing_or_wrong_vat_rate_requires_review(task_data, vat_percent):
    pack, request = _baseline(task_data)
    pack.vat_percent = vat_percent
    result = validate_pack(pack, request)
    assert _status(result, "VAT-001") == CheckStatus.HUMAN_REVIEW
    assert result.decision == Decision.HUMAN_REVIEW


def test_incorrect_vat_amount_is_caught_by_arithmetic_rule(task_data):
    pack, request = _baseline(task_data)
    pack.vat_amount_bdt += Decimal("1")
    result = validate_pack(pack, request)
    assert _status(result, "VAT-001") == CheckStatus.PASS
    assert _status(result, "MATH-001") == CheckStatus.HUMAN_REVIEW
    assert result.decision == Decision.HUMAN_REVIEW


@pytest.mark.parametrize("missing", ["tin", "bin", "both"])
def test_missing_tin_or_bin_rejects(task_data, missing):
    pack, request = _baseline(task_data)
    if missing in {"tin", "both"}:
        pack.tin = None
    if missing in {"bin", "both"}:
        pack.bin = None
    result = validate_pack(pack, request)
    assert _status(result, "ID-001") == CheckStatus.REJECT
    assert result.decision == Decision.REJECT


def test_penalty_with_ambiguous_order_value_basis_requires_review(task_data):
    pack, request = _baseline(task_data)
    pack.terms.late_penalty_mentions_order_value = False
    result = validate_pack(pack, request)
    assert _status(result, "PENALTY-001") == CheckStatus.HUMAN_REVIEW
    assert result.decision == Decision.HUMAN_REVIEW
