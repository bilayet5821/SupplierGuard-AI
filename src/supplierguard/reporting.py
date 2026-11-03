from __future__ import annotations

import io
import re
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    CondPageBreak,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from xml.sax.saxutils import escape

from .models import CheckStatus, Decision, EvaluationResult, PurchaseRequestLine
from .presentation import (
    business_summary,
    issue_details,
    recommendations_for_result,
    rule_label,
    unique_evidence,
    unique_pages,
)


DHAKA = ZoneInfo("Asia/Dhaka")
STATUS_COLORS = {
    Decision.APPROVE: (colors.HexColor("#168451"), colors.HexColor("#E8F7EE")),
    Decision.REJECT: (colors.HexColor("#C93636"), colors.HexColor("#FFF0F0")),
    Decision.HUMAN_REVIEW: (colors.HexColor("#B97800"), colors.HexColor("#FFF5DC")),
}


def _ascii(text: object) -> str:
    value = "" if text is None else str(text)
    return (
        value.replace("–", "-")
        .replace("—", "-")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("•", "-")
    )


def _money(value: Decimal | None) -> str:
    return "Not shown" if value is None else f"BDT {value:,.2f}"


def _quantity(value: Decimal | None) -> str:
    if value is None:
        return "Not shown"
    return f"{value:,.0f}" if value == value.to_integral() else f"{value:,.2f}"


def audit_pdf_filename(result: EvaluationResult) -> str:
    identifier = result.extracted.quotation_number or result.extracted.supplier_name or "supplier-audit"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", identifier).strip("-._") or "supplier-audit"
    return f"{safe}-compliance-audit.pdf"


