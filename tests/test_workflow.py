from supplierguard.models import Decision
from supplierguard.workflow import WORKFLOW, run_workflow


def test_workflow_is_fixed_and_sequential():
    graph = WORKFLOW.get_graph()
    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert edges == {
        ("__start__", "load_inputs"),
        ("load_inputs", "extract_fields"),
        ("extract_fields", "validate_rules"),
        ("validate_rules", "aggregate_decision"),
        ("aggregate_decision", "__end__"),
    }


def test_workflow_runs_end_to_end(task_data):
    result = run_workflow(
        task_data / "supplier-pack-01.pdf",
        task_data / "purchase-request.csv",
    )
    assert result.decision == Decision.APPROVE
    assert result.extracted.supplier_name == "Padma Textile Mills Ltd"
