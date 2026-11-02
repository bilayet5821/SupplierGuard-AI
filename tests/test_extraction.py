from decimal import Decimal

from supplierguard.extraction import extract_supplier_pack
from supplierguard.pdf import extract_pdf_pages


def test_pdf_extraction_preserves_page_evidence(task_data):
    document = extract_pdf_pages(task_data / "supplier-pack-01.pdf")
    assert len(document.pages) == 1
    assert "Padma Textile Mills Ltd" in document.pages[0].text
    assert document.pages[0].page == 1


def test_structured_extraction_for_standard_pack(task_data):
    pack = extract_supplier_pack(extract_pdf_pages(task_data / "supplier-pack-01.pdf"))
    assert pack.supplier_name == "Padma Textile Mills Ltd"
    assert pack.quotation_number == "QT-2026-901"
    assert pack.reference == "PR-2026-114"
    assert pack.items[0].item_code == "A"
    assert pack.items[0].quantity == Decimal("12000")
    assert pack.items[0].unit_price_bdt == Decimal("472.00")
    assert pack.vat_percent == Decimal("15")
    assert pack.terms.delivery_days == 24
    assert pack.terms.payment_days_max == 45
    assert pack.terms.late_penalty_percent_per_week == Decimal("1")
    assert pack.evidence["delivery"][0].page == 1


def test_weeks_and_unclear_payment_are_parsed_without_guessing(task_data):
    pack = extract_supplier_pack(extract_pdf_pages(task_data / "supplier-pack-09.pdf"))
    assert pack.terms.delivery_days == 28
    assert pack.terms.payment_days_min == 30
    assert pack.terms.payment_days_max == 90


def test_vat_included_is_not_misread_as_separate_vat(task_data):
    pack = extract_supplier_pack(extract_pdf_pages(task_data / "supplier-pack-10.pdf"))
    assert pack.vat_percent is None
    assert pack.vat_amount_bdt is None
    assert pack.total_bdt == Decimal("282000.00")
