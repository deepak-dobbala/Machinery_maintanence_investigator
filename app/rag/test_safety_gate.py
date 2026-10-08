#!/usr/bin/env python3

from safety_gate import evaluate_safety


tests = [
    "Check the input line voltage.",
    "Check the tool-changer shuttle for a jam.",
    "Review the alarm description.",
]


for action in tests:

    result = evaluate_safety(
        action
    )

    print("=" * 60)
    print("ACTION:", action)
    print("STATUS:", result["status"])
    print("REQUIRED:", result["required"])
    print("HAZARDS:", result["hazards"])
    print("MESSAGE:", result["message"])