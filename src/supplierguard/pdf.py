from __future__ import annotations

from pathlib import Path

import fitz

from .models import PageText, PdfDocument


def extract_pdf_pages(pdf_path: str | Path) -> PdfDocument:
    """Extract embedded text page by page; scanned/image-only pages stay empty."""
    path = Path(pdf_path).resolve()
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise FileNotFoundError(f"PDF not found: {path}")

    pages: list[PageText] = []
    with fitz.open(path) as document:
        for index, page in enumerate(document):
            pages.append(PageText(page=index + 1, text=page.get_text("text", sort=True)))

    if not pages:
        raise ValueError(f"PDF has no pages: {path.name}")
    return PdfDocument(source_path=str(path), source_file=path.name, pages=pages)
