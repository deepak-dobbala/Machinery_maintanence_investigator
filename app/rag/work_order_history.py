"""Read-only work-order history lookup.

Synthetic work orders are returned as test context, not validated
diagnostic statistics or repair recommendations.
"""

from collections import Counter
from typing import Any, Dict, Optional

from google.cloud import firestore


PROJECT_ID = "maintenance-investigator"
COLLECTION = "work_orders"


def get_work_order_history(
    alarm_code: str,
    machine_model: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Retrieve work orders matching an alarm and optional machine model."""

    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")

    db = firestore.Client(project=PROJECT_ID)

    query = db.collection(COLLECTION).where(
        "alarm_code", "==", str(alarm_code)
    )

    if machine_model:
        query = query.where(
            "machine_model", "==", machine_model
        )

    rows = []
    for snapshot in query.limit(100).stream():
        row = snapshot.to_dict() or {}
        rows.append({
            "work_order_id": row.get("work_order_id", snapshot.id),
            "alarm_code": str(row.get("alarm_code", "")),
            "machine_model": row.get("machine_model"),
            "symptom": row.get("symptom"),
            "diagnosis": row.get("diagnosis"),
            "action_taken": row.get("action_taken"),
            "resolution_status": row.get("resolution_status"),
            "created_at": row.get("created_at"),
            "source": row.get("source", "unknown"),
        })

    rows.sort(
        key=lambda row: str(row.get("created_at") or ""),
        reverse=True,
    )

    status_counts = Counter(
        row["resolution_status"] or "unknown"
        for row in rows
    )
    source_counts = Counter(row["source"] for row in rows)

    return {
        "alarm_code": str(alarm_code),
        "machine_model": machine_model,
        "total_matching_records": len(rows),
        "status_counts": dict(status_counts),
        "source_counts": dict(source_counts),
        "records": rows[:limit],
        "interpretation": (
            "Historical context only. Synthetic or unvalidated records "
            "must not be treated as confirmed root causes, repair success "
            "rates, or probabilities."
        ),
    }
