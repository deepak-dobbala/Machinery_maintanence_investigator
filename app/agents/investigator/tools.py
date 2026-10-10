from typing import Any, Dict
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
from rag.manual_retriever import search_manual, format_evidence


def lookup_alarm(
    query: str,
    alarm_code: str = "",
) -> Dict[str, Any]:
    """
    Search the Haas VF Series service manuals for alarm definitions
    and troubleshooting evidence. Returns source citations and passages.
    """

    query = str(query or "").strip()
    alarm_code = str(alarm_code or "").strip()

    if not query and not alarm_code:
        return {
            "found": False,
            "message": "Provide an alarm number or troubleshooting question.",
            "evidence": [],
        }

    if not query:
        query = f"Alarm {alarm_code}"

    result = search_manual(
        query=query,
        alarm_number=alarm_code or None,
        machine_family="Haas VF Series",
    )

    evidence = format_evidence(result, max_results=8)

    if not evidence:
        return {
            "found": False,
            "alarm_code": alarm_code or None,
            "query": query,
            "message": (
                "The available manual evidence does not establish that."
            ),
            "evidence": [],
        }

    return {
        "found": True,
        "alarm_code": alarm_code or None,
        "query": query,
        "exact_alarm_count": result.get("exact_alarm_count", 0),
        "semantic_result_count": result.get("semantic_result_count", 0),
        "evidence": evidence,
        "important_note": (
            "Retrieved passages are candidate evidence. "
            "Use only claims directly supported by the passages and citations."
        ),
    }

def lookup_extracted_alarm(
    machine_model: str = "",
    control_generation: str = "",
    alarm_code: str = "",
    alarm_text: str = "",
    machine_state: str = "",
    confidence: float | None = None,
    missing_fields: list[str] = None,
    technician_confirmed: bool = False,
) -> Dict[str, Any]:
    """Validate extracted image fields before handing an alarm to manual lookup."""

    missing_fields = missing_fields or []
    alarm_code = str(alarm_code or "").strip()
    alarm_text = str(alarm_text or "").strip()
    machine_model = str(machine_model or "").strip()

    if confidence is not None and confidence < 0.85:
        return {
            "ready": False,
            "status": "confirmation_required",
            "message": "Image extraction confidence is low. Ask the technician to confirm the displayed fields.",
        }

    if missing_fields or not alarm_code:
        return {
            "ready": False,
            "status": "missing_fields",
            "message": "Confirm the alarm code and any missing or uncertain fields before manual lookup.",
            "missing_fields": missing_fields,
        }

    if not technician_confirmed:
        return {
            "ready": False,
            "status": "confirmation_required",
            "message": (
                f"Please confirm: {machine_model or 'machine model unknown'}, "
                f"Alarm {alarm_code}: {alarm_text or 'alarm text unavailable'}. "
                "Has this been read correctly from the machine screen?"
            ),
        }

    query = f"Alarm {alarm_code}: {alarm_text}. Machine state: {machine_state}."
    result = lookup_alarm(query=query, alarm_code=alarm_code)
    result["machine_model"] = machine_model or None
    result["control_generation"] = control_generation or None
    result["technician_confirmed"] = True
    return result