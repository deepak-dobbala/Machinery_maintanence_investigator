from typing import Any, Dict

from rag.manual_retriever import (
    search_manual,
    format_evidence,
)


def lookup_alarm(
    alarm_code: str,
    query: str = "",
) -> Dict[str, Any]:
    """
    Retrieve authoritative alarm and troubleshooting evidence
    from the Firestore manual corpus.

    Returns exact alarm definitions plus ranked troubleshooting
    evidence with manual citations.
    """

    alarm_code = str(alarm_code).strip()

    if not query:
        query = f"Alarm {alarm_code}"

    result = search_manual(
        query=query,
        alarm_number=alarm_code,
    )

    evidence = format_evidence(
        result,
        max_results=8,
    )

    if not evidence:
        return {
            "found": False,
            "alarm_code": alarm_code,
            "message": (
                "The alarm was not found in the "
                "manual evidence corpus."
            ),
        }

    return {
        "found": True,
        "alarm_code": alarm_code,
        "query": query,
        "exact_alarm_count": result[
            "exact_alarm_count"
        ],
        "semantic_result_count": result[
            "semantic_result_count"
        ],
        "evidence": evidence,
    }