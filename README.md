# 🛡️ SupplierGuard AI

**Evidence-backed supplier quotation compliance, built for reliable procurement decisions.**

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/Workflow-LangGraph-5555A5?style=flat-square)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)
![PDF Reports](https://img.shields.io/badge/Reports-ReportLab-175CD3?style=flat-square)
![Tests](https://img.shields.io/badge/Tests-88%20passed-238636?style=flat-square)
![Offline](https://img.shields.io/badge/Runtime-Offline%20%7C%20CPU--only-0B7285?style=flat-square)

> **BIAI AI Engineer — Round 2, Task 1.** SupplierGuard reads the assessment's supplier quotation PDFs, checks the associated purchase request and company policy, and returns **Approve**, **Reject**, or **Needs Human Review**—with reasons, source-page evidence, and next actions. The automated result **does not constitute human purchase authorization**.

**[Features](#-features) · [Results](#-evaluation-results) · [Setup](#-quick-start) · [Workflow](#-architecture) · [Limitations](#-limitations-and-engineering-choices)**

## ✨ Features

| Capability | What a procurement employee gets |
|---|---|
| 📄 **Supplier document extraction** | Supplier, item, quantity, unit price, totals, payment, VAT, delivery lead time, validity, and registration identifiers |
| ⚖️ **Policy validation** | Purchase-request comparison, precise `Decimal` arithmetic, and a transparent rule-by-rule audit |
| 🟢🟥🟡 **Three-way decision** | **Approve / Reject / Needs Human Review**, with `Reject > Review > Approve` precedence |
| 🧭 **Finding-specific actions** | Recommendations tied to actual violations, including multiple issues in the same quotation |
| ⬆️ **Supplier PDF upload** | Inspect an additional PDF in the **supported sample format**, using the same fixed workflow |
| 📥 **A4 PDF audit report** | Download an employee-readable report with decision, values, checks, evidence, and next actions |
| 🔎 **Traceable evidence** | Exact text excerpts tied to PDF page numbers, plus a JSON audit export |
| 🖥️ **Accessible dashboard** | Streamlit views for **Decision**, **Extracted Data**, **Rule Audit**, and **Source Evidence** |

The application runs **locally on a CPU**. No API key, hosted inference, model training, external AI call, or autonomous agent is used at runtime. AI coding tools were permitted for development; the shipped decision engine itself is **deterministic**, not an inference-time LLM.

## 📊 Evaluation results

![Approve](https://img.shields.io/badge/Approve-2-238636?style=flat-square)
![Reject](https://img.shields.io/badge/Reject-5-C62828?style=flat-square)
![Human Review](https://img.shields.io/badge/Needs%20Human%20Review-3-B7791F?style=flat-square)

All **10 BIAI-supplied PDFs** were processed with the same workflow. The resulting labels agree with the documented **manual rules oracle on 10/10 packs**. **This is not a claim of accuracy against an official or hidden ground-truth answer key**; BIAI did not provide one.

| Packs | Decision | Representative reason |
|---|---|---|
| 01, 02 | ✅ Approve | Required checks passed |
| 03, 05, 06, 08, 10 | ❌ Reject | Excess price / advance, missing penalty or registration, late delivery |
| 04, 07, 09 | ⚠️ Needs Human Review | Price tolerance, quantity deviation, unclear payment or arithmetic |

**Latest locally verified run:** `88 passed, 14 warnings` (`python -m pytest -q`), with the same **2 / 5 / 3** evaluation distribution after the feature upgrades. Warnings are dependency deprecations, not test failures. See [RESULTS.md](RESULTS.md) for the engineering summary.

## 🧩 Architecture

```text
Supplied PDF or supported uploaded PDF
                 │
       Upload / PDF safety checks
                 │
                 ▼
        Page-level PyMuPDF text
                 │
                 ▼
      Deterministic field extraction
          Pydantic + Decimal
                 │
                 ▼
      Purchase request comparison
                 │
                 ▼
       Company policy rule checks
                 │
                 ▼
   Reject > Needs Human Review > Approve
                 │
       ┌─────────┼───────────┐
       ▼         ▼           ▼
   Streamlit  A4 PDF audit   JSON / CSV
   dashboard  + actions     evidence
```

The core orchestration is a **fixed, acyclic LangGraph** path:

```text
START → load_inputs → extract_fields → validate_rules → aggregate_decision → END
```

There is no open-ended agent planner or tool-calling loop. Extraction, validation, presentation, and reporting are separated so policy decisions can be tested independently. Unclear, unsupported, or missing required fields **must never be guessed or silently approved**.

## 📋 Implemented company-rule checks

| Severity | Policy condition | Outcome |
|---|---|---|
| 🔴 | Unit price **more than 3%** above PR maximum | Reject |
| 🔴 | Advance **more than 20%** | Reject |
| 🔴 | Missing required late-delivery penalty clause, or a stated penalty below **0.5%/week** | Reject |
| 🔴 | Missing supplier TIN or BIN | Reject |
| 🔴 | Delivery **over 45 days** after purchase order | Reject |
| 🟠 | Price above maximum but **no more than 3%** above | Human Review |
| 🟠 | Absolute quoted-quantity variance **over 5%** | Human Review |
| 🟠 | Payment terms unclear or outside **30–60 days** after delivery | Human Review |
| 🟠 | Delivery **31–45 days** after purchase order | Human Review |
| 🟠 | **15% VAT** not shown separately | Human Review |
| 🟠 | Line, subtotal, VAT, or final-total arithmetic mismatch | Human Review |
| 🟠 | Quotation validity **under 30 days** | Human Review |
| 🟢 | No applicable exception | Approve |

Rejection has precedence when multiple issues occur; other findings remain visible. Four weeks is normalized to 28 days where supported by the source wording. Delivery lead times are **not converted to invented calendar dates** when a purchase-order date is absent. The supplied `company-rules.md` is the policy source of truth.

## 🗂️ Required assessment data

**The original BIAI brief, rules, purchase request, and supplier PDFs are not published in this public repository.** Evaluators should use the BIAI-provided ZIP, extracted alongside `app.py` in the repository root:

```text
SupplierGuard-AI/
├── BIAI-AI-Engineer-Round2-Pack/
│   ├── BIAI-AI-Engineer-Round2-Brief.md
│   └── sample-data/
│       └── engineer/
│           └── task1-procurement/
│               ├── company-rules.md
│               ├── purchase-request.csv
│               ├── supplier-pack-01.pdf
│               ├── ...
│               └── supplier-pack-10.pdf
├── src/supplierguard/
├── tests/
├── app.py
├── evaluate.py
├── requirements.txt
├── README.md
└── RESULTS.md
```

**Do not test with real supplier, company, or customer data for this hiring exercise.** Uploaded-file demonstrations should use copies or controlled modifications of the BIAI-supplied fictional samples only.

## 🚀 Quick start

**Requirements:** Windows / macOS / Linux, a working Python installation (Python **3.11** recommended), and the assessment files placed as shown above. The app uses CPU only; no GPU or paid credentials are needed.

### Option A — Windows Git Bash

```bash
# From your chosen working directory
git clone https://github.com/bilayet5821/SupplierGuard-AI.git
cd SupplierGuard-AI

# Extract the supplied BIAI ZIP here before running the app
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

### Option B — Windows PowerShell

```powershell
git clone https://github.com/bilayet5821/SupplierGuard-AI.git
cd SupplierGuard-AI

# Extract the supplied BIAI ZIP here before running the app
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the **Local URL** printed by Streamlit (commonly `http://localhost:8501`; your port may differ). `localhost` is **not a publicly accessible demo link**.

### Using the dashboard

1. In **Document source**, choose **BIAI supplied samples** or **Upload supplier PDF**.
2. Select a supplied pack, or upload a **supported, text-based sample-format PDF**.
3. Review **Final decision**, supplier values, policy issues, and **finding-specific recommended actions**.
4. Switch among **Decision**, **Extracted Data**, **Rule Audit**, and **Source Evidence**.
5. Select **Download Audit Report (PDF)** for a formatted A4 report; JSON audit data is also available for technical inspection.

The upload path validates PDF input and handles invalid, encrypted, empty, image-only, or unsupported files conservatively. It is **not a general-purpose arbitrary-template parser**. A PDF that cannot be reliably processed must not be treated as approved.

## 🧪 Tests and reproducible evaluation

With the environment active and supplied files in place:

```bash
python -m pytest -q
python evaluate.py
```

The latest provided local outputs were:

```text
88 passed, 14 warnings
Evaluated 10 documents
Approve: 2
Reject: 5
Needs Human Review: 3
```

`evaluate.py` creates local files (intentionally ignored by Git):

- `artifacts/evaluation-results.json` — extracted data, findings, and source evidence.
- `artifacts/evaluation-summary.csv` — one-row-per-pack decision summary.

The tests cover original samples, rule boundaries, evidence integrity, derived PDF modifications, upload safeguards, finding-specific recommendations, reporting, and UI helpers. This evaluation does **not** establish performance on unrelated real-world document layouts.

## 📁 Project structure

```text
app.py                     Streamlit UI and download controls
evaluate.py                Batch evaluation of the 10 supplied packs
src/supplierguard/
  models.py                Typed Pydantic data and findings
  pdf.py                   Page-level PDF text extraction
  inputs.py                Purchase-request CSV loading
  extraction.py            Deterministic field extraction
  validation.py            Compliance rules and precedence
  workflow.py              Fixed sequential LangGraph
  service.py               Service entry points
  presentation.py          Plain-English explanations and recommendations
  uploads.py               Uploaded-PDF validation and safety checks
  reporting.py             Professional ReportLab audit PDFs
tests/                     Unit, boundary, upload, report, and regression tests
RESULTS.md                 Engineering results and limitations
requirements.txt           Pinned project dependencies
```

## ⚠️ Limitations and engineering choices

- **Deterministic, not generative:** No inference-time LLM or autonomous agent is used. This supports reproducibility and reduces unsupported approval decisions, but limits natural-language generalization.
- **Layout scope:** Extraction is optimized for the provided **text-based quotation layouts**. Unfamiliar templates, scanned/image-only PDFs, and complex multi-item documents may be rejected at intake or require human review; OCR is not included.
- **Human authority:** **Approve** means automated policy checks passed, **not** that a procurement officer approved or placed an order.
- **Evidence integrity:** Values and issue explanations are tied to source-page quotations. Missing or ambiguous information is not filled in by inference.
- **Evaluation scope:** The **10/10** result is agreement with a manual rules oracle—not independent hidden-label accuracy or production validation.
- **Deployment:** Production use would need authentication, secure document storage, malware scanning, audit identities, policy versioning, monitoring, and testing on a larger representative dataset. No production deployment claim is made here.

## 📌 Assessment deliverables

- ✅ Reproducible code and setup instructions
- ✅ Ten-document evaluation and transparent results
- ✅ Human-readable PDF audit export and finding-level recommendations
- 📹 **Loom walkthrough (5 minutes or less):** to be provided with the hiring submission
- 📝 **One-page technical note:** see [RESULTS.md](RESULTS.md) (check one-page pagination if exporting for submission)

---

**Scope:** BIAI AI Engineer Round 2 — Task 1 only. Assessment data remains outside the public repository.


## ☁️ Streamlit Community Cloud demo

The BIAI-provided PDFs and `purchase-request.csv` are **not committed** to this
public repository. When these local files are missing, the app switches to a
cloud-safe demo screen. Upload both the **BIAI-provided purchase-request CSV**
and **one BIAI supplier quotation PDF**. The existing fixed LangGraph workflow
then produces the decision, cited findings, and a downloadable audit PDF.

Cloud-mode CSV validation checks the expected headers, numeric fields, duplicate
item codes, file size and row count. PDF validation checks structural and text
requirements. Files are temporarily used during processing and are not deliberately
saved by SupplierGuard. **Cloud uploads are processed on the hosting provider's
server**, not on your computer. Do not upload real/confidential company or customer
data. For this assessment, use only the fictional BIAI samples and controlled
sample-derived copies.

To deploy: go to https://share.streamlit.io, sign in with GitHub, create an app,
and select `bilayet5821/SupplierGuard-AI`, branch `main`, entrypoint `app.py`.
Select a compatible Python version under Advanced settings (prefer Python 3.11
if offered). Dependencies are specified in `requirements.txt`. The public app
URL is assigned by Streamlit once deployment succeeds.

**Limitations:** The upload parser is intentionally restricted to BIAI-like,
text-based single-item supplier quotation layouts. Unsupported, scanned,
encrypted or unreadable documents are sent for human review. Automated
approval never represents recorded purchase-order authorization.
