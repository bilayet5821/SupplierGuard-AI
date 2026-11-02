from __future__ import annotations

import re

from supplierguard.models import CheckStatus, Decision
from supplierguard.pdf import extract_pdf_pages
from supplierguard.workflow import run_workflow


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_all_supplied_extraction_and_findings_use_genuine_page_text(task_data):
    for pdf in sorted(task_data.glob("supplier-pack-*.pdf")):
        document = extract_pdf_pages(pdf)
        page_text = {page.page: _compact(page.text) for page in document.pages}
        result = run_workflow(pdf, task_data / "purchase-request.csv")
        pack = result.extracted

        required_categories = {
            "supplier_name",
            "header",
            "items",
            "totals",
            "identifiers",
            "payment",
            "delivery",
            "validity",
        }
        assert required_categories <= pack.evidence.keys()
        assert pack.items
        if pack.terms.late_penalty_clause_present:
            assert "delay" in pack.evidence
        if pack.tin or pack.bin:
            assert pack.evidence["identifiers"]
        for evidence_list in pack.evidence.values():
            for evidence in evidence_list:
                assert evidence.quote in page_text[evidence.page]

        for finding in result.findings:
            assert finding.evidence, f"{pdf.name} {finding.rule_id} has no evidence"
            for evidence in finding.evidence:
                assert evidence.quote in page_text[evidence.page]

        decisive_status = {
            Decision.APPROVE: CheckStatus.PASS,
            Decision.REJECT: CheckStatus.REJECT,
            Decision.HUMAN_REVIEW: CheckStatus.HUMAN_REVIEW,
        }[result.decision]
        decisive = [f for f in result.findings if f.status == decisive_status]
        assert decisive and all(f.evidence for f in decisive)
