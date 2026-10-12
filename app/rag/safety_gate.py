#!/usr/bin/env python3
"""
Fail-closed safety gate for the Maintenance Investigator.

A triggered safety gate is not authorization to perform work.
A verified, machine-specific lockout/tagout (LOTO) procedure must
be available before hazardous work can be cleared.
"""

import json
from pathlib import Path
from typing import Any, Dict


DEMO_FIXTURE_PATH = Path(__file__).with_name("synthetic_loto_demo.json")


def load_synthetic_demo_fixture() -> Dict[str, Any]:
    """Load illustrative UI data; never treat it as an approved procedure."""
    with DEMO_FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
        fixture = json.load(fixture_file)

    if (
        fixture.get("fixture_type") != "synthetic_demo"
        or fixture.get("source_status") != "not_verified"
        or fixture.get("operational_use") is not False
    ):
        raise ValueError("Synthetic safety fixture is missing required safety labels.")

    return fixture


# These terms indicate potential exposure to hazardous energy.
ENERGY_TERMS = {
    "electrical energy": (
        "voltage", "electrical", "power", "circuit", "drive",
        "motor", "amplifier", "electrical cabinet", "breaker",
        "wiring", "disconnect", "energized",
    ),
    "unexpected machine movement": (
        "spindle", "rotation", "tool changer", "shuttle",
        "carousel", "mechanical", "axis", "servo", "moving",
        "machine motion",
    ),
    "stored pneumatic or hydraulic energy": (
        "air", "pressure", "pneumatic", "hydraulic", "stored energy",
    ),
}

# Maintenance actions that can expose a person to hazardous energy,
# even when the action text does not name a particular energy source.
HIGH_RISK_TERMS = (
    "service", "servicing", "repair", "replace", "remove",
    "adjust", "clear a jam", "clear jam", "unjam", "clean inside",
    "enter enclosure", "enter the enclosure", "open cabinet",
    "open the cabinet", "isolate", "isolation", "lockout",
    "lock-out", "tagout", "tag-out",
)


def evaluate_safety(
    action: str,
    evidence: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Evaluate an action; never infer that missing safety evidence is clearance."""

    action_text = (action or "").casefold()
    evidence_data = evidence or {}
    hazards = []

    for hazard, terms in ENERGY_TERMS.items():
        if any(term in action_text for term in terms):
            hazards.append(hazard)

    high_risk = any(term in action_text for term in HIGH_RISK_TERMS)

    # A high-risk maintenance action must not pass simply because its
    # energy source was omitted from the wording.
    if high_risk and not hazards:
        hazards.append("hazardous maintenance activity")

    if hazards:
        return {
            "required": True,
            "status": "gate_required",
            "hazards": hazards,
            "blocked": True,
            "checklist_required": True,
            "checklist_status": "source_missing",
            "checklist": [],
            "demo_checklist": load_synthetic_demo_fixture(),
            "message": (
                "BLOCKED: Do not perform this action. The approved, "
                "machine-specific lockout/tagout and energy-isolation "
                "checklist has not been verified in the ingested sources. "
                "Obtain and verify the applicable site-approved procedure "
                "before considering this action. An emergency stop alone "
                "is not evidence of energy isolation."
            ),
            "evidence": evidence_data,
        }

    return {
        "required": False,
        "status": "clear",
        "hazards": [],
        "blocked": False,
        "checklist_required": False,
        "checklist_status": "not_triggered",
        "checklist": [],
        "message": (
            "No specific safety trigger was detected in the action text. "
            "This is not a general safety clearance; review the full task "
            "and applicable site procedures before work."
        ),
        "evidence": evidence_data,
    }
