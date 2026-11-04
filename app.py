from __future__ import annotations

import json
import sys
from decimal import Decimal
from html import escape
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from supplierguard.models import CheckStatus, Decision  # noqa: E402
from supplierguard.inputs import load_purchase_request  # noqa: E402
from supplierguard.pdf import extract_pdf_pages  # noqa: E402
from supplierguard.presentation import (  # noqa: E402
    business_explanation,
    business_summary,
    issue_details,
    recommendations_for_result,
    rule_label,
    status_label,
    unique_evidence,
    unique_pages,
)
from supplierguard.reporting import audit_pdf_filename, generate_audit_pdf  # noqa: E402
from supplierguard.uploads import (  # noqa: E402
    MAX_UPLOAD_BYTES,
    UploadValidationError,
    evaluate_uploaded_pdf,
)
from supplierguard.workflow import run_workflow  # noqa: E402
from supplierguard.cloud_demo import RequestValidationError, evaluate_cloud_upload  # noqa: E402


DATA_DIR = (
    ROOT
    / "BIAI-AI-Engineer-Round2-Pack"
    / "sample-data"
    / "engineer"
    / "task1-procurement"
)
PR_CSV = DATA_DIR / "purchase-request.csv"


st.set_page_config(
    page_title="SupplierGuard AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
    <style>
      .block-container {
        max-width: 1180px;
        padding-top: 3.5rem;
        padding-bottom: 3rem;
      }
      h1 {letter-spacing: -0.025em;}
      .sg-eyebrow {
        color: var(--text-color);
        font-size: .72rem;
        font-weight: 700;
        letter-spacing: .085em;
        opacity: .68;
        text-transform: uppercase;
      }
      .sg-decision {
        border: 1px solid rgba(128, 128, 128, .28);
        border-left-width: 6px;
        border-radius: 14px;
        box-shadow: 0 3px 14px rgba(0, 0, 0, .06);
        margin: 1rem 0 1.35rem;
        padding: 1.15rem 1.3rem;
      }
      .sg-decision--approve {background: #e8f7ee; border-left-color: #168451; color: #103f2a;}
      .sg-decision--reject {background: #fff0f0; border-left-color: #c93636; color: #681f1f;}
      .sg-decision--review {background: #fff5dc; border-left-color: #b97800; color: #604400;}
      .sg-decision .sg-eyebrow {color: inherit; opacity: .78;}
      .sg-decision__title {
        color: inherit;
        font-size: clamp(1.35rem, 2.4vw, 1.85rem);
        font-weight: 750;
        line-height: 1.2;
        margin: .18rem 0 .42rem;
      }
      .sg-decision__summary {color: inherit; line-height: 1.55; max-width: 920px;}
      .sg-action {
        background: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, .3);
        border-radius: 12px;
        color: var(--text-color);
        line-height: 1.55;
        margin: -0.45rem 0 1.3rem;
        padding: .9rem 1.05rem;
      }
      .sg-action__title {font-size: .82rem; font-weight: 750; margin-bottom: .25rem;}
      .sg-action ol {margin: .35rem 0 0 1.2rem; padding: 0;}
      .sg-action li {margin: .25rem 0;}
      .sg-kpi-grid {
        display: grid;
        gap: .85rem;
        grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
        margin: 0 0 1.5rem;
      }
      .sg-kpi {
        background: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, .32);
        border-radius: 12px;
        color: var(--text-color) !important;
        min-height: 94px;
        padding: .85rem 1rem;
      }
      .sg-kpi__label {
        color: var(--text-color) !important;
        font-size: .78rem;
        font-weight: 650;
        letter-spacing: .025em;
        opacity: .72;
      }
      .sg-kpi__value {
        color: var(--text-color) !important;
        font-size: clamp(1rem, 1.7vw, 1.25rem);
        font-weight: 700;
        line-height: 1.25;
        margin-top: .42rem;
        overflow-wrap: anywhere;
      }
      .sg-driver {
        background: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, .28);
        border-radius: 10px;
        color: var(--text-color);
        margin: .65rem 0;
        padding: .85rem 1rem;
      }
      .sg-driver__rule {font-size: .82rem; font-weight: 700; margin-bottom: .25rem;}
      .sg-issue {
        background: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, .28);
        border-left-width: 4px;
        border-radius: 10px;
        color: var(--text-color);
        margin: .65rem 0;
        padding: .85rem 1rem;
      }
      .sg-issue--reject {border-left-color: #c93636;}
      .sg-issue--review {border-left-color: #b97800;}
      .sg-issue__top {align-items: center; display: flex; flex-wrap: wrap; gap: .45rem; margin-bottom: .35rem;}
      .sg-issue__name {font-weight: 750;}
      .sg-reference {font-size: .72rem; opacity: .65;}
      .sg-status {
        border-radius: 999px;
        font-size: .7rem;
        font-weight: 800;
        letter-spacing: .04em;
        padding: .2rem .5rem;
      }
      .sg-status--reject {background: #fde0e0; color: #771e1e;}
      .sg-status--review {background: #ffedbd; color: #674500;}
      .sg-detail-grid {
        display: grid;
        gap: .65rem;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        margin: .4rem 0 1rem;
      }
      .sg-detail {
        background: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, .25);
        border-radius: 9px;
        color: var(--text-color);
        min-height: 70px;
        padding: .68rem .8rem;
      }
      .sg-detail__label {font-size: .72rem; font-weight: 700; opacity: .68;}
      .sg-detail__value {font-weight: 650; line-height: 1.35; margin-top: .28rem; overflow-wrap: anywhere;}
      .sg-help {color: var(--text-color); font-size: .86rem; line-height: 1.5; opacity: .72;}
      .sg-facts {
        display: grid;
        gap: .45rem;
        grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
        margin-top: .6rem;
      }
      .sg-fact {border-top: 1px solid rgba(128, 128, 128, .22); padding-top: .42rem;}
      .sg-fact__label {font-size: .68rem; font-weight: 750; opacity: .62; text-transform: uppercase;}
      .sg-fact__value {font-size: .84rem; line-height: 1.4; margin-top: .2rem;}
      .sg-note {
        background: rgba(55, 115, 180, .12);
        border: 1px solid rgba(80, 125, 175, .25);
        border-radius: 9px;
        color: var(--text-color) !important;
        line-height: 1.5;
        padding: .75rem .9rem;
      }
      .sg-quote {
        background: var(--secondary-background-color);
        border-left: 3px solid var(--primary-color);
        border-radius: 5px;
        color: var(--text-color) !important;
        line-height: 1.5;
        margin: .45rem 0;
        padding: .7rem .9rem;
      }
      [data-testid="stSegmentedControl"] {margin: .25rem 0 1rem;}
      [data-testid="stSegmentedControl"] button {
        font-size: .94rem;
        font-weight: 750;
        min-height: 44px;
        padding-left: 1rem;
        padding-right: 1rem;
      }
      @media (max-width: 700px) {
        .block-container {padding-left: 1rem; padding-right: 1rem; padding-top: 2.25rem;}
        .sg-decision {padding: 1rem;}
        .sg-kpi-grid {grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));}
        [data-testid="stSegmentedControl"] button {font-size: .8rem; padding-left: .55rem; padding-right: .55rem;}
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def evaluate(pdf_path: str):
    return run_workflow(pdf_path, PR_CSV)


@st.cache_data(show_spinner=False)
def evaluate_upload(pdf_bytes: bytes, filename: str):
    return evaluate_uploaded_pdf(pdf_bytes, filename, PR_CSV)


def money(value):
    return "—" if value is None else f"BDT {value:,.2f}"


def quantity(value) -> str:
    if value is None:
        return "—"
    return f"{value:,.0f}" if value == value.to_integral() else f"{value:,.2f}"


def plural_unit(unit: str, value) -> str:
    if value == 1:
        return unit
    return {"piece": "pieces", "metre": "metres", "cone": "cones"}.get(unit, unit)


def render_kpis(values: list[tuple[str, str]]) -> None:
    cards = "".join(
        '<div class="sg-kpi">'
        f'<div class="sg-kpi__label">{escape(label)}</div>'
        f'<div class="sg-kpi__value">{escape(value)}</div>'
        "</div>"
        for label, value in values
    )
    st.markdown(f'<div class="sg-kpi-grid">{cards}</div>', unsafe_allow_html=True)


def render_details(values: list[tuple[str, str | None]]) -> None:
    cards = "".join(
        '<div class="sg-detail">'
        f'<div class="sg-detail__label">{escape(label)}</div>'
        f'<div class="sg-detail__value">{escape(value or "Not shown")}</div>'
        "</div>"
        for label, value in values
    )
    st.markdown(f'<div class="sg-detail-grid">{cards}</div>', unsafe_allow_html=True)


with st.sidebar:
    st.markdown("### SupplierGuard AI")
    st.caption("Deterministic procurement compliance")
    files = sorted(DATA_DIR.glob("supplier-pack-*.pdf"))
    local_samples_available = bool(files) and PR_CSV.is_file()
    source_options = (
        ["BIAI supplied samples", "Upload supplier PDF"]
        if local_samples_available
        else ["Upload supplier PDF"]
    )
    source_mode = st.radio("Document source", source_options)
    selected = None
    uploaded_file = None
    request_file = None
    if source_mode == "BIAI supplied samples":
        selected = st.selectbox(
            "Supplier pack",
            files,
            format_func=lambda path: path.stem.replace("supplier-pack-", "Pack "),
        )
    else:
        if not PR_CSV.is_file():
            st.caption("Cloud demo: upload the fictional BIAI purchase request and supplier PDF. Uploaded files are processed on the hosting server. Do not use confidential data.")
            request_file = st.file_uploader(
                "Purchase request CSV",
                type=["csv"],
                help="Use the purchase-request.csv supplied in the BIAI Round 2 ZIP.",
            )
        uploaded_file = st.file_uploader(
            "Supplier quotation PDF",
            type=["pdf"],
            help=(
                f"Maximum {MAX_UPLOAD_BYTES // (1024 * 1024)} MB and 10 pages. "
                "Optimized for the supplied BIAI quotation format; "
                "scans and arbitrary templates require human review."
            ),
        )
        st.caption(
            "Assessment note: test uploads only with copies or controlled modifications of the supplied BIAI samples."
        )
    st.divider()
    st.markdown("**Fixed workflow**")
    st.caption("1. Read PDF pages\n\n2. Extract fields\n\n3. Apply rules\n\n4. Aggregate decision")
    st.markdown(
        '<div class="sg-note">No API key, network call, LLM, or autonomous agent is used.</div>',
        unsafe_allow_html=True,
    )

st.markdown('<div class="sg-eyebrow">SupplierGuard AI · Procurement compliance demo</div>', unsafe_allow_html=True)
st.title("Supplier Document Compliance Review")
st.caption("Traceable decisions with page-level evidence. Missing or unclear values are never guessed.")

if source_mode == "BIAI supplied samples" and not local_samples_available:
    st.error("The local BIAI sample files or purchase request are missing. Switch to upload mode.")
    st.stop()
if source_mode == "Upload supplier PDF" and uploaded_file is None:
    st.info("Upload a supported BIAI supplier quotation PDF to begin.")
    st.stop()
if source_mode == "Upload supplier PDF" and not PR_CSV.is_file() and request_file is None:
    st.info("Upload the BIAI purchase-request.csv to compare the quotation against its requested quantities and prices.")
    st.stop()

with st.spinner("Running the fixed compliance workflow…"):
    upload_metadata = None
    if source_mode == "BIAI supplied samples":
        result = evaluate(str(selected))
        purchase_request = load_purchase_request(PR_CSV)
    else:
        try:
            if PR_CSV.is_file():
                uploaded = evaluate_upload(uploaded_file.getvalue(), uploaded_file.name)
                purchase_request = load_purchase_request(PR_CSV)
            else:
                uploaded, purchase_request = evaluate_cloud_upload(
                    uploaded_file.getvalue(),
                    uploaded_file.name,
                    request_file.getvalue(),
                    request_file.name,
                )
        except (UploadValidationError, RequestValidationError) as exc:
            st.error(str(exc))
            st.warning(
                "Result: Needs Human Review. SupplierGuard stopped because the uploaded input could not be validated reliably."
            )
            st.stop()
        result = uploaded.result
        upload_metadata = uploaded.metadata

pack = result.extracted
multi_item_upload = bool(upload_metadata and upload_metadata.detected_item_rows > 1)
item = pack.items[0] if len(pack.items) == 1 and not multi_item_upload else None
requested_item = purchase_request.get(item.item_code) if item else None
recommendations = recommendations_for_result(result, purchase_request)
details = issue_details(result, purchase_request)
decision_class = {
    Decision.APPROVE: "approve",
    Decision.REJECT: "reject",
    Decision.HUMAN_REVIEW: "review",
}[result.decision]
st.markdown(
    f'<section class="sg-decision sg-decision--{decision_class}">'
    '<div class="sg-eyebrow">Final decision</div>'
    f'<div class="sg-decision__title">{escape(result.decision.value)}</div>'
    f'<div class="sg-decision__summary">{escape(business_summary(result))}</div>'
    "</section>",
    unsafe_allow_html=True,
)
st.markdown(
    '<section class="sg-action">'
    '<div class="sg-action__title">Recommended action(s)</div>'
    "<ol>"
    + "".join(f"<li>{escape(action)}</li>" for action in recommendations)
    + "</ol>"
    "</section>",
    unsafe_allow_html=True,
)

render_kpis(
    [
        ("Supplier", pack.supplier_name or "Unknown"),
        ("Quotation", pack.quotation_number or "Unknown"),
        ("Quoted total", money(pack.total_bdt)),
        (
            "Quoted quantity",
            (
                f"{quantity(item.quantity)} {plural_unit(item.unit, item.quantity)}"
                if item
                else ("Multiple items — review" if multi_item_upload else "Unknown")
            ),
        ),
        ("Policy issues", str(len(result.exceptions))),
    ]
)

report_bytes = generate_audit_pdf(result, purchase_request)
download_column, note_column = st.columns([1, 2])
with download_column:
    st.download_button(
        "Download Audit Report (PDF)",
        data=report_bytes,
        file_name=audit_pdf_filename(result),
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )
with note_column:
    st.caption(
        "Professional A4 audit with procurement values, every policy check, exact evidence, and issue-specific actions."
    )

section = st.segmented_control(
    "Review section",
    ["Decision", "Extracted Data", "Rule Audit", "Source Evidence"],
    default="Decision",
    label_visibility="collapsed",
)

if section == "Decision":
    st.subheader("Policy issues")
    if result.decision == Decision.APPROVE:
        st.markdown(
            '<div class="sg-driver"><strong>No policy issues found.</strong><br>'
            "All automated checks passed. The complete check-by-check record remains available "
            "in Rule audit.</div>",
            unsafe_allow_html=True,
        )
    else:
        issue_order = {CheckStatus.REJECT: 0, CheckStatus.HUMAN_REVIEW: 1}
        issues = sorted(
            zip(result.exceptions, details),
            key=lambda pair: issue_order[pair[0].status],
        )
        for finding, detail in issues:
            issue_class = (
                "reject" if finding.status == CheckStatus.REJECT else "review"
            )
            issue_status = (
                "BLOCKS PURCHASE"
                if finding.status == CheckStatus.REJECT
                else "HUMAN CHECK NEEDED"
            )
            st.markdown(
                f'<div class="sg-issue sg-issue--{issue_class}">'
                '<div class="sg-issue__top">'
                f'<span class="sg-status sg-status--{issue_class}">{issue_status}</span>'
                f'<span class="sg-issue__name">{escape(detail.issue_name)}</span>'
                f'<span class="sg-reference">Policy reference {escape(finding.rule_id)}</span>'
                "</div>"
                f'<div>{escape(business_explanation(finding))}</div>'
                '<div class="sg-facts">'
                '<div class="sg-fact"><div class="sg-fact__label">Supplier value</div>'
                f'<div class="sg-fact__value">{escape(detail.actual_value)}</div></div>'
                '<div class="sg-fact"><div class="sg-fact__label">Policy requirement</div>'
                f'<div class="sg-fact__value">{escape(detail.policy_requirement)}</div></div>'
                '<div class="sg-fact"><div class="sg-fact__label">Measured difference</div>'
                f'<div class="sg-fact__value">{escape(detail.measured_difference)}</div></div>'
                "</div>"
                "</div>",
                unsafe_allow_html=True,
            )
        if result.decision == Decision.REJECT and any(
            finding.status == CheckStatus.HUMAN_REVIEW for finding in result.findings
        ):
            st.caption(
                "Review-level issues are shown because they still need correction, although any rejection issue determines the final result."
            )
        st.caption("Open Rule audit for every check, policy reference, threshold explanation, and exact supporting quote.")

if section == "Extracted Data":
    st.subheader("Document details")
    st.markdown(
        '<div class="sg-help">Values read from the supplier quotation. “Not shown” means the value was not found and was not guessed.</div>',
        unsafe_allow_html=True,
    )
    render_details(
        [
            ("Supplier", pack.supplier_name),
            ("Quotation number", pack.quotation_number),
            ("Quotation date", pack.quotation_date),
            ("Purchase request", pack.reference),
            ("Supplier TIN", pack.tin),
            ("Supplier BIN", pack.bin),
        ]
    )

    st.subheader("Purchase request comparison")
    if item and requested_item:
        quantity_difference = item.quantity - requested_item.quantity_requested
        quantity_variance = (
            abs(quantity_difference) / requested_item.quantity_requested * Decimal("100")
        )
        price_difference = item.unit_price_bdt - requested_item.maximum_unit_price_bdt
        price_variance = (
            price_difference / requested_item.maximum_unit_price_bdt * Decimal("100")
        )
        quantity_finding = next(
            finding for finding in result.findings if finding.rule_id == "QTY-001"
        )
        price_finding = next(
            finding for finding in result.findings if finding.rule_id == "PRICE-001"
        )
        if quantity_difference == 0:
            quantity_difference_text = "No difference"
        else:
            direction = "more" if quantity_difference > 0 else "fewer"
            quantity_difference_text = (
                f"{quantity(abs(quantity_difference))} {direction} "
                f"({quantity_variance:.2f}% variance)"
            )
        if price_difference == 0:
            price_difference_text = "Matches maximum"
        elif price_difference > 0:
            price_difference_text = (
                f"BDT {price_difference:,.2f} above maximum ({price_variance:.2f}%)"
            )
        else:
            price_difference_text = f"BDT {abs(price_difference):,.2f} below maximum"
        st.dataframe(
            [
                {
                    "Comparison": "Quantity",
                    "Purchase request": (
                        f"{quantity(requested_item.quantity_requested)} "
                        f"{plural_unit(requested_item.unit, requested_item.quantity_requested)}"
                    ),
                    "Supplier quote": (
                        f"{quantity(item.quantity)} {plural_unit(item.unit, item.quantity)}"
                    ),
                    "Difference": quantity_difference_text,
                    "Assessment": status_label(quantity_finding.status),
                },
                {
                    "Comparison": "Unit price",
                    "Purchase request": (
                        f"Maximum {money(requested_item.maximum_unit_price_bdt)}"
                    ),
                    "Supplier quote": money(item.unit_price_bdt),
                    "Difference": price_difference_text,
                    "Assessment": status_label(price_finding.status),
                },
            ],
            hide_index=True,
            use_container_width=True,
        )
        st.caption(
            f"Item {item.item_code}: {item.description} · Quoted line amount {money(item.amount_bdt)}"
        )
    else:
        st.warning("A complete line item could not be matched to the purchase request. Human review is required.")

    terms_column, totals_column = st.columns(2)
    with terms_column:
        st.subheader("Commercial terms")
        if pack.terms.payment_days_min is None:
            payment_text = "Not clearly stated"
        elif pack.terms.payment_days_min == pack.terms.payment_days_max:
            payment_text = f"{pack.terms.payment_days_min} days after delivery"
        else:
            payment_text = (
                f"{pack.terms.payment_days_min}–{pack.terms.payment_days_max} days after delivery"
            )
        if pack.terms.late_penalty_percent_per_week is None:
            penalty_text = "Not clearly stated"
        else:
            penalty_text = f"{pack.terms.late_penalty_percent_per_week}% per week"
            if pack.terms.late_penalty_mentions_order_value:
                penalty_text += " of order value"
            else:
                penalty_text += " (order-value basis not clear)"
        render_details(
            [
                (
                    "Advance payment",
                    None
                    if pack.terms.advance_percent is None
                    else f"{pack.terms.advance_percent}%",
                ),
                ("Balance payment", payment_text),
                (
                    "Delivery lead time",
                    None
                    if pack.terms.delivery_days is None
                    else f"{pack.terms.delivery_days} days after PO",
                ),
                ("Late-delivery penalty", penalty_text),
                (
                    "Quotation validity",
                    None
                    if pack.terms.validity_days is None
                    else f"{pack.terms.validity_days} days",
                ),
            ]
        )
    with totals_column:
        st.subheader("Financial summary")
        render_details(
            [
                ("Subtotal", money(pack.subtotal_bdt)),
                (
                    "VAT rate",
                    None if pack.vat_percent is None else f"{pack.vat_percent}%",
                ),
                ("VAT amount", money(pack.vat_amount_bdt)),
                ("Quoted total", money(pack.total_bdt)),
            ]
        )

    with st.expander("Technical extracted data (JSON)"):
        st.caption("Optional machine-readable view for technical review and debugging.")
        st.json(pack.model_dump(mode="json"))

if section == "Rule Audit":
    st.subheader("Policy audit")
    st.markdown(
        '<div class="sg-help">Every automated check is shown below. REJECT blocks the purchase; REVIEW requires a human check; PASS meets the stated policy. Rejection takes precedence over review issues.</div>',
        unsafe_allow_html=True,
    )
    status_priority = {
        CheckStatus.REJECT: 0,
        CheckStatus.HUMAN_REVIEW: 1,
        CheckStatus.PASS: 2,
    }
    audit_findings = sorted(
        result.findings, key=lambda finding: status_priority[finding.status]
    )
    rows = [
        {
            "Check": rule_label(finding.rule_id),
            "Result": status_label(finding.status),
            "Details": finding.explanation,
            "Evidence page(s)": ", ".join(str(page) for page in unique_pages(finding)) or "—",
            "Policy reference": finding.rule_id,
        }
        for finding in audit_findings
    ]
    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.markdown("#### Supporting quotes")
    st.caption(
        "Open a check to verify its exact supplier-document wording. Quotes are whitespace-normalized and retain their PDF page."
    )
    for finding in audit_findings:
        quotes = unique_evidence(finding)
        if not quotes:
            continue
        pages = ", ".join(map(str, unique_pages(finding)))
        short_status = {
            CheckStatus.PASS: "PASS",
            CheckStatus.REJECT: "REJECT",
            CheckStatus.HUMAN_REVIEW: "REVIEW",
        }[finding.status]
        with st.expander(
            f"{short_status} · {rule_label(finding.rule_id)} · page(s) {pages} · {finding.rule_id}"
        ):
            for evidence in quotes:
                st.markdown(
                    '<div class="sg-quote">'
                    f'<strong>Page {evidence.page}</strong> — “{escape(evidence.quote)}”'
                    "</div>",
                    unsafe_allow_html=True,
                )

if section == "Source Evidence":
    st.subheader("Source document text")
    st.markdown(
        '<div class="sg-help">Use this read-only page text to verify extracted values against the supplier PDF. Page numbering matches the original document.</div>',
        unsafe_allow_html=True,
    )
    if upload_metadata is None:
        source_pages = [
            (page.page, page.text) for page in extract_pdf_pages(selected).pages
        ]
    else:
        source_pages = list(enumerate(upload_metadata.page_texts, start=1))
        st.caption(
            f"Uploaded file: {upload_metadata.original_filename} · {upload_metadata.page_count} page(s) · "
            f"SHA-256 {upload_metadata.sha256[:12]}… · processed temporarily and not retained"
        )
    for page_number, page_text in source_pages:
        with st.expander(
            f"Page {page_number} extracted text", expanded=page_number == 1
        ):
            st.text(page_text)

    json_payload = {
        "evaluation": result.model_dump(mode="json"),
        "recommendations": recommendations,
        "issue_details": [detail.as_dict() for detail in details],
        "source": {
            "mode": source_mode,
            "filename": result.source_file,
            "sha256": upload_metadata.sha256 if upload_metadata else None,
        },
    }
    st.download_button(
        "Download audit JSON",
        data=json.dumps(json_payload, indent=2, ensure_ascii=False),
        file_name=audit_pdf_filename(result).replace(".pdf", ".json"),
        mime="application/json",
    )
