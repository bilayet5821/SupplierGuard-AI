from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .extraction import extract_supplier_pack
from .inputs import load_purchase_request
from .models import (
    EvaluationResult,
    ExtractedSupplierPack,
    PdfDocument,
    PurchaseRequestLine,
    RuleFinding,
)
from .pdf import extract_pdf_pages
from .validation import aggregate_decision, evaluate_rules


class WorkflowState(TypedDict, total=False):
    pdf_path: str
    purchase_request_csv: str
    document: PdfDocument
    purchase_request: dict[str, PurchaseRequestLine]
    extracted: ExtractedSupplierPack
    findings: list[RuleFinding]
    result: EvaluationResult


def load_inputs(state: WorkflowState) -> WorkflowState:
    return {
        "document": extract_pdf_pages(state["pdf_path"]),
        "purchase_request": load_purchase_request(state["purchase_request_csv"]),
    }


def extract_fields(state: WorkflowState) -> WorkflowState:
    return {"extracted": extract_supplier_pack(state["document"])}


def validate_rules(state: WorkflowState) -> WorkflowState:
    return {
        "findings": evaluate_rules(state["extracted"], state["purchase_request"])
    }


def aggregate(state: WorkflowState) -> WorkflowState:
    return {"result": aggregate_decision(state["extracted"], state["findings"])}


def build_workflow():
    """Build the fixed, acyclic workflow. There are no agents or conditional loops."""
    graph = StateGraph(WorkflowState)
    graph.add_node("load_inputs", load_inputs)
    graph.add_node("extract_fields", extract_fields)
    graph.add_node("validate_rules", validate_rules)
    graph.add_node("aggregate_decision", aggregate)
    graph.add_edge(START, "load_inputs")
    graph.add_edge("load_inputs", "extract_fields")
    graph.add_edge("extract_fields", "validate_rules")
    graph.add_edge("validate_rules", "aggregate_decision")
    graph.add_edge("aggregate_decision", END)
    return graph.compile()


WORKFLOW = build_workflow()


def run_workflow(
    pdf_path: str | Path,
    purchase_request_csv: str | Path,
) -> EvaluationResult:
    final_state = WORKFLOW.invoke(
        {
            "pdf_path": str(Path(pdf_path).resolve()),
            "purchase_request_csv": str(Path(purchase_request_csv).resolve()),
        }
    )
    return final_state["result"]
