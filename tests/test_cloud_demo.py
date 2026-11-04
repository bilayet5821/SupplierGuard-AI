from __future__ import annotations

import pytest
from supplierguard.cloud_demo import (
    RequestValidationError,
    evaluate_cloud_upload,
    validate_request_csv,
)
from supplierguard.models import Decision


def test_cloud_uploaded_sample_uses_existing_rules(task_data):
    pdf = (task_data / "supplier-pack-03.pdf").read_bytes()
    csv_bytes = (task_data / "purchase-request.csv").read_bytes()
    uploaded, request = evaluate_cloud_upload(pdf, "supplier-pack-03.pdf", csv_bytes, "purchase-request.csv")
    assert uploaded.result.decision == Decision.REJECT
    assert len(request) > 0


def test_cloud_uploaded_approved_sample(task_data):
    pdf = (task_data / "supplier-pack-01.pdf").read_bytes()
    csv_bytes = (task_data / "purchase-request.csv").read_bytes()
    uploaded, _ = evaluate_cloud_upload(pdf, "supplier-pack-01.pdf", csv_bytes, "purchase-request.csv")
    assert uploaded.result.decision == Decision.APPROVE


@pytest.mark.parametrize("data,filename", [
    (b"", "purchase-request.csv"),
    (b"something", "purchase-request.txt"),
    (b"Wrong,Headers\n1,2\n", "purchase-request.csv"),
])
def test_invalid_request_is_rejected(data, filename):
    with pytest.raises(RequestValidationError):
        validate_request_csv(data, filename)


def test_duplicate_codes_are_rejected(task_data):
    original = (task_data / "purchase-request.csv").read_text(encoding="utf-8-sig")
    lines = original.splitlines()
    duplicate = "\n".join([*lines, lines[1]]) + "\n"
    with pytest.raises(RequestValidationError, match="Duplicate"):
        validate_request_csv(duplicate.encode(), "purchase-request.csv")
