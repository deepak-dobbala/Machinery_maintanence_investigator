"""Firestore cache for manual-grounded diagnostic proposals."""

import hashlib
import json
import os
from typing import Any, Dict, Optional

from google.cloud import firestore


PROJECT_ID = os.environ.get(
    "GOOGLE_CLOUD_PROJECT", "maintenance-investigator"
)
COLLECTION = "catalog"
SCHEMA_VERSION = 1


def proposal_cache_key(
    alarm_code: str,
    machine_model: str,
    manual_revision: str,
    proposal_model: str,
) -> str:
    """Build a deterministic key for this exact proposal configuration."""
    identity = {
        "alarm_code": str(alarm_code).strip(),
        "machine_model": str(machine_model).strip(),
        "manual_revision": str(manual_revision).strip(),
        "proposal_model": str(proposal_model).strip(),
        "schema_version": SCHEMA_VERSION,
    }
    encoded = json.dumps(
        identity, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def get_cached_proposal(
    alarm_code: str,
    machine_model: str,
    manual_revision: str,
    proposal_model: str,
    db=None,
) -> Optional[Dict[str, Any]]:
    """Return a cached proposal, or None on a cache miss."""
    key = proposal_cache_key(
        alarm_code, machine_model, manual_revision, proposal_model
    )
    client = db or firestore.Client(project=PROJECT_ID)
    snapshot = client.collection(COLLECTION).document(key).get()

    if not snapshot.exists:
        return None

    data = snapshot.to_dict() or {}
    return data.get("proposal")


def cache_proposal(
    alarm_code: str,
    machine_model: str,
    manual_revision: str,
    proposal_model: str,
    proposal: Dict[str, Any],
    db=None,
) -> str:
    """Store a proposal under its alarm/model/revision cache key."""
    key = proposal_cache_key(
        alarm_code, machine_model, manual_revision, proposal_model
    )
    client = db or firestore.Client(project=PROJECT_ID)
    client.collection(COLLECTION).document(key).set({
        "alarm_code": str(alarm_code).strip(),
        "machine_model": str(machine_model).strip(),
        "manual_revision": str(manual_revision).strip(),
        "proposal_model": str(proposal_model).strip(),
        "schema_version": SCHEMA_VERSION,
        "proposal": proposal,
    })
    return key


def diagnose_cached(
    alarm_code: str,
    machine_model: str,
    manual_revision: str,
    proposal_model: str,
    evidence,
    db=None,
):
    """Return a cached diagnostic proposal, generating it on a cache miss."""
    from rag.diagnostic_engine import diagnose

    cached = get_cached_proposal(
        alarm_code, machine_model, manual_revision, proposal_model, db=db
    )
    if cached is not None:
        return cached

    proposal = diagnose(alarm_code, evidence)
    cache_proposal(
        alarm_code,
        machine_model,
        manual_revision,
        proposal_model,
        proposal,
        db=db,
    )
    return proposal
