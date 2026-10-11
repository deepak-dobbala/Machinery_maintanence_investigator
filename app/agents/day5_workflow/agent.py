"""Day 5 workflow: route new cases, check results, and close-out."""

import json
import sys
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[2]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from google.adk.events.event import Event
from google.adk.workflow import Workflow, FunctionNode, Edge, START

from agents.investigator.tools import lookup_alarm
from rag.diagnostic_session import DiagnosticSession


def normalize_input(node_input: Any) -> dict[str, Any]:
    """Normalize an ADK Content message or dictionary into a payload."""
    if isinstance(node_input, dict):
        return node_input

    parts = getattr(node_input, "parts", None)
    if parts is not None:
        raw_text = "".join(getattr(part, "text", "") or "" for part in parts)
    elif isinstance(node_input, str):
        raw_text = node_input
    else:
        raw_text = ""

    try:
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return {}

    return parsed if isinstance(parsed, dict) else {}


def route_phase(ctx, node_input: Any):
    node_input = normalize_input(node_input)
    """Choose the workflow path from the caller's requested phase."""
    phase = str(node_input.get("phase", "new_case")).strip().lower()

    aliases = {
        "new": "new_case",
        "new_case": "new_case",
        "check": "check_result",
        "check_result": "check_result",
        "close": "close_out",
        "close_out": "close_out",
        "explain": "explain",
    }
    route = aliases.get(phase)

    if route is None:
        return Event(
            output={
                "status": "invalid_phase",
                "accepted_phases": ["new_case", "check_result", "close_out", "explain"],
                "received_phase": phase,
            },
            route="invalid_phase",
        )

    return Event(output=node_input, route=route)


def new_case(ctx, node_input: dict[str, Any]):
    """Retrieve manual evidence and initialize a diagnostic session."""
    alarm_number = str(node_input.get("alarm_number", "")).strip()
    query = str(node_input.get("query", "")).strip()

    if not alarm_number and not query:
        return Event(
            output={
                "status": "input_required",
                "required": "Provide alarm_number or query.",
            },
            route="case_error",
        )

    retrieved = lookup_alarm(query=query, alarm_code=alarm_number)

    evidence = retrieved.get("evidence", [])
    if not evidence:
        return Event(
            output={
                "status": "insufficient_evidence",
                "message": "The available manual evidence does not establish that.",
                "retrieval": retrieved,
            },
            route="case_error",
        )

    session = DiagnosticSession(
        alarm_number=alarm_number,
        query=query or f"Alarm {alarm_number}",
        evidence=evidence,
    )
    snapshot = session.state()

    # Keep the data needed to resume this investigation in workflow state.
    ctx.state["diagnostic_case"] = {
        "alarm_number": alarm_number,
        "query": query or f"Alarm {alarm_number}",
        "evidence": evidence,
        "observations": [],
        "session_state": snapshot,
    }

    return Event(
        output={
            "status": "case_initialized",
            "retrieval": retrieved,
            "diagnosis": snapshot,
        },
        route="ask_check" if snapshot.get("next_check", {}).get("check") else "close_out",
    )


def check_result(ctx, node_input: dict[str, Any]):
    """Apply a technician observation to the existing diagnostic case."""
    case = ctx.state.get("diagnostic_case")
    if not case:
        return {
            "status": "no_active_case",
            "message": "Start a new case before submitting a check result.",
        }

    observation = str(node_input.get("observation", "")).strip()
    if not observation:
        return {
            "status": "observation_required",
            "message": "Provide the technician's observation or check result.",
        }

    session = DiagnosticSession.restore(
        saved_state=case["session_state"],
        evidence=case["evidence"],
    )

    diagnosis = session.record_observation(observation)
    case["observations"].append(observation)
    case["session_state"] = diagnosis
    ctx.state["diagnostic_case"] = case

    return Event(
        output={
            "status": "observation_recorded",
            "diagnosis": diagnosis,
        },
        route="close_out" if diagnosis.get("confirmed_cause") else (
            "ask_check" if diagnosis.get("next_check", {}).get("check") else "more_evidence"
        ),
    )


def ask_check(ctx, node_input):
    """Present the supported check and wait for the technician's result."""
    case = ctx.state.get("diagnostic_case", {})
    diagnosis = case.get("session_state", {})
    next_check = diagnosis.get("next_check", {})
    safety = next_check.get("safety", {})

    return {
        "status": "waiting_for_check_result",
        "check": next_check.get("check"),
        "reason": next_check.get("reason"),
        "evidence": next_check.get("evidence", []),
        "safety": {
            "required": safety.get("required", False),
            "status": safety.get("status", "unknown"),
            "hazards": safety.get("hazards", []),
            "message": safety.get("message"),
        },
        "effort": None,
        "effort_note": "No effort estimate is supplied by the diagnostic engine.",
        "awaiting": "observation",
        "message": (
            "Do not perform the check until the applicable safety "
            "conditions are established. Submit the technician's "
            "observation to continue the investigation."
        ),
    }


