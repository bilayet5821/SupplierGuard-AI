from __future__ import annotations

import hashlib
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import fitz

from .models import CheckStatus, EvaluationResult, Evidence, RuleFinding
from .validation import aggregate_decision
from .workflow import run_workflow


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_PAGES = 10
MIN_TEXT_CHARACTERS = 80
ITEM_ROW_PATTERN = re.compile(
    r"(?mi)^\s*[A-Z]\s+.+?\s+[\d,]+\s+(?:metre|piece|cone)\s+"
    r"[\d,]+(?:\.\d+)?\s+[\d,]+(?:\.\d+)?\s*$"
)


class UploadValidationError(ValueError):
    """A safe, user-facing rejection of an unreadable or unsupported upload."""


@dataclass(frozen=True)
class UploadMetadata:
    original_filename: str
    size_bytes: int
    page_count: int
    text_characters: int
    detected_item_rows: int
    detected_item_evidence: tuple[Evidence, ...]
    page_texts: tuple[str, ...]
    sha256: str


@dataclass(frozen=True)
class UploadedEvaluation:
    result: EvaluationResult
    metadata: UploadMetadata


def validate_uploaded_pdf(data: bytes, filename: str) -> UploadMetadata:
    if not data:
        raise UploadValidationError(
            "The uploaded file is empty. Select a readable PDF quotation and try again."
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadValidationError(
            f"The PDF is larger than the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB safety limit."
        )
    if Path(filename).suffix.lower() != ".pdf":
        raise UploadValidationError("Only PDF quotation files are accepted.")
    if not data.startswith(b"%PDF-"):
        raise UploadValidationError(
            "The file does not appear to be a valid PDF. It may be corrupt or incorrectly named."
        )

    try:
        document = fitz.open(stream=data, filetype="pdf")
    except (fitz.FileDataError, RuntimeError, ValueError) as exc:
        raise UploadValidationError(
            "The PDF could not be opened. It may be corrupt or incomplete."
        ) from exc

    try:
        if document.needs_pass:
            raise UploadValidationError(
                "Password-protected PDFs cannot be checked. Upload an unlocked copy for human review."
            )
        if document.page_count < 1:
            raise UploadValidationError("The PDF contains no pages.")
        if document.page_count > MAX_UPLOAD_PAGES:
            raise UploadValidationError(
                f"The PDF has {document.page_count} pages; the upload limit is {MAX_UPLOAD_PAGES}."
            )

        page_texts = [page.get_text("text", sort=True) for page in document]
        empty_pages = [index + 1 for index, text in enumerate(page_texts) if not text.strip()]
        if empty_pages:
            pages = ", ".join(map(str, empty_pages))
            raise UploadValidationError(
                f"No readable text was found on page(s) {pages}. The PDF may be scanned or image-only; "
                "send it to a human reviewer because SupplierGuard does not use OCR."
            )
        combined = "\n".join(page_texts)
        text_characters = len(re.sub(r"\s+", "", combined))
        if text_characters < MIN_TEXT_CHARACTERS:
            raise UploadValidationError(
                "The PDF contains too little readable text for a reliable compliance check. "
                "Send it to a human reviewer."
            )
        required_markers = {
            "QUOTATION heading": r"(?mi)^\s*QUOTATION\s*$",
            "quotation number": r"(?i)Quotation\s+no\.",
            "purchase-request reference": r"(?i)Reference\s+PR-",
            "item table": r"(?i)Item\s+Description\s+Qty\s+Unit",
            "terms and conditions": r"(?i)TERMS\s+AND\s+CONDITIONS",
        }
        missing_markers = [
            label
            for label, pattern in required_markers.items()
            if not re.search(pattern, combined)
        ]
        if missing_markers:
            raise UploadValidationError(
                "The PDF does not match the verified BIAI supplier-pack structure. "
                "Missing section(s): "
                + ", ".join(missing_markers)
                + ". Send it to a human reviewer."
            )
        item_evidence = tuple(
            Evidence(page=page_number, quote=re.sub(r"\s+", " ", match.group(0)).strip())
            for page_number, text in enumerate(page_texts, start=1)
            for match in ITEM_ROW_PATTERN.finditer(text)
        )
    finally:
        document.close()

    return UploadMetadata(
        original_filename=Path(filename).name,
        size_bytes=len(data),
        page_count=len(page_texts),
        text_characters=text_characters,
        detected_item_rows=len(item_evidence),
        detected_item_evidence=item_evidence,
        page_texts=tuple(page_texts),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def _apply_upload_safety(
    result: EvaluationResult,
    metadata: UploadMetadata,
) -> EvaluationResult:
    detected_item_rows = metadata.detected_item_rows
    extracted_count = len(result.extracted.items)
    if detected_item_rows <= 1 and extracted_count <= 1:
        return result

    count = max(detected_item_rows, extracted_count)
    evidence = list(metadata.detected_item_evidence)
    if not evidence:
        evidence = result.extracted.evidence.get("items", [])
    if not evidence:
        evidence = [Evidence(page=1, quote=f"{count} quotation line items detected")]
    finding = RuleFinding(
        rule_id="UPLOAD-MULTI-ITEM",
        rule="Uploaded quotations must use the verified one-item supplier-pack structure",
        status=CheckStatus.HUMAN_REVIEW,
        explanation=(
            f"{count} line items were detected. The upload path is verified for one item per supplier pack; "
            "the document must not be approved automatically."
        ),
        evidence=evidence,
    )
    findings = [*result.findings, finding]
    return aggregate_decision(result.extracted, findings)


def evaluate_uploaded_pdf(
    data: bytes,
    filename: str,
    purchase_request_csv: str | Path,
) -> UploadedEvaluation:
    metadata = validate_uploaded_pdf(data, filename)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary:
            temporary.write(data)
            temporary_path = Path(temporary.name)
        result = run_workflow(temporary_path, purchase_request_csv)
        if result.extracted.uncertainties or not result.extracted.items:
            reasons = "; ".join(result.extracted.uncertainties) or "No complete item was extracted."
            raise UploadValidationError(
                "SupplierGuard could not reliably interpret the required quotation fields. "
                f"{reasons} Send the original document to a human reviewer; no values were guessed."
            )
        result.source_file = metadata.original_filename
        result.extracted.source_file = metadata.original_filename
        result = _apply_upload_safety(result, metadata)
        return UploadedEvaluation(result=result, metadata=metadata)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
