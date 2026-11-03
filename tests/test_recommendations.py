from __future__ import annotations

from copy import deepcopy

import pytest

from supplierguard.extraction import extract_supplier_pack
from supplierguard.inputs import load_purchase_request
from supplierguard.models import CheckStatus, Decision
from supplierguard.pdf import extract_pdf_pages
from supplierguard.presentation import issue_details, recommendations_for_result
from supplierguard.validation import validate_pack
from supplierguard.workflow import run_workflow


@pytest.mark.parametrize(
    ("number", "expected_action"),
    [
        (3, "revised unit price"),
        (4, "purchasing officer"),
        (5, "advance payment to 20% or less"),
        (6, "late-delivery clause"),
        (7, "corrected quotation for 20,000"),
        (8, "supplier TIN and BIN"),
        (9, "clarified payment terms"),
        (9, "internally consistent calculations"),
        (10, "delivery lead time of 45 days or less"),
        (10, "15% VAT shown as a separate amount"),
    ],
)
def test_original_exception_types_have_specific_actions(
    task_data, number, expected_action
):
    result = run_workflow(
        task_data / f"supplier-pack-{number:02d}.pdf",
        task_data / "purchase-request.csv",
    )
    request = load_purchase_request(task_data / "purchase-request.csv")
    actions = recommendations_for_result(result, request)
    assert any(expected_action in action for action in actions)


def test_approve_action_does_not_claim_human_authorization(task_data):
    result = run_workflow(
        task_data / "supplier-pack-01.pdf", task_data / "purchase-request.csv"
    )
    request = load_purchase_request(task_data / "purchase-request.csv")
    actions = recommendations_for_result(result, request)
    assert len(actions) == 1
    assert "not a recorded human approval" in actions[0]


def test_rejection_recommendations_precede_review_recommendations(task_data):
    result = run_workflow(
        task_data / "supplier-pack-08.pdf", task_data / "purchase-request.csv"
    )
    request = load_purchase_request(task_data / "purchase-request.csv")
    details = issue_details(result, request)
    actions = recommendations_for_result(result, request)
    assert result.decision == Decision.REJECT
    assert any(detail.status == CheckStatus.REJECT for detail in details)
    assert any(detail.status == CheckStatus.HUMAN_REVIEW for detail in details)
    assert "TIN and BIN" in actions[0]


def test_short_validity_and_uncertainty_have_specific_human_actions(task_data):
    request = load_purchase_request(task_data / "purchase-request.csv")
    pack = extract_supplier_pack(
        extract_pdf_pages(task_data / "supplier-pack-02.pdf")
    )
    changed = deepcopy(pack)
    changed.terms.validity_days = 29
    result = validate_pack(changed, request)
    assert any(
        "validity period of at least 30 days" in action
        for action in recommendations_for_result(result, request)
    )

    uncertain = deepcopy(pack)
    uncertain.uncertainties.append("Delivery wording could not be interpreted.")
    result = validate_pack(uncertain, request)
    assert any(
        "human reviewer" in action
        for action in recommendations_for_result(result, request)
    )
