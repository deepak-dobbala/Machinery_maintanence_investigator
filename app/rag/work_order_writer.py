"""Persist explicitly confirmed diagnostic outcomes to Firestore."""

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from google.cloud import firestore


PROJECT_ID = "maintenance-investigator"
COLLECTION = "work_orders"


def record_confirmed_work_order(
    *,
    alarm_code: str,
    machine_model: str,
    symptom: str,
    diagnosis: str,
    action_taken: str,
    confirmation_status: str,
) -> Dict[str, Any]:
    """Create a work-order record only after explicit cause confirmation."""

    if confirmation_status != "confirmed":
        raise ValueError(
            "Refusing to persist a work order without explicit confirmation."
        )

    required = {
        "alarm_code": alarm_code,
        "machine_model": machine_model,
        "symptom": symptom,
        "diagnosis": diagnosis,
        "action_taken": action_taken,
    }
    missing = [key for key, value in required.items() if not str(value).strip()]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    work_order_id = f"confirmed-{uuid4().hex}"
    record = {
        "work_order_id": work_order_id,
        "alarm_code": str(alarm_code),
        "machine_model": machine_model.strip(),
        "symptom": symptom.strip(),
        "diagnosis": diagnosis.strip(),
        "action_taken": action_taken.strip(),
        "resolution_status": "confirmed",
        "confirmation_status": "confirmed",
        "source": "confirmed_diagnostic_session",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "synthetic": False,
    }

    db = firestore.Client(project=PROJECT_ID)
    db.collection(COLLECTION).document(work_order_id).create(record)

    return record
