import json
from pathlib import Path

from rag.diagnostic_session import DiagnosticSession

DATASET = Path("data/diagnostic_eval_cases.jsonl")

MANUAL_EVIDENCE = {
    "113": [{
        "evidence_id": "MANUAL-113",
        "citation": "Haas VF Series Service Manual, Rev E, June 2002, p. 52",
        "chunk_type": "alarm",
        "text": (
            "Alarm 113 Shuttle In Fault: a jammed slide or a tool "
            "in a pocket facing the spindle may prevent shuttle movement. "
            "A loss of power to the tool changer is also a possible cause."
        ),
    }],
    "122": [{
        "evidence_id": "MANUAL-122",
        "citation": "Haas VF Series Service Manual, Rev E, June 2002, p. 53",
        "chunk_type": "alarm",
        "text": (
            "Alarm 122 Regen Overheat: incoming line voltage too high "
            "is a possible cause. High spindle start/stop duty cycle "
            "can also contribute to this condition."
        ),
    }],
}


def main():
    cases = [
        json.loads(line)
        for line in DATASET.read_text().splitlines()
        if line.strip()
    ]

    summary = {
        "cases": len(cases),
        "expected_abstention_matches": 0,
        "no_candidate_cases": 0,
        "all_candidates_ruled_out_cases": 0,
        "unresolved_candidate_cases": 0,
        "expected_causes_present": 0,
        "expected_cause_sets_exact": 0,
        "next_check_exact_matches": 0,
    }

    for case in cases:
        alarm = str(case["alarm_code"])
        evidence = MANUAL_EVIDENCE.get(alarm, [])

        session = DiagnosticSession(
            alarm,
            f'Alarm {alarm}: {case["scenario"]}',
            evidence,
        )

        initial_state = session.state()

        for observation in case["observations"]:
            state = session.record_observation(observation)

        state = session.state()
        candidates = state["candidate_causes"]

        actual_causes = [
            c["cause"].lower() for c in candidates
            if c["status"] != "ruled_out"
        ]
        expected_causes = [
            c.lower() for c in case["expected_candidate_causes"]
        ]

        no_candidates = len(candidates) == 0
        all_ruled_out = (
            bool(candidates)
            and all(c["status"] == "ruled_out" for c in candidates)
        )
        unresolved = any(
            c["status"] in {"possible", "supported"}
            for c in candidates
        )

        abstention_match = (
            no_candidates == case["expected_abstain"]
        )

        expected_present = all(
            any(expected in actual for actual in actual_causes)
            for expected in expected_causes
        )
        cause_set_exact = (
            expected_present and len(actual_causes) == len(expected_causes)
        )

        actual_check = state["next_check"]["check"]
        expected_check = case["expected_next_check"]
        check_match = actual_check == expected_check

        summary["expected_abstention_matches"] += int(abstention_match)
        summary["no_candidate_cases"] += int(no_candidates)
        summary["all_candidates_ruled_out_cases"] += int(all_ruled_out)
        summary["unresolved_candidate_cases"] += int(unresolved)
        summary["expected_causes_present"] += int(expected_present)
        summary["expected_cause_sets_exact"] += int(cause_set_exact)
        summary["next_check_exact_matches"] += int(check_match)

        print(json.dumps({
            "case_id": case["case_id"],
            "case_type": case["case_type"],
            "expected_abstain": case["expected_abstain"],
            "actual_no_candidates": no_candidates,
            "actual_all_candidates_ruled_out": all_ruled_out,
            "actual_has_unresolved_candidate": unresolved,
            "expected_abstention_match": abstention_match,
            "expected_causes": case["expected_candidate_causes"],
            "actual_causes": [
                {
                    "cause": c["cause"],
                    "status": c["status"],
                }
                for c in candidates
            ],
            "expected_causes_present": expected_present,
            "expected_cause_sets_exact": cause_set_exact,
            "expected_next_check": expected_check,
            "actual_next_check": actual_check,
            "next_check_exact_match": check_match,
        }))

    print("\nSUMMARY")
    print(json.dumps(summary, indent=2))
    print(
        "\nEvaluation note: all cases are synthetic. Manual evidence is "
        "a fixed test fixture; observations are passed separately through "
        "DiagnosticSession. These scores are not real-world accuracy."
    )


if __name__ == "__main__":
    main()
