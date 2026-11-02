import pytest

from supplierguard.models import Decision
from supplierguard.service import evaluate_document


EXPECTED = {
    1: Decision.APPROVE,
    2: Decision.APPROVE,
    3: Decision.REJECT,
    4: Decision.HUMAN_REVIEW,
    5: Decision.REJECT,
    6: Decision.REJECT,
    7: Decision.HUMAN_REVIEW,
    8: Decision.REJECT,
    9: Decision.HUMAN_REVIEW,
    10: Decision.REJECT,
}


@pytest.mark.parametrize(("number", "expected"), EXPECTED.items())
def test_rule_derived_expected_decision_for_each_pack(task_data, number, expected):
    result = evaluate_document(
        task_data / f"supplier-pack-{number:02d}.pdf",
        task_data / "purchase-request.csv",
    )
    assert result.decision == expected
    decisive_status = expected.value
    if expected == Decision.APPROVE:
        assert all(finding.status.value == "Pass" for finding in result.findings)
    else:
        assert any(finding.status.value == decisive_status for finding in result.findings)


def test_decisive_findings_have_page_level_quotes(task_data):
    for number, expected in EXPECTED.items():
        result = evaluate_document(
            task_data / f"supplier-pack-{number:02d}.pdf",
            task_data / "purchase-request.csv",
        )
        decisive = (
            result.findings
            if expected == Decision.APPROVE
            else [f for f in result.findings if f.status.value == expected.value]
        )
        assert decisive
        assert all(f.evidence for f in decisive)
        assert all(e.page >= 1 and e.quote.strip() for f in decisive for e in f.evidence)
