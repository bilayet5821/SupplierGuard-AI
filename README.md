# SupplierGuard AI

SupplierGuard is a local, deterministic compliance checker for the supplied BIAI Task 1 procurement packs. It extracts each PDF page, structures the commercial fields, applies the exact company rules, and returns **Approve**, **Reject**, or **Needs Human Review** with page-numbered source quotations.

It uses no paid API, no network service, no LLM, and no autonomous agent. Task 2 is intentionally untouched.

## Results at a glance

The workflow processed all 10 supplied PDFs: **2 Approve, 5 Reject, and 3 Needs Human Review**. Its decisions agree on **10/10 packs** with the manually derived rules oracle documented in [RESULTS.md](RESULTS.md). The sample set contains no official label file, so this is transparent rules-oracle agreement, not a claim of accuracy against undisclosed ground truth.

## Architecture

```text
supplier PDF + purchase-request.csv
              │
              ▼
     page-level PyMuPDF text
              │
              ▼
 deterministic field extraction ──► Pydantic + Decimal models
              │
              ▼
 deterministic company-rule checks
              │
              ▼
 Reject > Needs Human Review > Approve
              │
              ▼
 Streamlit UI / JSON and CSV evaluation artifacts
```

LangGraph implements one fixed acyclic path:

```text
START → load_inputs → extract_fields → validate_rules → aggregate_decision → END
```

There are no tools, routers, retries, planning steps, or agent loops. Business logic remains in pure functions so it can be tested independently of orchestration and UI.

## Rule implementation

| Precedence | Condition | Result |
|---|---|---|
| 1 | Unit price is more than 3% over maximum | Reject |
| 1 | Advance is more than 20% | Reject |
| 1 | No late-delivery penalty; a stated rate below 0.5%/week is noncompliant | Reject |
| 1 | TIN or BIN missing | Reject |
| 1 | Delivery later than 45 days after PO | Reject |
| 2 | Unit price over maximum by no more than 3% | Needs Human Review |
| 2 | Absolute quantity variance over 5% | Needs Human Review |
| 2 | Payment unclear or outside inclusive 30–60 days after delivery | Needs Human Review |
| 2 | Delivery in inclusive 31–45 day range | Needs Human Review |
| 2 | VAT not separately shown at 15% | Needs Human Review |
| 2 | Line, subtotal, VAT, or total arithmetic mismatch | Needs Human Review |
| 2 | Validity under 30 days | Needs Human Review |
| 3 | No exception | Approve |

An unclear required value produces human review, never a guessed value. A present penalty that does not identify its percentage or order-value basis is also sent to review; a missing clause is rejected exactly as the rule requires. Four weeks is deterministically converted to 28 days.


## Required Sample Data

The original BIAI assessment files are not included in this
public repository.

To reproduce the evaluation, extract the BIAI-provided
Round 2 ZIP into the repository root.

Required directory structure:

BIAI-SupplierGuard-AI/
├── BIAI-AI-Engineer-Round2-Pack/
│   └── sample-data/
│       └── engineer/
│           └── task1-procurement/
│               ├── company-rules.md
│               ├── purchase-request.csv
│               ├── supplier-pack-01.pdf
│               ├── ...
│               └── supplier-pack-10.pdf
├── app.py
├── evaluate.py
├── requirements.txt
├── src/
└── tests/

After placing the supplied files, install dependencies
and run the application:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python -m pytest -q
python evaluate.py
python -m streamlit run app.py
```

The application requires no API key or external inference
service. It operates locally using the supplied data.


## Run locally (Windows 11 / Python 3.11)

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed by Streamlit. Select any of the ten supplied packs in the sidebar. The app shows the final decision, extracted values, every rule result, exact page-level evidence, raw extracted text, and a downloadable audit JSON.

No environment variables or API keys are required. The application is sized for CPU-only use and loads one small PDF at a time.

## Test and reproduce the evaluation

```powershell
python -m pytest -q
python evaluate.py
```

Git Bash equivalent:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python evaluate.py
python -m streamlit run app.py
```

The evaluation command requires exactly ten `supplier-pack-*.pdf` files and writes:

- `artifacts/evaluation-results.json` — complete extracted models, rule findings, and evidence.
- `artifacts/evaluation-summary.csv` — compact decision summary.

The supplied input files are opened read-only and are never rewritten. Runtime decisions use document content and purchase-request item codes; filenames are used only to discover the supplied PDFs. Test expectations are an independent manual oracle, not production decision logic.

## Project structure

```text
src/supplierguard/
  models.py       Typed Pydantic audit models
  pdf.py          Page-level PyMuPDF extraction
  inputs.py       Purchase-request CSV loader
  extraction.py   Deterministic field and terms parser
  validation.py   Decimal arithmetic, rules, precedence
  workflow.py     Fixed sequential LangGraph
  service.py      Small public service API
tests/             Extraction, boundary, evidence, graph, and 10-pack tests
app.py             Streamlit dashboard
evaluate.py        Reproducible batch evaluation
RESULTS.md         One-page results and limitations note
requirements.txt   Pinned direct dependencies
artifacts/          Reproducible generated outputs
```

## Extraction and evidence design

- PyMuPDF reads embedded text separately for each page.
- Regex parsing is deliberately constrained to the supplied quote layout; it does not invent absent fields.
- Monetary values use `Decimal`, including thresholds and arithmetic checks.
- Each extracted clause and line retains `{page, quote}` evidence.
- Pydantic models make missing values explicit with `None`.
- All rule findings—passes as well as exceptions—remain in the audit result.

## Honest limitations and next steps

- The supplied PDFs contain embedded text. Image-only scans are detected as missing extraction and sent for review, but OCR is not included to keep this submission lightweight.
- The parser targets the supplied quotation structure and commercial wording. More layout diversity would require table-region detection and a larger labelled regression set.
- Dates are retained exactly as printed; delivery is expressed relative to PO in these samples, so no PO date is fabricated.
- Penalty language without an explicit order-value basis is conservatively reviewed.
- There is no official ground-truth label file. The reported 10/10 figure is agreement with a documented manual reading of the supplied rules.
- In production, add PDF malware controls, file-size/page limits, OCR confidence, schema/versioned policies, reviewer overrides with audit identity, and monitoring on a larger representative corpus.
