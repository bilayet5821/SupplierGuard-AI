from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from supplierguard.models import CheckStatus  # noqa: E402
from supplierguard.inputs import load_purchase_request  # noqa: E402
from supplierguard.presentation import issue_details, recommendations_for_result  # noqa: E402
from supplierguard.workflow import run_workflow  # noqa: E402


DEFAULT_DATA = (
    ROOT
    / "BIAI-AI-Engineer-Round2-Pack"
    / "sample-data"
    / "engineer"
    / "task1-procurement"
)


def evaluate_all(data_dir: Path) -> list[dict]:
    pr_csv = data_dir / "purchase-request.csv"
    purchase_request = load_purchase_request(pr_csv)
    pdfs = sorted(data_dir.glob("supplier-pack-*.pdf"))
    if len(pdfs) != 10:
        raise ValueError(f"Expected exactly 10 supplier PDFs; found {len(pdfs)} in {data_dir}")

    records: list[dict] = []
    for pdf in pdfs:
        result = run_workflow(pdf, pr_csv)
        decisive_status = {
            "Reject": CheckStatus.REJECT,
            "Needs Human Review": CheckStatus.HUMAN_REVIEW,
            "Approve": CheckStatus.PASS,
        }[result.decision.value]
        decisive = [
            finding.model_dump(mode="json")
            for finding in result.findings
            if finding.status == decisive_status
        ]
        records.append(
            {
                "source_file": result.source_file,
                "decision": result.decision.value,
                "decision_reason": result.decision_reason,
                "recommendations": recommendations_for_result(result, purchase_request),
                "issue_details": [
                    detail.as_dict()
                    for detail in issue_details(result, purchase_request)
                ],
                "decisive_findings": decisive,
                "result": result.model_dump(mode="json"),
            }
        )
    return records


def write_outputs(records: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = Counter(record["decision"] for record in records)
    payload = {
        "documents_evaluated": len(records),
        "decision_counts": dict(sorted(counts.items())),
        "records": records,
    }
    (output_dir / "evaluation-results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    with (output_dir / "evaluation-summary.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["source_file", "decision", "decision_reason"],
        )
        writer.writeheader()
        writer.writerows(
            {
                "source_file": record["source_file"],
                "decision": record["decision"],
                "decision_reason": record["decision_reason"],
            }
            for record in records
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate all supplied Task 1 PDFs.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts")
    args = parser.parse_args()
    records = evaluate_all(args.data_dir.resolve())
    write_outputs(records, args.output_dir.resolve())
    counts = Counter(record["decision"] for record in records)
    print(f"Evaluated {len(records)} documents")
    for decision in ("Approve", "Reject", "Needs Human Review"):
        print(f"{decision}: {counts[decision]}")
    print(f"Wrote: {args.output_dir.resolve() / 'evaluation-results.json'}")
    print(f"Wrote: {args.output_dir.resolve() / 'evaluation-summary.csv'}")


if __name__ == "__main__":
    main()
