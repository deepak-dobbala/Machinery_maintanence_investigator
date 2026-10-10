"""Day 4.6: manual evidence plus work-order history."""

import importlib.util
from pathlib import Path

from google.adk.workflow import Workflow, FunctionNode, Edge, START


BASE = Path(__file__).resolve().parents[2]


def load_module(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module: {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tools_module = load_module(
    "investigator_tools_day46",
    BASE / "agents" / "investigator" / "tools.py",
)
history_module = load_module(
    "work_order_history_day46",
    BASE / "rag" / "work_order_history.py",
)


def retrieve_manual_evidence():
    result = tools_module.lookup_alarm(
        query="Alarm 113 Shuttle In Fault",
        alarm_code="113",
    )

    evidence = result.get("evidence", [])

    return {
        "status": (
            "RETRIEVAL_COMPLETE"
            if result.get("found")
            else "NO_EVIDENCE"
        ),
        "alarm_code": "113",
        "found": result.get("found", False),
        "evidence_count": len(evidence),
        "evidence": [
            {
                "evidence_id": item.get("evidence_id"),
                "citation": item.get("citation"),
                "chunk_type": item.get("chunk_type"),
                "text": item.get("text"),
            }
            for item in evidence[:3]
        ],
        "source_type": "service_manual",
    }


def retrieve_work_order_history():
    result = history_module.get_work_order_history(
        alarm_code="113",
        limit=10,
    )

    return {
        "status": "HISTORY_RETRIEVED",
        "alarm_code": result["alarm_code"],
        "total_matching_records": result["total_matching_records"],
        "status_counts": result["status_counts"],
        "source_counts": result["source_counts"],
        "records": result["records"],
        "source_type": "historical_work_orders",
        "interpretation": result["interpretation"],
    }


def combine_results():
    manual = retrieve_manual_evidence()
    history = retrieve_work_order_history()

    output = {
        "status": "COMBINED_RETRIEVAL_COMPLETE",
        "alarm_code": "113",
        "manual_evidence": manual,
        "work_order_history": history,
        "safety_note": (
            "Manual evidence and work-order history are separate sources. "
            "All current work orders are synthetic test data and must not "
            "be treated as validated causes or repair probabilities."
        ),
    }

    print("DAY46_STATUS:", output["status"])
    print(
        "DAY46_MANUAL_EVIDENCE_COUNT:",
        manual["evidence_count"],
    )
    print(
        "DAY46_WORK_ORDER_COUNT:",
        history["total_matching_records"],
    )
    print("DAY46_WORK_ORDER_SOURCES:", history["source_counts"])

    return output


combined_node = FunctionNode(
    name="combine_manual_and_history",
    func=combine_results,
    parameter_binding="state",
)

root_agent = Workflow(
    name="day46_history_workflow",
    description=(
        "Retrieve service-manual evidence and work-order history "
        "as separate, traceable sources for Alarm 113"
    ),
    edges=[
        Edge(from_node=START, to_node=combined_node),
    ],
)