def close_out(ctx, node_input):
    """Close only confirmed cases; otherwise return a reason and escalation tier."""
    case = ctx.state.get("diagnostic_case", {})
    diagnosis = case.get("session_state", {})
    confirmed_cause = diagnosis.get("confirmed_cause")

    if confirmed_cause:
        return {
            "status": "confirmed",
            "confirmed_cause": confirmed_cause,
            "stop_tier": "confirmed",
            "stop_reason": "A cause was explicitly confirmed by the diagnostic session.",
            "diagnosis": diagnosis,
        }

    next_check = diagnosis.get("next_check", {})
    safety = next_check.get("safety", {})
    if safety.get("required") and safety.get("status") != "clear":
        stop_tier = "high_stakes_escalation"
        stop_reason = (
            "A safety gate remains unresolved. Do not proceed until the "
            "applicable machine safety conditions are established."
        )
    elif not diagnosis:
        stop_tier = "insufficient_information"
        stop_reason = "No active diagnostic case is available to close out."
    else:
        stop_tier = "unresolved"
        stop_reason = (
            next_check.get("reason")
            or "The available evidence does not support a confirmed cause."
        )

    return {
        "status": "stopped_needs_more_evidence",
        "stop_tier": stop_tier,
        "stop_reason": stop_reason,
        "diagnosis": diagnosis or None,
    }


def explain(ctx, node_input):
    """Explain the current assessment using saved evidence and observations."""
    case = ctx.state.get("diagnostic_case", {})
    diagnosis = case.get("session_state", {})
    candidates = diagnosis.get("candidate_causes", [])
    observations = diagnosis.get("observations", [])
    next_check = diagnosis.get("next_check", {})

    explanations = []
    for candidate in candidates:
        supporting = [
            item for item in candidate.get("evidence", [])
            if item.get("citation") and item.get("text", "").strip()
        ]
        explanations.append({
            "cause": candidate.get("cause", "Unspecified candidate"),
            "status": candidate.get("status", "possible"),
            "confidence_band": candidate.get("confidence_band", "unknown"),
            "confidence_note": "Engine-provided band; not a calibrated probability.",
            "evidence_for": supporting,
            "evidence_against": [],
            "evidence_against_note": (
                "No candidate-specific contrary evidence has been established."
            ),
            "what_would_change_assessment": (
                next_check.get("check")
                or "Obtain additional relevant evidence."
            ),
        })

    return {
        "status": "explanation_ready",
        "confirmed_cause": diagnosis.get("confirmed_cause"),
        "candidates": explanations,
        "observations": observations,
        "next_check": next_check.get("check"),
        "message": (
            "This explanation summarizes recorded evidence. A cause is confirmed "
            "only when the diagnostic session explicitly confirms it."
        ),
    }


def invalid_phase(ctx, node_input):
    return node_input


def case_error(ctx, node_input):
    return node_input


def more_evidence(ctx, node_input):
    """Stop without claiming a diagnosis when no supported check remains."""
    case = ctx.state.get("diagnostic_case", {})
    diagnosis = case.get("session_state", {})
    next_check = diagnosis.get("next_check", {})
    safety = next_check.get("safety", {})

    if safety.get("required") and safety.get("status") != "clear":
        stop_tier = "high_stakes_escalation"
        stop_reason = (
            "A safety gate remains unresolved. Escalate to an appropriately "
            "qualified technician before taking further action."
        )
    else:
        stop_tier = "insufficient_evidence"
        stop_reason = (
            next_check.get("reason")
            or "Additional manual evidence is required; no supported next check remains."
        )

    return {
        "status": "stopped_needs_more_evidence",
        "stop_tier": stop_tier,
        "stop_reason": stop_reason,
        "diagnosis": diagnosis or None,
    }


phase_router = FunctionNode(
    name="route_phase",
    func=route_phase,
    parameter_binding="state",
)

new_case_node = FunctionNode(
    name="new_case",
    func=new_case,
    parameter_binding="state",
)

check_result_node = FunctionNode(
    name="check_result",
    func=check_result,
    parameter_binding="state",
)

ask_check_node = FunctionNode(
    name="ask_check",
    func=ask_check,
    parameter_binding="state",
)

close_out_node = FunctionNode(
    name="close_out",
    func=close_out,
    parameter_binding="state",
)

case_error_node = FunctionNode(
    name="case_error", func=case_error, parameter_binding="state"
)
invalid_phase_node = FunctionNode(
    name="invalid_phase",
    func=invalid_phase,
    parameter_binding="state",
)

more_evidence_node = FunctionNode(
    name="more_evidence",
    func=more_evidence,
    parameter_binding="state",
)

explain_node = FunctionNode(
    name="explain",
    func=explain,
    parameter_binding="state",
)

root_agent = Workflow(
    name="maintenance_investigator_day5",
    description="Maintenance investigation with explicit phase routing.",
    edges=[
        Edge(from_node=START, to_node=phase_router),
        Edge(from_node=phase_router, to_node=new_case_node, route="new_case"),
        Edge(from_node=phase_router, to_node=check_result_node, route="check_result"),
        Edge(from_node=phase_router, to_node=close_out_node, route="close_out"),
        Edge(from_node=phase_router, to_node=explain_node, route="explain"),
        Edge(from_node=phase_router, to_node=invalid_phase_node, route="invalid_phase"),
        Edge(from_node=new_case_node, to_node=ask_check_node, route="ask_check"),
        Edge(from_node=new_case_node, to_node=close_out_node, route="close_out"),
        Edge(from_node=new_case_node, to_node=case_error_node, route="case_error"),
        Edge(from_node=check_result_node, to_node=ask_check_node, route="ask_check"),
        Edge(from_node=check_result_node, to_node=close_out_node, route="close_out"),
        Edge(from_node=check_result_node, to_node=more_evidence_node, route="more_evidence"),
    ],
)
