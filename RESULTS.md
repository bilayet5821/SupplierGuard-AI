# 🧾 SupplierGuard AI — Engineering Results & Limitations

![Tests](https://img.shields.io/badge/Automated%20tests-88%20passed-238636?style=flat-square)
![Documents](https://img.shields.io/badge/Sample%20PDFs-10%20evaluated-175CD3?style=flat-square)
![Runtime](https://img.shields.io/badge/Runtime-CPU%20%7C%20Offline-0B7285?style=flat-square)

> **BIAI AI Engineer — Round 2, Task 1** · Concise engineering note · **Last locally verified: 4 Nov 2026**

## 🔧 What I built

**SupplierGuard AI** is a local supplier-quotation checker for the fictional BIAI procurement pack. **PyMuPDF** extracts page-level text; deterministic parsing and **Pydantic** models capture supplier details, item/quantity/price, payment, VAT, delivery, registration and validity. **Decimal** arithmetic compares quotations with the supplied purchase request and company rules. A **fixed LangGraph sequence** produces **Approve**, **Reject**, or **Needs Human Review** (`Reject > Review > Approve`) with cited source evidence. A **Streamlit dashboard** displays plain-English explanations and finding-specific actions. The updated version includes **supported-format PDF uploads**, **A4 ReportLab audit downloads**, and JSON audit export. No runtime LLM, external API, or GPU is used.

## 📊 Actual results — 10 supplied PDFs

| Pack | Decision | Key finding |
|---|---|---|
| 01 | ✅ Approve | All required checks passed |
| 02 | ✅ Approve | All required checks passed |
| 03 | ❌ Reject | Unit price **9.05%** above maximum |
| 04 | ⚠️ Human Review | Unit price **2.31%** above maximum |
| 05 | ❌ Reject | **40%** advance exceeds policy |
| 06 | ❌ Reject | Required delay-penalty clause absent |
| 07 | ⚠️ Human Review | Quoted quantity **17.50%** below requested |
| 08 | ❌ Reject | Supplier **TIN / BIN** missing |
| 09 | ⚠️ Human Review | Ambiguous **30–90 day** payment; arithmetic mismatch |
| 10 | ❌ Reject | **60-day** delivery; VAT not separately itemized |

**Distribution:** 🟢 **2 Approve** · 🔴 **5 Reject** · 🟠 **3 Needs Human Review**. All **10/10** outcomes match a **documented manual interpretation of the supplied rules**. BIAI supplied **no official label file**; this is *rules-oracle agreement*, **not** accuracy against an independent hidden ground truth.

## 🧪 Testing and evidence

**Latest local verification:** `python -m pytest -q` → **88 passed, 14 dependency warnings, 0 failures**; `python evaluate.py` → **10 documents, unchanged 2/5/3 distribution**. Tests cover rule thresholds and precedence, PDF extraction and page evidence, modified copies of supplied samples, upload safety, recommendations, PDF report generation, and presentation. A supplied **Pack 04 copy** uploaded through the new path returned **Human Review** for the 2.31% price exception; **Pack 07** showed a quantity-specific next action. Report-generation tests covered all three decision categories. These results support the sample workflow, not arbitrary vendor documents.

## ⚠️ What does not work well

The parser targets **text-based BIAI quotation layouts** rather than arbitrary supplier templates. **OCR is not supported**; corrupt, encrypted, image-only, ambiguous, and unsupported multi-item documents are handled conservatively instead of silently approved. No actual human approvals are recorded. The app uses a deterministic rules pipeline, **not an inference-time LLM**. The sample data and generated evidence artifacts are intentionally excluded from the public repository.

## 🚀 What I would do next

For production use: add validated OCR and table extraction, more diverse labelled vendor samples, reviewer sign-off with audit identities, versioned company policies, stronger upload/security controls, and monitoring. **Before any rollout**, independently evaluate false approvals and human-review rates across real approved test data (not used in this assessment).

**Reproduce:** See [README.md](README.md) for sample-pack placement and commands. The downloadable PDF audit report includes full field values, all rule results, page evidence, and corrective recommendations.
