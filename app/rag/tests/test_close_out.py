from unittest.mock import Mock

from agents.day5_workflow import agent


def test_close_out_does_not_claim_persistence_when_fields_are_missing():
    ctx = Mock()
    ctx.state = {
        "diagnostic_case": {
            "alarm_number": "123",
            "session_state": {"confirmed_cause": "Spindle drive failure"},
        }
    }

    result = agent.close_out(ctx, {})

    assert result["status"] == "confirmed_not_persisted"
    assert "machine_model" in result["stop_reason"]
    assert "symptom" in result["stop_reason"]
    assert "action_taken" in result["stop_reason"]
    assert "work_order_id" not in result


def test_close_out_persists_confirmed_diagnosis_with_complete_fields(monkeypatch):
    recorded = {}

    def fake_writer(**kwargs):
        recorded.update(kwargs)
        return {"work_order_id": "test-work-order-123"}

    monkeypatch.setattr(
        "rag.work_order_writer.record_confirmed_work_order",
        fake_writer,
    )

    ctx = Mock()
    ctx.state = {
        "diagnostic_case": {
            "alarm_number": "123",
            "session_state": {"confirmed_cause": "Spindle drive failure"},
        }
    }
    node_input = {
        "machine_model": "VF-2",
        "symptom": "Spindle drive fault alarm",
        "action_taken": "Replaced failed drive component",
    }

    result = agent.close_out(ctx, node_input)

    assert result["status"] == "confirmed"
    assert result["work_order_id"] == "test-work-order-123"
    assert recorded == {
        "alarm_code": "123",
        "machine_model": "VF-2",
        "symptom": "Spindle drive fault alarm",
        "diagnosis": "Spindle drive failure",
        "action_taken": "Replaced failed drive component",
        "confirmation_status": "confirmed",
    }
