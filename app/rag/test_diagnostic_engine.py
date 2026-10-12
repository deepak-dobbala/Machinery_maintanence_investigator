#!/usr/bin/env python3

from manual_retriever import search_manual, format_evidence
from diagnostic_engine import diagnose


def run_test(alarm_number, query):
    print("=" * 70)
    print(f"ALARM {alarm_number}")
    print("=" * 70)

    search_result = search_manual(
        query,
        str(alarm_number),
    )

    evidence = format_evidence(
        search_result,
        max_results=8,
    )

    print()
    print("RETRIEVED EVIDENCE")
    print("-" * 70)

    for item in evidence:
        print(
            item["evidence_id"],
            "|",
            item["citation"],
            "|",
            item["chunk_type"],
            "|",
            item["subsystem"],
        )

    result = diagnose(
        str(alarm_number),
        evidence,
    )

    print()
    print("CANDIDATE CAUSES")
    print("-" * 70)

    for candidate in result["candidate_causes"]:
        print()
        print("CAUSE:", candidate["cause"])
        print("STATUS:", candidate["status"])

        for evidence_item in candidate["evidence"]:
            print(
                "  EVIDENCE:",
                evidence_item["evidence_id"],
                "|",
                evidence_item["citation"],
            )

    print()
    print("NEXT CHECK")
    print("-" * 70)

    next_check = result["next_check"]

    print("CHECK:", next_check["check"])
    print("REASON:", next_check["reason"])

    for evidence_item in next_check["evidence"]:
        print(
            "  EVIDENCE:",
            evidence_item["evidence_id"],
            "|",
            evidence_item["citation"],
        )

    print()
    print("ABSTAINED:", result["abstained"])
    print()


if __name__ == "__main__":

    run_test(
        "122",
        "Alarm 122 Regen Overheat",
    )

    run_test(
        "113",
        "Alarm 113 Shuttle In Fault",
    )

def test_unsourced_candidate_confidence_is_capped_at_probable():
    from rag.diagnostic_engine import _merge_candidates

    merged = _merge_candidates([
        {
            "cause": "Spindle drive failure",
            "status": "candidate",
            "next_check": "Inspect diagnostic evidence",
            "confidence_band": "high",
            "sourced": False,
            "evidence": [],
        }
    ])

    assert len(merged) == 1
    assert merged[0]["confidence_band"] in {"unlikely", "probable"}
    assert merged[0]["sourced"] is False


def test_irrelevant_passage_does_not_verify_cause_terms():
    from rag.diagnostic_engine import _verify_evidence_terms

    result = _verify_evidence_terms(
        "Spindle drive failure",
        {
            "citation": "VF Series Service Manual, page 53",
            "text": "The coolant tank should be inspected for leaks.",
        },
    )

    assert result["verified"] is False
    assert result["matched_terms"] == []