def generate_audit_pdf(
    result: EvaluationResult,
    purchase_request: dict[str, PurchaseRequestLine],
    generated_at: datetime | None = None,
) -> bytes:
    generated_at = generated_at or datetime.now(DHAKA)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=DHAKA)
    else:
        generated_at = generated_at.astimezone(DHAKA)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title="Supplier Document Compliance Audit",
        author="SupplierGuard AI",
        subject=f"Compliance audit for {result.source_file}",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#18324A"),
            alignment=TA_LEFT,
            spaceAfter=5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#18324A"),
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Small",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.2,
            leading=10.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyCompact",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12,
            spaceAfter=1.5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Status",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=1.5 * mm,
        )
    )

    def paragraph(text: object, style: str = "BodyCompact") -> Paragraph:
        return Paragraph(escape(_ascii(text)).replace("\n", "<br/>"), styles[style])

    def table(data, widths, header=True, font_size=8.2) -> Table:
        value = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        commands = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#AAB4BE")),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ]
        if header:
            commands.extend(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EDF2")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#18324A")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ]
            )
        for row in range(1 if header else 0, len(data)):
            if row % 2 == 0:
                commands.append(("BACKGROUND", (0, row), (-1, row), colors.HexColor("#F7F9FB")))
        value.setStyle(TableStyle(commands))
        return value

    def page_decorations(canvas, document) -> None:
        canvas.saveState()
        width, height = A4
        canvas.setStrokeColor(colors.HexColor("#9AA8B5"))
        canvas.setLineWidth(0.4)
        canvas.line(15 * mm, height - 12 * mm, width - 15 * mm, height - 12 * mm)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(colors.HexColor("#425466"))
        canvas.drawString(15 * mm, height - 9 * mm, "SupplierGuard AI | Compliance Audit")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(width - 15 * mm, height - 9 * mm, f"Page {document.page}")
        canvas.line(15 * mm, 12 * mm, width - 15 * mm, 12 * mm)
        canvas.drawString(15 * mm, 8 * mm, "Automated policy recommendation - not human authorization")
        canvas.drawRightString(
            width - 15 * mm,
            8 * mm,
            generated_at.strftime("Generated %Y-%m-%d %H:%M %Z"),
        )
        canvas.restoreState()

    pack = result.extracted
    story = [
        paragraph("SupplierGuard AI", "Small"),
        paragraph("Supplier Document Compliance Audit", "ReportTitle"),
    ]
    header_rows = [
        [paragraph("Supplier", "Small"), paragraph(pack.supplier_name or "Not extracted", "Small")],
        [paragraph("Quotation", "Small"), paragraph(pack.quotation_number or "Not extracted", "Small")],
        [paragraph("Quotation date", "Small"), paragraph(pack.quotation_date or "Not extracted", "Small")],
        [paragraph("Purchase request", "Small"), paragraph(pack.reference or "Not extracted", "Small")],
        [paragraph("Generated", "Small"), paragraph(generated_at.strftime("%Y-%m-%d %H:%M:%S %Z"), "Small")],
    ]
    story.extend([table(header_rows, [45 * mm, 120 * mm], header=False), Spacer(1, 4 * mm)])

    status_color, status_background = STATUS_COLORS[result.decision]
    status_table = Table(
        [
            [paragraph(result.decision.value.upper(), "Status")],
            [paragraph(business_summary(result), "BodyCompact")],
            [paragraph("Automated policy recommendation only; no human authorization is recorded.", "Small")],
        ],
        colWidths=[165 * mm],
    )
    status_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), status_background),
                ("BOX", (0, 0), (-1, -1), 1.2, status_color),
                ("TEXTCOLOR", (0, 0), (-1, 0), status_color),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([status_table, paragraph("Procurement summary", "Section")])

    if any(finding.rule_id == "UPLOAD-MULTI-ITEM" for finding in result.findings):
        story.append(
            paragraph(
                "Multiple line items were detected. The item summary below may be incomplete and must be verified by a human reviewer."
            )
        )

    summary_rows = [
        [paragraph("Item", "Small"), paragraph("Requested", "Small"), paragraph("Quoted", "Small"), paragraph("Difference", "Small")]
    ]
    if pack.items:
        for quoted in pack.items:
            requested = purchase_request.get(quoted.item_code)
            if requested:
                quantity_delta = quoted.quantity - requested.quantity_requested
                quantity_pct = abs(quantity_delta) / requested.quantity_requested * Decimal("100")
                price_delta = quoted.unit_price_bdt - requested.maximum_unit_price_bdt
                price_pct = price_delta / requested.maximum_unit_price_bdt * Decimal("100")
                requested_text = (
                    f"Qty {_quantity(requested.quantity_requested)} {requested.unit}\n"
                    f"Max unit price {_money(requested.maximum_unit_price_bdt)}"
                )
                quoted_text = (
                    f"Qty {_quantity(quoted.quantity)} {quoted.unit}\n"
                    f"Unit price {_money(quoted.unit_price_bdt)}\n"
                    f"Line amount {_money(quoted.amount_bdt)}"
                )
                difference_text = (
                    f"Quantity {quantity_delta:+,.0f} ({quantity_pct:.2f}%)\n"
                    f"Price {price_delta:+,.2f} BDT ({price_pct:+.2f}%)"
                )
            else:
                requested_text = "No matching purchase-request item"
                quoted_text = f"Qty {_quantity(quoted.quantity)} {quoted.unit}\nUnit price {_money(quoted.unit_price_bdt)}"
                difference_text = "Cannot compare reliably"
            summary_rows.append(
                [
                    paragraph(f"{quoted.item_code} - {quoted.description}", "Small"),
                    paragraph(requested_text, "Small"),
                    paragraph(quoted_text, "Small"),
                    paragraph(difference_text, "Small"),
                ]
            )
    else:
        summary_rows.append([paragraph("No complete item extracted", "Small"), "", "", ""])
    story.append(table(summary_rows, [45 * mm, 42 * mm, 42 * mm, 36 * mm]))

    terms_rows = [
        [paragraph("Commercial / identity field", "Small"), paragraph("Extracted value", "Small")],
        [paragraph("Subtotal", "Small"), paragraph(_money(pack.subtotal_bdt), "Small")],
        [paragraph("VAT", "Small"), paragraph(f"{pack.vat_percent}% / {_money(pack.vat_amount_bdt)}" if pack.vat_percent is not None else "Not separately shown", "Small")],
        [paragraph("Total", "Small"), paragraph(_money(pack.total_bdt), "Small")],
        [paragraph("Advance payment", "Small"), paragraph("Unclear" if pack.terms.advance_percent is None else f"{pack.terms.advance_percent}%", "Small")],
        [paragraph("Payment after delivery", "Small"), paragraph("Unclear" if pack.terms.payment_days_min is None else f"{pack.terms.payment_days_min}-{pack.terms.payment_days_max} days", "Small")],
        [paragraph("Delivery lead time", "Small"), paragraph("Unclear" if pack.terms.delivery_days is None else f"{pack.terms.delivery_days} days after PO", "Small")],
        [paragraph("Late-delivery penalty", "Small"), paragraph("Not clearly stated" if pack.terms.late_penalty_percent_per_week is None else f"{pack.terms.late_penalty_percent_per_week}% per week; order-value basis: {'yes' if pack.terms.late_penalty_mentions_order_value else 'unclear'}", "Small")],
        [paragraph("Quotation validity", "Small"), paragraph("Unclear" if pack.terms.validity_days is None else f"{pack.terms.validity_days} days", "Small")],
        [paragraph("Supplier TIN / BIN", "Small"), paragraph(f"TIN: {pack.tin or 'Not shown'} | BIN: {pack.bin or 'Not shown'}", "Small")],
    ]
    story.extend([Spacer(1, 2 * mm), table(terms_rows, [62 * mm, 103 * mm])])

    details = issue_details(result, purchase_request)
    story.extend([CondPageBreak(80 * mm), paragraph("Policy exceptions", "Section")])
    if not details:
        story.append(paragraph("No policy exceptions were found."))
    else:
        for index, (detail, finding) in enumerate(zip(details, result.exceptions), start=1):
            evidence_lines = [
                f'Page {evidence.page}: "{evidence.quote}"' for evidence in unique_evidence(finding)
            ] or ["No reliable source quotation available; human verification required."]
            exception_rows = [
                [paragraph("Issue", "Small"), paragraph(detail.issue_name, "Small")],
                [paragraph("Finding", "Small"), paragraph(detail.status.value.upper(), "Small")],
                [paragraph("Actual extracted value", "Small"), paragraph(detail.actual_value, "Small")],
                [paragraph("Policy requirement", "Small"), paragraph(detail.policy_requirement, "Small")],
                [paragraph("Measured difference", "Small"), paragraph(detail.measured_difference, "Small")],
                [paragraph("Evidence", "Small"), paragraph("\n".join(evidence_lines), "Small")],
                [paragraph("Policy reference", "Small"), paragraph(detail.rule_id, "Small")],
                [paragraph("Recommended action", "Small"), paragraph(detail.action, "Small")],
            ]
            story.append(
                KeepTogether(
                    [
                        paragraph(f"Exception {index}: {detail.issue_name}", "BodyCompact"),
                        table(exception_rows, [42 * mm, 123 * mm], header=False),
                        Spacer(1, 2.5 * mm),
                    ]
                )
            )

    story.extend([PageBreak(), paragraph("Complete rule audit", "Section")])
    audit_rows = [
        [
            paragraph("Check", "Small"),
            paragraph("Result", "Small"),
            paragraph("Explanation", "Small"),
            paragraph("Reference", "Small"),
            paragraph("Page(s)", "Small"),
        ]
    ]
    for finding in result.findings:
        audit_rows.append(
            [
                paragraph(rule_label(finding.rule_id), "Small"),
                paragraph(finding.status.value.upper(), "Small"),
                paragraph(finding.explanation, "Small"),
                paragraph(finding.rule_id, "Small"),
                paragraph(", ".join(map(str, unique_pages(finding))) or "None", "Small"),
            ]
        )
    story.append(table(audit_rows, [35 * mm, 25 * mm, 68 * mm, 25 * mm, 12 * mm], font_size=7.5))

    story.append(paragraph("Recommended actions", "Section"))
    for index, action in enumerate(recommendations_for_result(result, purchase_request), start=1):
        story.append(paragraph(f"{index}. {action}"))

    story.append(paragraph("Limitations and disclaimer", "Section"))
    disclaimer = (
        "SupplierGuard applies the supplied purchase request and company rules deterministically to text "
        "that can be extracted from the PDF. Missing or ambiguous values are not guessed and must be "
        "verified by a person. Delivery is reported as lead time after the purchase order because no PO "
        "date is supplied; no calendar delivery date is fabricated. This report is an automated policy "
        "recommendation and does not replace normal organizational purchasing, quality, legal, tax, or "
        "human authorization procedures."
    )
    story.append(paragraph(disclaimer))

    doc.build(story, onFirstPage=page_decorations, onLaterPages=page_decorations)
    return buffer.getvalue()
