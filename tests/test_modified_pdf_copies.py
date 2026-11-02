from __future__ import annotations

import hashlib

import fitz
import pytest

from supplierguard.models import Decision
from supplierguard.workflow import run_workflow


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_modified_copy(source, output, old: str, new: str) -> None:
    with fitz.open(source) as document:
        text = "\n".join(page.get_text("text", sort=True) for page in document)
    assert old in text
    modified = text.replace(old, new, 1)

    output_document = fitz.open()
    page = output_document.new_page(width=595, height=842)
    remaining = page.insert_textbox(
        fitz.Rect(25, 25, 570, 817),
        modified,
        fontsize=7,
        fontname="helv",
        lineheight=1.1,
    )
    assert remaining >= 0, "Modified sample text did not fit on its temporary page"
    output_document.save(output)
    output_document.close()


@pytest.mark.parametrize(
    ("filename", "old", "new", "expected", "evidence_fragment"),
    [
        (
            "supplier-pack-01.pdf",
            "within 21 days from the date of PO.",
            "within 46 days from the date of PO.",
            Decision.REJECT,
            "46 days",
        ),
        (
            "supplier-pack-10.pdf",
            "valid for 30 days from the date above.",
            "valid for 29 days from the date above.",
            Decision.HUMAN_REVIEW,
            "29 days",
        ),
    ],
)
def test_content_changes_drive_decisions_not_filenames(
    task_data, tmp_path, filename, old, new, expected, evidence_fragment
):
    source = task_data / "supplier-pack-02.pdf"
    original_hash = _sha256(source)
    variant = tmp_path / filename
    _make_modified_copy(source, variant, old, new)

    result = run_workflow(variant, task_data / "purchase-request.csv")

    assert result.decision == expected
    decisive = [f for f in result.findings if f.status.value == expected.value]
    assert any(
        evidence_fragment in evidence.quote
        for finding in decisive
        for evidence in finding.evidence
    )
    assert _sha256(source) == original_hash
