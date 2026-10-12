"""Atomic daily LLM-call quota backed by Firestore."""

import os
from datetime import datetime, timezone

from google.cloud import firestore


PROJECT_ID = "maintenance-investigator"
COLLECTION = "llm_daily_usage"


class DailyQuotaExceeded(Exception):
    """Raised when the configured daily LLM quota is exhausted."""


def reserve_llm_call() -> dict:
    limit = int(os.environ.get("DAILY_LLM_CALL_LIMIT", "100"))
    if limit < 1:
        raise ValueError("DAILY_LLM_CALL_LIMIT must be at least 1")

    day = datetime.now(timezone.utc).date().isoformat()
    db = firestore.Client(project=PROJECT_ID)
    ref = db.collection(COLLECTION).document(day)
    transaction = db.transaction()

    @firestore.transactional
    def reserve(tx):
        snapshot = ref.get(transaction=tx)
        used = int((snapshot.to_dict() or {}).get("count", 0))
        if used >= limit:
            return {"allowed": False, "used": used, "limit": limit}

        tx.set(
            ref,
            {
                "date_utc": day,
                "count": used + 1,
                "limit": limit,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            merge=True,
        )
        return {"allowed": True, "used": used + 1, "limit": limit}

    result = reserve(transaction)
    if not result["allowed"]:
        raise DailyQuotaExceeded(
            f"Daily LLM-call limit reached ({result['used']}/{result['limit']} UTC)."
        )
    return result
