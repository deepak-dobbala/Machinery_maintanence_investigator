"""Conservative ranking hints from validated work-order history."""

from typing import Any, Dict, List


def apply_history_ranking(
    candidates: List[Dict[str, Any]],
    records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Use confirmed, non-synthetic history only as a ranking tie-breaker.

    This does not establish causation or calculate diagnostic probabilities.
    """
    confirmed_diagnoses = {
        " ".join(str(row.get("diagnosis", "")).casefold().split())
        for row in records
        if row.get("confirmation_status") == "confirmed"
        and row.get("resolution_status") == "confirmed"
        and row.get("synthetic") is False
        and str(row.get("diagnosis", "")).strip()
    }

    result = [dict(candidate) for candidate in candidates]
    for candidate in result:
        diagnosis = " ".join(
            str(candidate.get("cause", "")).casefold().split()
        )
        candidate["history_match"] = bool(
            diagnosis and diagnosis in confirmed_diagnoses
        )
        candidate["history_note"] = (
            "Matches a confirmed, non-synthetic historical diagnosis; "
            "historical context only, not proof for this case."
            if candidate["history_match"]
            else "No eligible confirmed historical match."
        )

    # Stable tie-breaker only: manual-supported candidates remain ahead of
    # unsourced candidates regardless of history.
    result.sort(
        key=lambda item: (
            bool(item.get("sourced")),
            bool(item.get("history_match")),
        ),
        reverse=True,
    )
    return result
