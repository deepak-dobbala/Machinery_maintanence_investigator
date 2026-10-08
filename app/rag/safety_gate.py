#!/usr/bin/env python3

"""
Safety gate for the Maintenance Investigator.

The gate does not decide whether a repair is technically correct.
It determines whether a proposed diagnostic action requires a
safety condition before being presented as an action.
"""


from typing import Any, Dict


def evaluate_safety(
    action: str,
    evidence: Dict[str, Any] | None = None,
) -> Dict[str, Any]:

    action_text = action.lower()

    hazards = []

    if any(
        term in action_text
        for term in [
            "voltage",
            "electrical",
            "power",
            "circuit",
            "drive",
            "motor",
            "amplifier",
        ]
    ):
        hazards.append(
            "electrical energy"
        )

    if any(
        term in action_text
        for term in [
            "spindle",
            "rotation",
            "tool changer",
            "shuttle",
            "carousel",
            "mechanical",
        ]
    ):
        hazards.append(
            "unexpected machine movement"
        )

    if any(
        term in action_text
        for term in [
            "air",
            "pressure",
            "pneumatic",
        ]
    ):
        hazards.append(
            "stored pneumatic energy"
        )

    if hazards:

        return {
            "required": True,
            "status": "gate_required",
            "hazards": hazards,
            "message": (
                "Do not perform the diagnostic action "
                "until the applicable machine safety "
                "conditions have been established."
            ),
            "evidence": (
                evidence or {}
            ),
        }

    return {
        "required": False,
        "status": "clear",
        "hazards": [],
        "message": (
            "No specific safety gate was triggered "
            "by the proposed diagnostic action."
        ),
        "evidence": (
            evidence or {}
        ),
    }