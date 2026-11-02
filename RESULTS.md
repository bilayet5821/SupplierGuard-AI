# SupplierGuard AI — Results and one-page engineering note

## What was built

A CPU-only local pipeline reads embedded PDF text page by page, deterministically extracts supplier identity, line item, quantities, prices, totals, delivery, payment, VAT, validity, and late-penalty terms, then applies the supplied rules using `Decimal`. A fixed LangGraph sequence orchestrates extraction, validation, and precedence aggregation. Streamlit exposes both the decision and its audit trail.

## Actual results on the 10 supplied PDFs

| Pack | Result | Decisive rule(s) | Actual page-1 supporting text |
|---|---|---|---|
| 01 | Approve | All checks pass | “10% advance payable with the purchase order. Balance payable within 45 days after delivery…”; “Delivery within 24 days…”; “Late delivery penalty: 1% of order value…”; “VAT 15% 849,600.00” |
| 02 | Approve | All checks pass | “No advance payment required. Full payment within 30 days of delivery.”; “within 21 days from the date of PO”; “0.75% of the order value per week” |
| 03 | Reject | PRICE-001 | “C Polyester sewing thread, cone 800 cone 229.00 183,200.00” (PR maximum: BDT 210.00; 9.05% over) |
| 04 | Needs Human Review | PRICE-001 | “D Poly bag, 30 x 40 cm 50,000 piece 6.65 332,500.00” (PR maximum: BDT 6.50; 2.31% over) |
| 05 | Reject | PAY-ADV-001 | “40% advance payable with the purchase order. 40% advance with the purchase order, balance 60% within 30 days of delivery.” |
| 06 | Reject | PENALTY-001 | “2. Delivery. Delivery within 27 days of PO.” is followed by “3. Validity. This quotation is valid for 30 days…”; no delay-penalty clause is present |
| 07 | Needs Human Review | QTY-001 | “B Metal zipper, 18 cm 16,500 piece 35.00 577,500.00” (PR quantity: 20,000; 17.50% variance) |
| 08 | Reject | ID-001 | “Supplier registration details available on request.”; neither a TIN nor BIN is shown |
| 09 | Needs Human Review | PAY-TERM-001, MATH-001 | “Payment within 30 to 90 days as agreed by both parties.”; “50,000 … 6.40 322,000.00” (multiplication equals 320,000.00) |
| 10 | Reject | DELIVERY-001 | “Delivery within 60 days of PO.” A secondary review issue is “Unit price (BDT, VAT included)” / “Total (all taxes included)” because VAT is not separately shown |

Decision distribution: **2 Approve, 5 Reject, 3 Needs Human Review**.

The repository contains no official expected-label file. I manually applied `company-rules.md` to form the transparent oracle above, then encoded it as regression assertions. The implemented system agrees on **10/10** packs with that oracle. This is not represented as accuracy against hidden ground truth.

## How it was tested

`python -m pytest -q` passes **56 tests** covering page extraction, typed fields, genuine page evidence, VAT-included handling, unclear range terms, week conversion, every requested price/quantity/advance/delivery/payment/penalty/validity boundary, arithmetic and VAT failures, missing identifiers, conservative missing-value handling, rejection precedence, modified temporary PDFs, filename independence, fixed graph topology, all ten decisions, UI presentation helpers, and Streamlit rendering. The Streamlit process also passed a local `/_stcore/health` smoke check and 1440×1000 browser captures at 100% scale in light and dark themes. Generated details are in `artifacts/evaluation-results.json` and `artifacts/evaluation-summary.csv`.

## What does not work well / what comes next

The parser is intentionally optimized for the supplied text-based quote layout; it does not perform OCR or generalize to arbitrary vendor templates. Natural-language clauses outside tested patterns will stop for human review. With production data, I would add OCR confidence, layout/table models, policy versioning, security limits, reviewer feedback, and a labelled multi-template evaluation set. Optional local-LLM extraction could be added only as a candidate generator; every numeric and compliance field would still require independent deterministic verification.
