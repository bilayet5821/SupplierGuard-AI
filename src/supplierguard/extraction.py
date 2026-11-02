from __future__ import annotations

import re
from decimal import Decimal

from .models import (
    Evidence,
    ExtractedSupplierPack,
    PdfDocument,
    QuotedItem,
    Terms,
)


MONEY = r"[\d,]+(?:\.\d+)?"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _decimal(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


def _match(pattern: str, text: str, flags: int = re.IGNORECASE) -> re.Match[str] | None:
    return re.search(pattern, text, flags)


def _ev(page: int, quote: str) -> Evidence:
    return Evidence(page=page, quote=_compact(quote))


def _extract_clauses(text: str) -> dict[str, str]:
    clauses: dict[str, str] = {}
    pattern = re.compile(
        r"(?:^|\s)(\d+)\.\s+([A-Za-z-]+)\.\s+(.*?)"
        r"(?=(?:\s+\d+\.\s+[A-Za-z-]+\.)|(?:\s+For\s+[^.]+$)|$)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        clauses[match.group(2).lower()] = _compact(
            f"{match.group(1)}. {match.group(2)}. {match.group(3)}"
        )
    return clauses


def extract_supplier_pack(document: PdfDocument) -> ExtractedSupplierPack:
    """Parse the supplied quote format with deterministic patterns only."""
    page_texts = [(page.page, _compact(page.text)) for page in document.pages]
    combined = " ".join(text for _, text in page_texts)
    first_page = page_texts[0][0]
    evidence: dict[str, list[Evidence]] = {}
    uncertainties: list[str] = []

    supplier_match = _match(r"^(.+?)\s+QUOTATION\b", combined)
    supplier_name = supplier_match.group(1).strip() if supplier_match else None
    if supplier_match:
        evidence["supplier_name"] = [_ev(first_page, supplier_match.group(1))]
    else:
        uncertainties.append("Supplier name could not be extracted.")

    header_match = _match(
        r"Quotation no\.\s+(\S+)\s+Date\s+(\d{4}-\d{2}-\d{2})\s+"
        r"To\s+.*?\s+Reference\s+(\S+)",
        combined,
    )
    quotation_number = quotation_date = reference = None
    if header_match:
        quotation_number, quotation_date, reference = header_match.groups()
        evidence["header"] = [_ev(first_page, header_match.group(0))]
    else:
        uncertainties.append("Quotation number, date, or reference could not be extracted.")

    item_pattern = re.compile(
        rf"\b([A-Z])\s+(.+?)\s+({MONEY})\s+(metre|piece|cone)\s+"
        rf"({MONEY})\s+({MONEY})(?=\s+(?:Subtotal|VAT|Total|Supplier))",
        re.IGNORECASE,
    )
    items: list[QuotedItem] = []
    for match in item_pattern.finditer(combined):
        quote = match.group(0)
        items.append(
            QuotedItem(
                item_code=match.group(1).upper(),
                description=match.group(2).strip(),
                quantity=_decimal(match.group(3)),
                unit=match.group(4).lower(),
                unit_price_bdt=_decimal(match.group(5)),
                amount_bdt=_decimal(match.group(6)),
            )
        )
        evidence.setdefault("items", []).append(_ev(first_page, quote))
    if not items:
        uncertainties.append("No complete quotation line item could be extracted.")

    subtotal_match = _match(rf"\bSubtotal\s+({MONEY})", combined)
    vat_match = _match(rf"\bVAT\s+(\d+(?:\.\d+)?)%\s+({MONEY})", combined)
    total_match = _match(rf"\bTotal(?:\s+\(all taxes included\))?\s+({MONEY})", combined)
    subtotal = _decimal(subtotal_match.group(1)) if subtotal_match else None
    vat_percent = _decimal(vat_match.group(1)) if vat_match else None
    vat_amount = _decimal(vat_match.group(2)) if vat_match else None
    total = _decimal(total_match.group(1)) if total_match else None
    totals_quotes = [m.group(0) for m in (subtotal_match, vat_match, total_match) if m]
    if totals_quotes:
        evidence["totals"] = [_ev(first_page, quote) for quote in totals_quotes]

    identifier_match = _match(
        r"Supplier\s+TIN:\s*([A-Za-z0-9-]+)\s+BIN:\s*([A-Za-z0-9-]+)", combined
    )
    tin = bin_number = None
    if identifier_match:
        tin, bin_number = identifier_match.groups()
        evidence["identifiers"] = [_ev(first_page, identifier_match.group(0))]
    else:
        registration_match = _match(r"Supplier registration details[^.]*\.", combined)
        if registration_match:
            evidence["identifiers"] = [_ev(first_page, registration_match.group(0))]

    clauses = _extract_clauses(combined)
    for name, quote in clauses.items():
        evidence[name] = [_ev(first_page, quote)]

    payment = clauses.get("payment", "")
    advance_matches = re.findall(r"(\d+(?:\.\d+)?)%\s+advance", payment, re.IGNORECASE)
    if advance_matches:
        advance = max(_decimal(value) for value in advance_matches)
    elif re.search(r"No advance payment required", payment, re.IGNORECASE):
        advance = Decimal("0")
    else:
        advance = None

    range_match = _match(r"within\s+(\d+)\s+to\s+(\d+)\s+days", payment)
    single_payment_matches = re.findall(
        r"within\s+(\d+)\s+days(?:\s+(?:after|of)\s+delivery)?", payment, re.IGNORECASE
    )
    if range_match:
        payment_min, payment_max = int(range_match.group(1)), int(range_match.group(2))
    elif single_payment_matches:
        payment_min = payment_max = int(single_payment_matches[-1])
    else:
        payment_min = payment_max = None
    payment_clear = bool(
        payment
        and payment_min is not None
        and re.search(r"delivery", payment, re.IGNORECASE)
    )

    delivery = clauses.get("delivery", "")
    delivery_days_match = _match(r"within\s+(\d+)\s+days", delivery)
    delivery_weeks_match = _match(r"within\s+(\d+)\s+weeks?", delivery)
    if delivery_days_match:
        delivery_days = int(delivery_days_match.group(1))
    elif delivery_weeks_match:
        delivery_days = int(delivery_weeks_match.group(1)) * 7
    else:
        delivery_days = None

    delay = clauses.get("delay", "")
    penalty_match = _match(r"(\d+(?:\.\d+)?)%", delay)
    penalty = _decimal(penalty_match.group(1)) if penalty_match else None

    validity = clauses.get("validity", "")
    validity_match = _match(r"valid for\s+(\d+)\s+days", validity)
    validity_days = int(validity_match.group(1)) if validity_match else None

    terms = Terms(
        advance_percent=advance,
        payment_days_min=payment_min,
        payment_days_max=payment_max,
        payment_is_clear=payment_clear,
        delivery_days=delivery_days,
        late_penalty_percent_per_week=penalty,
        late_penalty_mentions_order_value=bool(
            re.search(r"order value", delay, re.IGNORECASE)
        ),
        late_penalty_clause_present=bool(delay),
        validity_days=validity_days,
    )
    return ExtractedSupplierPack(
        source_file=document.source_file,
        supplier_name=supplier_name,
        quotation_number=quotation_number,
        quotation_date=quotation_date,
        reference=reference,
        items=items,
        subtotal_bdt=subtotal,
        vat_percent=vat_percent,
        vat_amount_bdt=vat_amount,
        total_bdt=total,
        tin=tin,
        bin=bin_number,
        terms=terms,
        evidence=evidence,
        uncertainties=uncertainties,
    )
