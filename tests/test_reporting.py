from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import fitz
import pytest

from supplierguard.inputs import load_purchase_request
from supplierguard.models import Decision
from supplierguard.reporting import audit_pdf_filename, generate_audit_pdf
from supplierguard.workflow import run_workflow


FIXED_TIME = datetime(2026, 11, 4, 9, 30, tzinfo=ZoneInfo("Asia/Dhaka"))


@pytest.mark.parametrize(
    ("number", "decision_text", "expected_text"),
    [
        (1, "APPROVE", "no human authorization is recorded"),
        (3, "REJECT", "Quoted unit price BDT 229.00"),
        (7, "NEEDS HUMAN REVIEW", "Quoted quantity 16,500"),
    ],
)
def test_audit_pdf_contains_correct_decision_values_and_actions(
    task_data, number, decision_text, expected_text
):
    result = run_workflow(
        task_data / f"supplier-pack-{number:02d}.pdf",
        task_data / "purchase-request.csv",
    )
    request = load_purchase_request(task_data / "purchase-request.csv")
    pdf_bytes = generate_audit_pdf(result, request, generated_at=FIXED_TIME)

    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 5_000
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        text = "\n".join(page.get_text() for page in document)
        assert document.page_count >= 2
        assert "Supplier Document Compliance Audit" in text
        assert decision_text in text
        assert result.extracted.supplier_name in text
        assert result.extracted.quotation_number in text
        assert expected_text in text
        assert "Complete rule audit" in text
        assert "Automated policy recommendation" in text
        assert "Page 1" in text


def test_reject_report_contains_exact_evidence_and_corrective_action(task_data):
    result = run_workflow(
        task_data / "supplier-pack-03.pdf", task_data / "purchase-request.csv"
    )
    request = load_purchase_request(task_data / "purchase-request.csv")
    pdf_bytes = generate_audit_pdf(result, request, generated_at=FIXED_TIME)
    evidence = result.exceptions[0].evidence[0].quote

    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        text = " ".join(" ".join(page.get_text().split()) for page in document)
        assert evidence in text
        assert "Ask the supplier for a revised unit price" in text
        assert "Maximum BDT 210.00" in text
        assert "PRICE-001" in text


def test_generated_report_pages_render_and_text_stays_inside_page(task_data, tmp_path):
    result = run_workflow(
        task_data / "supplier-pack-09.pdf", task_data / "purchase-request.csv"
    )
    request = load_purchase_request(task_data / "purchase-request.csv")
    pdf_bytes = generate_audit_pdf(result, request, generated_at=FIXED_TIME)

    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        assert document.page_count >= 2
        for index, page in enumerate(document):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
            image_path = tmp_path / f"report-page-{index + 1}.png"
            pixmap.save(image_path)
            assert image_path.stat().st_size > 10_000
            assert page.get_text().strip()
            for block in page.get_text("blocks"):
                x0, y0, x1, y1 = block[:4]
                assert x0 >= -1 and y0 >= -1
                assert x1 <= page.rect.width + 1
                assert y1 <= page.rect.height + 1


def test_audit_filename_uses_safe_quotation_identifier(task_data):
    result = run_workflow(
        task_data / "supplier-pack-01.pdf", task_data / "purchase-request.csv"
    )
    assert audit_pdf_filename(result) == "QT-2026-901-compliance-audit.pdf"
    assert result.decision == Decision.APPROVE
