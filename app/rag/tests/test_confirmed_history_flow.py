from agents.day5_workflow import agent
from rag.history_ranking import apply_history_ranking


def test_confirmed_closeout_record_changes_next_alarm_ranking(monkeypatch):
    # Step 1: close out a confirmed diagnosis without using live Firestore.
    persisted_records = []

    def fake_writer(**kwargs):
        record = {
            **kwargs,
            "confirmation_status": "confirmed",
            "resolution_status": "confirmed",
            "synthetic": False,
        }
        persisted_records.append(record)
        return {"work_order_id": "mock-work-order-001"}

    monkeypatch.setattr(
        "rag.work_order_writer.record_confirmed_work_order",
        fake_writer,
    )

    class FakeContext:
        state = {
            "diagnostic_case": {
                "alarm_number": "123",
                "session_state": {
                    "confirmed_cause": "Spindle drive failure",
                },
            }
        }

    closeout = agent.close_out(
        FakeContext(),
        {
            "machine_model": "VF-2",
            "symptom": "Spindle drive fault",
            "action_taken": "Replaced failed drive component",
        },
    )

    assert closeout["status"] == "confirmed"
    assert closeout["work_order_id"] == "mock-work-order-001"
    assert len(persisted_records) == 1

    # Step 2: simulate the next matching alarm's candidate list.
    # Both candidates are sourced and have equal initial confidence,
    # so eligible history can act as a tie-breaker.
    next_candidates = [
        {
            "cause": "Coolant flow restriction",
            "sourced": True,
            "confidence_band": "probable",
        },
        {
            "cause": "Spindle drive failure",
            "sourced": True,
            "confidence_band": "probable",
        },
    ]

    ranked = apply_history_ranking(next_candidates, persisted_records)

    # Step 3: the confirmed historical match ranks first,
    # but history does not inflate diagnostic confidence.
    assert ranked[0]["cause"] == "Spindle drive failure"
    assert ranked[0]["history_match"] is True
    assert ranked[0]["confidence_band"] == "probable"
    assert ranked[1]["cause"] == "Coolant flow restriction"
    assert ranked[1]["history_match"] is False
    assert all(
        candidate["confidence_band"] == "probable"
        for candidate in ranked
    )
