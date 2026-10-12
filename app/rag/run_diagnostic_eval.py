"""Deterministic investigator evaluation; no live model calls."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from rag.diagnostic_session import DiagnosticSession

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET = REPO_ROOT / "app" / "data" / "diagnostic_eval_cases.jsonl"
OUTPUT = REPO_ROOT / "app" / "data" / "diagnostic_eval_results.json"

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


def evaluate_case(case):
    alarm = str(case["alarm_code"])
    evidence = MANUAL_EVIDENCE.get(alarm, [])
    session = DiagnosticSession(
        alarm,
        f'Alarm {alarm}: {case["scenario"]}',
        evidence,
    )

    for observation in case.get("observations", []):
        session.record_observation(observation)

    state = session.state()
    candidates = state["candidate_causes"]
    actual_causes = [
        item["cause"].lower()
        for item in candidates
        if item["status"] != "ruled_out"
    ]
    expected_causes = [
        cause.lower() for cause in case.get("expected_candidate_causes", [])
    ]

    no_candidates = not candidates
    all_ruled_out = bool(candidates) and all(
        item["status"] == "ruled_out" for item in candidates
    )
    unresolved = any(
        item["status"] in {"possible", "supported"}
        for item in candidates
    )
    # Cases with no expected causes are abstention cases, not cause-accuracy
    # successes. Exclude them from cause-presence and exact-set scoring.
    expected_present = (
        bool(expected_causes)
        and all(
            any(expected in actual for actual in actual_causes)
            for expected in expected_causes
        )
    )
    cause_set_exact = (
        bool(expected_causes)
        and expected_present
        and len(actual_causes) == len(expected_causes)
    )

    next_check = state.get("next_check") or {}
    actual_check = next_check.get("check")
    expected_check = case.get("expected_next_check")

    return {
        "case_id": case["case_id"],
        "case_type": case.get("case_type", "unknown"),
        "evaluation_system": "investigator",
        "evaluation_mode": "deterministic_no_model",
        "expected_abstain": case.get("expected_abstain"),
        "actual_no_candidates": no_candidates,
        "actual_all_candidates_ruled_out": all_ruled_out,
        "actual_has_unresolved_candidate": unresolved,
        "expected_abstention_match": (
            no_candidates == case.get("expected_abstain")
        ),
        "expected_causes": case.get("expected_candidate_causes", []),
        "actual_causes": [
            {"cause": item["cause"], "status": item["status"]}
            for item in candidates
        ],
        "expected_causes_present": expected_present,
        "expected_cause_sets_exact": cause_set_exact,
        "expected_next_check": expected_check,
        "actual_next_check": actual_check,
        "next_check_exact_match": actual_check == expected_check,
        "confidence_band": case.get("confidence_band"),
        "confidence_band_status": (
            "available" if case.get("confidence_band") else "not_provided"
        ),
    }



def score_baseline_answer(case, answer):
    """Score a baseline answer conservatively against the case labels."""
    expected_causes = [
        cause.strip().lower()
        for cause in case.get("expected_candidate_causes", [])
        if cause.strip()
    ]
    normalized_answer = (answer or "").lower()
    has_expected_causes = bool(expected_causes)
    expected_present = (
        has_expected_causes
        and all(cause in normalized_answer for cause in expected_causes)
    )
    return {
        "case_id": case["case_id"],
        "case_type": case.get("case_type", "unknown"),
        "evaluation_system": "baseline",
        "evaluation_mode": "fixed_evidence_live_model",
        "expected_abstain": case.get("expected_abstain"),
        "answer": answer or "",
        "expected_causes": case.get("expected_candidate_causes", []),
        "expected_causes_present": expected_present,
        "abstention_match": (
            not bool(answer and answer.strip())
            if case.get("expected_abstain") is True
            else None
        ),
        "scoring_note": (
            "Literal cause-label matching only; this is not semantic grading."
        ),
    }


def evaluate_baseline_case(case, client, quota_reserver):
    """Call the baseline only after quota reservation; let quota failures stop the run."""
    from rag.llm_quota import DailyQuotaExceeded

    alarm = str(case["alarm_code"])
    evidence = MANUAL_EVIDENCE.get(alarm, [])
    if not evidence:
        return {
            "case_id": case["case_id"],
            "case_type": case.get("case_type", "unknown"),
            "evaluation_system": "baseline",
            "evaluation_mode": "fixed_evidence_live_model",
            "status": "abstained_no_evidence",
            "answer": "",
            "expected_causes_present": False,
            "model_call_made": False,
        }

    passages = "\\n\\n".join(
        f"[{item['evidence_id']}] Citation: {item['citation']}\\n{item['text']}"
        for item in evidence
    )
    prompt = (
        "Answer using only the manual passages supplied. State uncertainty "
        "when a cause is not established. Do not invent maintenance steps. "
        "Do not instruct the user to perform hazardous work.\\n\\n"
        f"Case: {case['scenario']}\\n"
        f"Observations: {json.dumps(case.get('observations', []))}\\n\\n"
        f"Manual passages:\\n{passages}\\n\\n"
        "Give a concise answer and distinguish possible causes from confirmed causes."
    )

    quota = quota_reserver()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    result = score_baseline_answer(case, response.text or "")
    result.update({
        "status": "ok",
        "model": "gemini-2.5-flash",
        "model_call_made": True,
        "quota": quota,
        "evidence_ids": [item["evidence_id"] for item in evidence],
    })
    return result

def summarize(results):
    grouped = defaultdict(list)
    for result in results:
        grouped[result["case_type"]].append(result)

    summaries = {}
    for case_type, items in sorted(grouped.items()):
        count = len(items)
        summaries[case_type] = {
            "cases": count,
            "abstention_matches": sum(
                item["expected_abstention_match"] for item in items
            ),
            "expected_causes_present": sum(
                item["expected_causes_present"] for item in items
            ),
            "exact_cause_sets": sum(
                item["expected_cause_sets_exact"] for item in items
            ),
            "exact_next_check_text_matches": sum(
                item["next_check_exact_match"] for item in items
            ),
            "confidence_band_cases": sum(
                item["confidence_band_status"] == "available"
                for item in items
            ),
        }

    real_count = sum(
        item["case_type"] == "real" for item in results
    )
    synthetic_count = sum(
        item["case_type"] == "synthetic" for item in results
    )
    return {
        "total_cases": len(results),
        "case_type_counts": {
            "real": real_count,
            "synthetic": synthetic_count,
            "other": len(results) - real_count - synthetic_count,
        },
        "by_case_type": summaries,
        "real_evaluation_status": (
            "evaluated" if real_count else "not_evaluated_no_real_cases"
        ),
        "confidence_band_status": (
            "available"
            if any(item["confidence_band_status"] == "available"
                   for item in results)
            else "not_available_dataset_has_no_confidence_bands"
        ),
        "model_calls_made": 0,
        "limitations": [
            "Manual evidence is a fixed test fixture.",
            "All scores describe the supplied evaluation cases only.",
            "Synthetic results are not real-world accuracy.",
            "Exact next-check matching compares strings, not semantic equivalence.",
            "This deterministic run does not evaluate the LLM baseline.",
        ],
    }



def summarize_baseline(results):
    completed = [item for item in results if item.get("status") == "ok"]
    scored = [item for item in completed if item.get("expected_causes")]
    by_type = {}
    for case_type in sorted({item["case_type"] for item in results}):
        items = [item for item in results if item["case_type"] == case_type]
        valid = [item for item in items if item.get("status") == "ok"
                 and item.get("expected_causes")]
        by_type[case_type] = {
            "cases": len(items),
            "completed_model_calls": sum(item.get("model_call_made", False) for item in items),
            "cause_label_matches": sum(item.get("expected_causes_present", False) for item in valid),
            "cases_scored": len(valid),
        }
    return {
        "cases_attempted": len(results),
        "completed_model_calls": len(completed),
        "cause_label_matches": sum(item.get("expected_causes_present", False) for item in scored),
        "cases_scored": len(scored),
        "by_case_type": by_type,
        "scoring_limitation": "Literal cause-label matching only; not semantic accuracy.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live-baseline",
        action="store_true",
        help="Opt in to Gemini baseline calls using the daily quota guard.",
    )
    args = parser.parse_args()

    cases = [
        json.loads(line)
        for line in DATASET.read_text().splitlines()
        if line.strip()
    ]
    investigator_results = [evaluate_case(case) for case in cases]
    report = {
        "evaluation_mode": (
            "fixed_evidence_live_baseline_and_deterministic_investigator"
            if args.live_baseline else "deterministic_no_model"
        ),
        "dataset": str(DATASET.relative_to(REPO_ROOT)),
        "investigator_results": investigator_results,
        "investigator_summary": summarize(investigator_results),
        "baseline_results": [],
        "baseline_summary": None,
        "baseline_status": "not_run_opt_in_required",
    }

    if args.live_baseline:
        from google import genai
        from rag.llm_quota import reserve_llm_call

        client = genai.Client(
            vertexai=True, project="maintenance-investigator", location="global"
        )
        report["baseline_status"] = "running"
        for case in cases:
            try:
                result = evaluate_baseline_case(case, client, reserve_llm_call)
            except Exception as exc:
                # Fail closed: do not attempt any more model calls after a
                # quota, credentials, or service error.
                report["baseline_results"].append({
                    "case_id": case["case_id"],
                    "case_type": case.get("case_type", "unknown"),
                    "evaluation_system": "baseline",
                    "status": "stopped_on_error",
                    "error_type": type(exc).__name__,
                    "model_call_made": False,
                })
                report["baseline_status"] = "stopped_on_error"
                break
            report["baseline_results"].append(result)

        if report["baseline_status"] == "running":
            report["baseline_status"] = "completed"
        report["baseline_summary"] = summarize_baseline(report["baseline_results"])

    report["summary"] = report["investigator_summary"]
    report["summary"]["baseline_status"] = report["baseline_status"]
    report["summary"]["baseline_model_calls_made"] = sum(
        item.get("model_call_made", False) for item in report["baseline_results"]
    )
    report["summary"]["limitations"].append(
        "Fixed manual evidence is a test fixture, not live retrieval."
    )
    if args.live_baseline:
        report["summary"]["limitations"].append(
            "Baseline cause scores use literal label matching, not semantic grading."
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\\n")

    for result in investigator_results:
        print(json.dumps(result))
    print("\\nINVESTIGATOR SUMMARY")
    print(json.dumps(report["investigator_summary"], indent=2))
    if args.live_baseline:
        print("\\nBASELINE SUMMARY")
        print(json.dumps(report["baseline_summary"], indent=2))
        print(f"Baseline status: {report['baseline_status']}")
    print(f"\\nSaved report: {OUTPUT}")

if __name__ == "__main__":
    main()
