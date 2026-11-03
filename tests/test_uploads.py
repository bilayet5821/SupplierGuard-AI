from __future__ import annotations

import fitz
import pytest

from supplierguard.models import Decision
from supplierguard.uploads import (
    UploadValidationError,
    evaluate_uploaded_pdf,
    validate_uploaded_pdf,
)


def _source_text(path) -> str:
    with fitz.open(path) as document:
        return "\n".join(page.get_text("text", sort=True) for page in document)


def _text_pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    remaining = page.insert_textbox(
        fitz.Rect(25, 25, 570, 817),
        text,
        fontsize=7,
        fontname="helv",
        lineheight=1.1,
    )
    assert remaining >= 0
    data = document.tobytes()
    document.close()
    return data


def _scanned_copy_bytes(path) -> bytes:
    with fitz.open(path) as source:
        pixmap = source[0].get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        image = pixmap.tobytes("png")
        width, height = source[0].rect.width, source[0].rect.height
    document = fitz.open()
    page = document.new_page(width=width, height=height)
    page.insert_image(page.rect, stream=image)
    data = document.tobytes()
    document.close()
    return data


def _two_page_text_pdf_bytes(first_page: str, second_page: str) -> bytes:
    document = fitz.open()
    for text in (first_page, second_page):
        page = document.new_page(width=595, height=842)
        remaining = page.insert_textbox(
            fitz.Rect(25, 25, 570, 817),
            text,
            fontsize=7,
            fontname="helv",
            lineheight=1.1,
        )
        assert remaining >= 0
    data = document.tobytes()
    document.close()
    return data


def test_valid_upload_copy_uses_existing_workflow_and_original_filename(task_data):
    data = (task_data / "supplier-pack-01.pdf").read_bytes()
    uploaded = evaluate_uploaded_pdf(
        data, "renamed-supplier-quote.pdf", task_data / "purchase-request.csv"
    )
    assert uploaded.result.decision == Decision.APPROVE
    assert uploaded.result.source_file == "renamed-supplier-quote.pdf"
    assert uploaded.metadata.page_count == 1
    assert uploaded.metadata.detected_item_rows == 1
    assert len(uploaded.metadata.sha256) == 64


def test_same_filename_with_different_content_does_not_reuse_a_decision(task_data):
    approved = evaluate_uploaded_pdf(
        (task_data / "supplier-pack-01.pdf").read_bytes(),
        "same-name.pdf",
        task_data / "purchase-request.csv",
    )
    rejected = evaluate_uploaded_pdf(
        (task_data / "supplier-pack-03.pdf").read_bytes(),
        "same-name.pdf",
        task_data / "purchase-request.csv",
    )
    assert approved.result.decision == Decision.APPROVE
    assert rejected.result.decision == Decision.REJECT
    assert approved.metadata.sha256 != rejected.metadata.sha256


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "empty"),
        (b"%PDF-corrupt-data", "could not be opened"),
        (b"not a pdf", "does not appear to be a valid PDF"),
    ],
)
def test_invalid_uploads_fail_with_clear_messages(data, message):
    with pytest.raises(UploadValidationError, match=message):
        validate_uploaded_pdf(data, "quotation.pdf")


def test_scanned_copy_is_rejected_for_human_review(task_data):
    data = _scanned_copy_bytes(task_data / "supplier-pack-01.pdf")
    with pytest.raises(UploadValidationError, match="scanned or image-only"):
        validate_uploaded_pdf(data, "scanned-copy.pdf")


def test_text_pdf_with_unsupported_structure_fails_closed(task_data):
    sample_text = _source_text(task_data / "supplier-pack-01.pdf")
    unsupported = sample_text.replace("QUOTATION", "UNSUPPORTED DOCUMENT", 1)
    with pytest.raises(UploadValidationError, match="does not match the verified BIAI"):
        evaluate_uploaded_pdf(
            _text_pdf_bytes(unsupported),
            "unsupported-layout.pdf",
            task_data / "purchase-request.csv",
        )


def test_encrypted_copy_is_rejected_clearly(task_data):
    with fitz.open(task_data / "supplier-pack-01.pdf") as source:
        data = source.tobytes(
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner-password",
            user_pw="user-password",
        )
    with pytest.raises(UploadValidationError, match="Password-protected"):
        validate_uploaded_pdf(data, "locked-copy.pdf")


def test_unmatched_item_copy_requires_human_review(task_data):
    text = _source_text(task_data / "supplier-pack-02.pdf")
    modified = text.replace("B       Metal zipper", "Z       Metal zipper", 1)
    assert modified != text
    uploaded = evaluate_uploaded_pdf(
        _text_pdf_bytes(modified),
        "unmatched-item.pdf",
        task_data / "purchase-request.csv",
    )
    assert uploaded.result.decision == Decision.HUMAN_REVIEW
    assert any(finding.rule_id == "PR-001" for finding in uploaded.result.findings)


def test_multi_item_copy_is_never_silently_approved(task_data):
    text = _source_text(task_data / "supplier-pack-02.pdf")
    item_line = next(line for line in text.splitlines() if line.lstrip().startswith("B       Metal zipper"))
    modified = text.replace(item_line, f"{item_line}\n{item_line}", 1)
    uploaded = evaluate_uploaded_pdf(
        _text_pdf_bytes(modified),
        "multi-item-copy.pdf",
        task_data / "purchase-request.csv",
    )
    assert uploaded.metadata.detected_item_rows == 2
    assert uploaded.result.decision == Decision.HUMAN_REVIEW
    safety = next(
        finding
        for finding in uploaded.result.findings
        if finding.rule_id == "UPLOAD-MULTI-ITEM"
    )
    assert len(safety.evidence) == 2
    assert all(evidence.page == 1 for evidence in safety.evidence)


def test_multi_page_copy_retains_actual_evidence_page(task_data):
    text = _source_text(task_data / "supplier-pack-01.pdf")
    first_page, terms = text.split("TERMS AND CONDITIONS", 1)
    data = _two_page_text_pdf_bytes(first_page, "TERMS AND CONDITIONS\n" + terms)
    uploaded = evaluate_uploaded_pdf(
        data,
        "two-page-copy.pdf",
        task_data / "purchase-request.csv",
    )
    assert uploaded.result.decision == Decision.APPROVE
    assert uploaded.metadata.page_count == 2
    delivery = next(
        finding
        for finding in uploaded.result.findings
        if finding.rule_id == "DELIVERY-001"
    )
    assert delivery.evidence[0].page == 2
