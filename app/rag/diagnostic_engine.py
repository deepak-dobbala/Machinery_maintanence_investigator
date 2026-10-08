#!/usr/bin/env python3

"""
Evidence-grounded diagnostic engine.

The engine converts retrieved manual evidence into:
- candidate causes
- diagnostic checks
- evidence supporting each item
- possible status
- abstention when evidence is insufficient

It does not invent maintenance procedures.
"""

from typing import Any, Dict, List


def _contains_any(text: str, terms: List[str]) -> bool:
    text = text.lower()
    return any(
        term.lower() in text
        for term in terms
    )


def _make_evidence_ref(
    evidence: Dict[str, Any],
) -> Dict[str, Any]:

    return {
        "evidence_id": evidence["evidence_id"],
        "citation": evidence["citation"],
        "chunk_type": evidence["chunk_type"],
        "text": evidence["text"],
    }


def _add_candidate(
    candidates: List[Dict[str, Any]],
    cause: str,
    check: str,
    evidence: Dict[str, Any],
):
    candidates.append(
        {
            "cause": cause,
            "status": "possible",
            "next_check": check,
            "evidence": [
                _make_evidence_ref(evidence)
            ],
        }
    )


def build_candidate_causes(
    alarm_number: str,
    evidence: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    alarm = str(alarm_number)

    candidates = []

    for e in evidence:

        text = e.get(
            "text",
            "",
        )

        # ---------------------------------------------------------
        # Alarm 122 - Regen Overheat
        # ---------------------------------------------------------

        if alarm == "122":

            if _contains_any(
                text,
                [
                    "input line voltage",
                    "line voltage",
                    "voltage too high",
                ],
            ):

                _add_candidate(
                    candidates,
                    "Input line voltage too high",
                    "Check the input line voltage.",
                    e,
                )

            if _contains_any(
                text,
                [
                    "spindle start/stop",
                    "start/stop duty",
                    "start stop duty",
                ],
            ):

                _add_candidate(
                    candidates,
                    "High spindle start/stop duty",
                    "Check whether the spindle is experiencing excessive start/stop duty.",
                    e,
                )

            if _contains_any(
                text,
                [
                    "regen load",
                    "regen",
                    "spindle drive",
                    "spindle-drive",
                ],
            ):

                _add_candidate(
                    candidates,
                    "Spindle-drive or regenerative-load condition",
                    "Check the spindle-drive/regenerative-load condition described by the manual.",
                    e,
                )

        # ---------------------------------------------------------
        # Alarm 113 - Shuttle In Fault
        # ---------------------------------------------------------

        elif alarm == "113":

            if _contains_any(
                text,
                [
                    "jammed",
                    "jam",
                    "shuttle",
                ],
            ):

                _add_candidate(
                    candidates,
                    "Tool-changer shuttle jam or mechanical obstruction",
                    "Check the tool-changer shuttle for a jam or mechanical obstruction.",
                    e,
                )

            if _contains_any(
                text,
                [
                    "tool in pocket",
                    "pocket facing spindle",
                    "tool pocket",
                ],
            ):

                _add_candidate(
                    candidates,
                    "Tool pocket/tool position preventing shuttle movement",
                    "Check whether a tool pocket is facing the spindle or otherwise preventing shuttle movement.",
                    e,
                )

            if _contains_any(
                text,
                [
                    "loss of power",
                    "loss of tool changer power",
                    "loss of tool-changer power",
                    "tool changer power",
                    "tool-changer power",
                    "k9",
                    "k10",
                    "k11",
                    "k12",
                    "f1",
                ],
            ):

                _add_candidate(
                    candidates,
                    "Tool-changer electrical/power or output/input problem",
                    "Check the tool-changer power and the manual-identified K9-K12/F1 circuits.",
                    e,
                )

    return _merge_candidates(
        candidates
    )


def _merge_candidates(
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    merged = {}

    for candidate in candidates:

        key = candidate["cause"]

        if key not in merged:

            merged[key] = {
                "cause": key,
                "status": candidate["status"],
                "next_check": candidate["next_check"],
                "evidence": [],
            }

        existing_ids = {
            item["evidence_id"]
            for item in merged[key]["evidence"]
        }

        for evidence in candidate["evidence"]:

            if (
                evidence["evidence_id"]
                not in existing_ids
            ):

                merged[key]["evidence"].append(
                    evidence
                )

    return list(
        merged.values()
    )


def select_next_check(
    alarm_number: str,
    candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:

    if not candidates:

        return {
            "check": None,
            "reason": (
                "No supported next check could be "
                "derived from the retrieved manual evidence."
            ),
            "evidence": [],
        }

    # -------------------------------------------------------------
    # Alarm-specific prioritization.
    #
    # These are deliberately conservative. We select among checks
    # already supported by the retrieved evidence.
    # -------------------------------------------------------------

    priority = {
        "122": [
            "Input line voltage too high",
            "High spindle start/stop duty",
            "Spindle-drive or regenerative-load condition",
        ],
        "113": [
            "Tool-changer shuttle jam or mechanical obstruction",
            "Tool pocket/tool position preventing shuttle movement",
            "Tool-changer electrical/power or output/input problem",
        ],
    }

    alarm_priority = priority.get(
        str(alarm_number),
        [],
    )

    for cause in alarm_priority:

        for candidate in candidates:

            if candidate["cause"] == cause:

                return {
                    "check": candidate["next_check"],
                    "reason": (
                        "Selected from a manual-supported "
                        "candidate cause."
                    ),
                    "evidence": candidate["evidence"],
                }

    first = candidates[0]

    return {
        "check": first["next_check"],
        "reason": (
            "Selected from the first manual-supported "
            "candidate cause."
        ),
        "evidence": first["evidence"],
    }


def diagnose(
    alarm_number: str,
    evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:

    candidates = build_candidate_causes(
        alarm_number,
        evidence,
    )

    next_check = select_next_check(
        alarm_number,
        candidates,
    )

    return {
        "alarm_number": str(alarm_number),
        "candidate_causes": candidates,
        "next_check": next_check,
        "abstained": (
            len(candidates) == 0
        ),
        "source": (
            "VF Series Service Manual evidence"
        ),
    }


if __name__ == "__main__":

    print(
        "diagnostic_engine.py loaded successfully"
    )