from __future__ import annotations

from pathlib import Path

from .models import EvaluationResult


def evaluate_document(
    pdf_path: str | Path,
    purchase_request_csv: str | Path,
) -> EvaluationResult:
    # Local import avoids a package import cycle while keeping the public API small.
    from .workflow import run_workflow

    return run_workflow(pdf_path, purchase_request_csv)
