from google.adk.workflow import Workflow, FunctionNode, Edge, START
import importlib.util
from pathlib import Path

_tools_path = Path(__file__).resolve().parents[1] / "investigator" / "tools.py"
_tools_spec = importlib.util.spec_from_file_location(
    "investigator_tools_day44", _tools_path
)
_tools_module = importlib.util.module_from_spec(_tools_spec)
_tools_spec.loader.exec_module(_tools_module)
lookup_alarm = _tools_module.lookup_alarm


def retrieve_manual_evidence():
    print("DAY44_RETRIEVAL_STARTED")

    result = lookup_alarm(
        query="Alarm 113 Shuttle In Fault",
        alarm_code="113",
    )

    evidence = result.get("evidence", [])

    output = {
        "status": "RETRIEVAL_COMPLETE" if result.get("found") else "NO_EVIDENCE",
        "alarm_code": result.get("alarm_code", "113"),
        "found": result.get("found", False),
        "exact_alarm_count": result.get("exact_alarm_count", 0),
        "semantic_result_count": result.get("semantic_result_count", 0),
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
    }

    print("DAY44_RETRIEVAL_RESULT:", output["status"])
    print("DAY44_EVIDENCE_COUNT:", output["evidence_count"])

    return output


retrieval_node = FunctionNode(
    name="retrieve_manual_evidence",
    func=retrieve_manual_evidence,
    parameter_binding="state",
)

root_agent = Workflow(
    name="day44_retrieval_node",
    description="Day 4.4 workflow node using the existing manual retriever",
    edges=[
        Edge(from_node=START, to_node=retrieval_node),
    ],
)
