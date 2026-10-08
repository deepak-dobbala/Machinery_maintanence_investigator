#!/usr/bin/env python3

"""
Stateful diagnostic investigation session.

Tracks:
- alarm
- retrieved evidence
- candidate causes
- candidate status
- current next check
- technician observations
- confirmed cause

Status values:
    possible
    supported
    ruled_out
    confirmed
"""


from typing import Any, Dict, List

from diagnostic_engine import diagnose
from safety_gate import evaluate_safety


VALID_STATUSES = {
    "possible",
    "supported",
    "ruled_out",
    "confirmed",
}


class DiagnosticSession:

    def __init__(
        self,
        alarm_number: str,
        query: str,
        evidence: List[Dict[str, Any]],
    ):

        self.alarm_number = str(
            alarm_number
        )

        self.query = query

        self.evidence = evidence

        diagnostic_result = diagnose(
            self.alarm_number,
            self.evidence,
        )

        self.candidate_causes = (
            diagnostic_result[
                "candidate_causes"
            ]
        )

        self.next_check = (
            diagnostic_result[
                "next_check"
            ]
        )

        # Apply the safety gate to the initial check too.
        if self.next_check.get("check"):

            evidence = None

            if self.next_check.get(
                "evidence"
            ):
                evidence = self.next_check[
                    "evidence"
                ][0]

            self.next_check[
                "safety"
            ] = evaluate_safety(
                self.next_check["check"],
                evidence,
            )

        else:

            self.next_check[
                "safety"
            ] = {
                "required": False,
                "status": "complete",
                "hazards": [],
                "message": (
                    "No diagnostic action is currently required."
                ),
            }

        self.observations = []

        self.confirmed_cause = None

    def record_observation(
        self,
        observation: str,
    ) -> Dict[str, Any]:

        observation = observation.strip()

        if not observation:
            raise ValueError(
                "Observation cannot be empty."
            )

        self.observations.append(
            observation
        )

        self._update_candidates(
            observation
        )

        self._select_next_check()

        return self.state()

    def _update_candidates(
        self,
        observation: str,
    ):

        text = observation.lower()

        # ---------------------------------------------------------
        # Explicit confirmation language.
        # ---------------------------------------------------------

        for candidate in self.candidate_causes:

            cause = candidate[
                "cause"
            ]

            cause_lower = cause.lower()

            if (
                "confirmed" in text
                and self._matches_candidate(
                    text,
                    cause_lower,
                )
            ):

                candidate[
                    "status"
                ] = "confirmed"

                self.confirmed_cause = cause

                continue

            # -----------------------------------------------------
            # Explicit negative finding.
            # -----------------------------------------------------

            if self._is_negative_observation(
                text
            ):

                if self._matches_candidate(
                    text,
                    cause_lower,
                ):

                    candidate[
                        "status"
                    ] = "ruled_out"

        # ---------------------------------------------------------
        # Simple manual-check interpretation.
        #
        # These rules deliberately require explicit technician
        # language. They do not infer physical machine state.
        # ---------------------------------------------------------

        if self.alarm_number == "122":

            if (
                "voltage" in text
                and any(
                    word in text
                    for word in [
                        "high",
                        "too high",
                        "above",
                    ]
                )
            ):

                self._set_status(
                    "Input line voltage too high",
                    "supported",
                )

            if (
                "voltage" in text
                and any(
                    word in text
                    for word in [
                        "normal",
                        "within range",
                        "ok",
                        "okay",
                    ]
                )
            ):

                self._set_status(
                    "Input line voltage too high",
                    "ruled_out",
                )

        if self.alarm_number == "113":

            if (
                any(
                    word in text
                    for word in [
                        "jam",
                        "jammed",
                        "obstruction",
                    ]
                )
                and any(
                    word in text
                    for word in [
                        "found",
                        "present",
                        "yes",
                    ]
                )
            ):

                self._set_status(
                    "Tool-changer shuttle jam or mechanical obstruction",
                    "supported",
                )

            if (
                any(
                    word in text
                    for word in [
                        "no jam",
                        "not jammed",
                        "no obstruction",
                        "clear",
                    ]
                )
            ):

                self._set_status(
                    "Tool-changer shuttle jam or mechanical obstruction",
                    "ruled_out",
                )

    def _matches_candidate(
        self,
        observation: str,
        candidate: str,
    ) -> bool:

        observation = observation.lower()
        candidate = candidate.lower()

        aliases = {
            "tool-changer shuttle jam or mechanical obstruction": [
                "jam",
                "jammed",
                "obstruction",
                "shuttle",
            ],
            "tool-changer electrical/power or output/input problem": [
                "tool changer power",
                "tool-changer power",
                "power problem",
                "electrical problem",
                "output/input problem",
                "k9",
                "k10",
                "k11",
                "k12",
                "f1",
            ],
            "input line voltage too high": [
                "input line voltage",
                "line voltage",
                "voltage too high",
            ],
            "high spindle start/stop duty": [
                "start/stop duty",
                "start stop duty",
                "excessive start/stop",
            ],
            "spindle-drive or regenerative-load condition": [
                "spindle drive",
                "spindle-drive",
                "regen",
                "regenerative load",
            ],
        }

        for key, terms in aliases.items():

            if key == candidate:

                return any(
                    term in observation
                    for term in terms
                )

        return False

        keywords = []

        for word in candidate.split():
            cleaned = (
                word
                .strip(".,;:()")
                .lower()
            )

            if len(cleaned) >= 5:
                keywords.append(
                    cleaned
                )

        return any(
            keyword in observation
            for keyword in keywords
        )

    def _is_negative_observation(
        self,
        observation: str,
    ) -> bool:

        return any(
            phrase in observation
            for phrase in [
                "not found",
                "no ",
                "none",
                "normal",
                "within range",
                "clear",
                "no issue",
                "no fault",
            ]
        )

    def _set_status(
        self,
        cause: str,
        status: str,
    ):

        if status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status: {status}"
            )

        for candidate in self.candidate_causes:

            if candidate[
                "cause"
            ] == cause:

                candidate[
                    "status"
                ] = status

                if status == "confirmed":
                    self.confirmed_cause = cause

    def _select_next_check(self):

        # ---------------------------------------------------------
        # Stop if a cause has been confirmed.
        # ---------------------------------------------------------

        if self.confirmed_cause:

            self.next_check = {
                "check": None,
                "reason": (
                    "A candidate cause has been confirmed."
                ),
                "evidence": [],
                "safety": {
                    "required": False,
                    "status": "complete",
                    "hazards": [],
                    "message": (
                        "Diagnostic session complete."
                    ),
                },
            }

            return

        # ---------------------------------------------------------
        # Select the first unresolved manual-supported cause.
        # ---------------------------------------------------------

        for candidate in self.candidate_causes:

            if candidate["status"] not in {
                "possible",
                "supported",
            }:
                continue

            action = candidate["next_check"]

            safety = evaluate_safety(
                action,
                candidate["evidence"][0]
                if candidate["evidence"]
                else None,
            )

            self.next_check = {
                "check": action,
                "reason": (
                    "Selected from the next unresolved "
                    "manual-supported candidate."
                ),
                "evidence": candidate[
                    "evidence"
                ],
                "safety": safety,
            }

            return

        # ---------------------------------------------------------
        # All currently known causes were ruled out.
        # ---------------------------------------------------------

        self.next_check = {
            "check": None,
            "reason": (
                "All currently retrieved candidate "
                "causes have been ruled out. "
                "Additional manual evidence is required."
            ),
            "evidence": [],
            "safety": {
                "required": False,
                "status": "abstain",
                "hazards": [],
                "message": (
                    "No supported diagnostic action remains."
                ),
            },
        }

    def state(self) -> Dict[str, Any]:

        return {
            "alarm_number": self.alarm_number,
            "query": self.query,
            "candidate_causes": self.candidate_causes,
            "next_check": self.next_check,
            "observations": self.observations,
            "confirmed_cause": self.confirmed_cause,
            "complete": (
                self.confirmed_cause is not None
            ),
        }