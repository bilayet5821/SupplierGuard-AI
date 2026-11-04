from __future__ import annotations

import csv
import io
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .inputs import load_purchase_request
from .models import PurchaseRequestLine
from .uploads import UploadedEvaluation, evaluate_uploaded_pdf

MAX_REQUEST_CSV_BYTES = 256 * 1024
MAX_REQUEST_ROWS = 100
REQUIRED_HEADERS = (
    "PR number",
    "Item",
    "Description",
    "Unit",
    "Quantity requested",
    "Maximum unit price (BDT)",
)


class RequestValidationError(ValueError):
    """Friendly error for malformed or unsupported uploaded purchase requests."""


def validate_request_csv(data: bytes, filename: str) -> int:
    """Validate a BIAI-structure purchase request before any compliance evaluation."""
    if Path(filename).suffix.lower() != ".csv":
        raise RequestValidationError("Upload a purchase request CSV (.csv file).")
    if not data:
        raise RequestValidationError("The purchase request CSV is empty.")
    if len(data) > MAX_REQUEST_CSV_BYTES:
        raise RequestValidationError("The purchase request CSV exceeds the 256 KB demo limit.")
    try:
        body = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RequestValidationError("The purchase request CSV must be UTF-8 encoded.") from exc
    if "\x00" in body:
        raise RequestValidationError("The purchase request contains invalid binary content.")
    try:
        reader = csv.DictReader(io.StringIO(body, newline=""))
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or any(h not in headers for h in REQUIRED_HEADERS):
            raise RequestValidationError("The purchase request CSV is missing or repeats required columns: " + ", ".join(REQUIRED_HEADERS))
        codes: set[str] = set()
        request_numbers: set[str] = set()
        count = 0
        for row in reader:
            count += 1
            if count > MAX_REQUEST_ROWS:
                raise RequestValidationError("The purchase request has too many rows for this demo (maximum 100).")
            if None in row or any(row.get(h) is None for h in REQUIRED_HEADERS):
                raise RequestValidationError("The purchase request CSV contains malformed rows.")
            values = {h: row[h].strip() for h in REQUIRED_HEADERS}
            if any(not v or len(v) > 512 for v in values.values()):
                raise RequestValidationError("Every purchase-request field must be present and reasonably sized.")
            if values["Item"] in codes:
                raise RequestValidationError("Duplicate purchase-request item codes are not supported.")
            codes.add(values["Item"])
            request_numbers.add(values["PR number"])
            try:
                qty = Decimal(values["Quantity requested"].replace(",", ""))
                max_price = Decimal(values["Maximum unit price (BDT)"].replace(",", ""))
            except InvalidOperation as exc:
                raise RequestValidationError("Purchase-request quantities and maximum prices must be valid numbers.") from exc
            if not qty.is_finite() or not max_price.is_finite() or qty <= 0 or max_price <= 0:
                raise RequestValidationError("Quantities and maximum prices must be finite, positive numbers.")
        if not count:
            raise RequestValidationError("The purchase request CSV has no item rows.")
        if len(request_numbers) != 1:
            raise RequestValidationError("The purchase request CSV must refer to a single purchase request.")
    except csv.Error as exc:
        raise RequestValidationError("Unable to parse the purchase request CSV.") from exc
    return count


def evaluate_cloud_upload(
    pdf_bytes: bytes,
    pdf_filename: str,
    request_csv_bytes: bytes,
    request_csv_filename: str,
) -> tuple[UploadedEvaluation, dict[str, PurchaseRequestLine]]:
    """Evaluate uploads without checking private input files into source control.

    The temporary request file exists only during evaluation, and the PDF upload
    adapter also deletes its own temporary PDF after use. This does not imply
    that the third-party hosting provider has an offline/zero-retention policy.
    """
    validate_request_csv(request_csv_bytes, request_csv_filename)
    with tempfile.TemporaryDirectory(prefix="supplierguard-request-") as directory:
        path = Path(directory) / "purchase-request.csv"
        path.write_bytes(request_csv_bytes)
        purchase_request = load_purchase_request(path)
        uploaded = evaluate_uploaded_pdf(pdf_bytes, pdf_filename, path)
        return uploaded, purchase_request
