#!/usr/bin/env python3

from manual_retriever import (
    search_manual,
    format_evidence,
)

from diagnostic_session import (
    DiagnosticSession,
)


def print_state(state):

    print()
    print("CANDIDATES")
    print("-" * 60)

    for candidate in state[
        "candidate_causes"
    ]:

        print(
            candidate["status"],
            "|",
            candidate["cause"],
        )

    print()
    print("NEXT CHECK")
    print("-" * 60)

    print(
        state["next_check"]["check"]
    )

    print()
    print("SAFETY")
    print("-" * 60)

    safety = state[
        "next_check"
    ].get(
        "safety",
        {},
    )

    print(
        "STATUS:",
        safety.get("status"),
    )

    print(
        "REQUIRED:",
        safety.get("required"),
    )

    print(
        "HAZARDS:",
        safety.get("hazards"),
    )

    print(
        "MESSAGE:",
        safety.get("message"),
    )

    print()
    print(
        "CONFIRMED:",
        state["confirmed_cause"],
    )

    print(
        "COMPLETE:",
        state["complete"],
    )

def main():

    alarm = "113"

    query = (
        "Alarm 113 Shuttle In Fault"
    )

    search_result = search_manual(
        query,
        alarm,
    )

    evidence = format_evidence(
        search_result,
        max_results=8,
    )

    session = DiagnosticSession(
        alarm,
        query,
        evidence,
    )

    print("=" * 60)
    print("INITIAL SESSION")
    print("=" * 60)

    print_state(
        session.state()
    )

    print()
    print("=" * 60)
    print("TECHNICIAN OBSERVATION 1")
    print("=" * 60)

    state = session.record_observation(
        "No jam or obstruction was found."
    )

    print_state(state)

    print()
    print("=" * 60)
    print("TECHNICIAN OBSERVATION 2")
    print("=" * 60)

    state = session.record_observation(
        "Tool changer power problem found."
    )

    print_state(state)

    print()
    print("=" * 60)
    print("TECHNICIAN OBSERVATION 3")
    print("=" * 60)

    state = session.record_observation(
        "Tool changer power problem confirmed."
    )

    print_state(state)


if __name__ == "__main__":
    main()