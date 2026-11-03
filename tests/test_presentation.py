from __future__ import annotations

from streamlit.testing.v1 import AppTest

from supplierguard.models import Decision, Evidence, RuleFinding, CheckStatus
from supplierguard.presentation import (
    business_explanation,
    business_summary,
    recommended_next_action,
    rule_label,
    status_label,
    unique_evidence,
    unique_pages,
)
from supplierguard.workflow import run_workflow


def test_page_numbers_and_quotes_are_deduplicated():
    finding = RuleFinding(
        rule_id="TEST",
        rule="Test rule",
        status=CheckStatus.PASS,
        explanation="Test",
        evidence=[
            Evidence(page=1, quote="A"),
            Evidence(page=1, quote="B"),
            Evidence(page=1, quote="A"),
            Evidence(page=2, quote="C"),
        ],
    )
    assert unique_pages(finding) == [1, 2]
    assert [(e.page, e.quote) for e in unique_evidence(finding)] == [
        (1, "A"),
        (1, "B"),
        (2, "C"),
    ]


def test_business_summary_is_concise_and_uses_top_drivers(task_data):
    result = run_workflow(
        task_data / "supplier-pack-08.pdf", task_data / "purchase-request.csv"
    )
    summary = business_summary(result)
    assert result.decision == Decision.REJECT
    assert summary.startswith("Rejected:")
    assert len(summary) < 300
    assert "PRICE-001" not in summary


def test_procurement_labels_and_actions_are_business_friendly(task_data):
    assert rule_label("PRICE-001") == "Unit price limit"
    assert status_label(CheckStatus.REJECT) == "REJECT — Blocks purchase"
    assert "not a recorded human approval" in recommended_next_action(Decision.APPROVE)
    assert "Do not issue a purchase order" in recommended_next_action(Decision.REJECT)
    assert "Pause purchase-order processing" in recommended_next_action(
        Decision.HUMAN_REVIEW
    )

    result = run_workflow(
        task_data / "supplier-pack-07.pdf", task_data / "purchase-request.csv"
    )
    quantity_finding = next(
        finding for finding in result.findings if finding.rule_id == "QTY-001"
    )
    explanation = business_explanation(quantity_finding)
    assert "16,500" in explanation
    assert "20,000" in explanation
    assert "QTY-001" not in explanation


def test_streamlit_app_renders_without_exceptions():
    app = AppTest.from_file("app.py").run(timeout=30)
    assert not app.exception
    assert app.title[0].value == "Supplier Document Compliance Review"
    markup = "\n".join(element.value for element in app.markdown)
    assert "sg-kpi-grid" in markup
    assert "sg-decision__summary" in markup
    assert "Recommended action(s)" in markup
    assert "Policy issues" in markup
    assert app.button_group[0].value == "Decision"
    assert len(app.get("download_button")) == 1


def test_all_navigation_sections_render():
    app = AppTest.from_file("app.py").run(timeout=30)
    expected_headings = {
        "Extracted Data": "Document details",
        "Rule Audit": "Policy audit",
        "Source Evidence": "Source document text",
    }
    for section, heading in expected_headings.items():
        app.button_group[0].set_value([section]).run(timeout=30)
        assert not app.exception
        assert heading in [element.value for element in app.subheader]
