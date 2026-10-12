#!/usr/bin/env python3

from safety_gate import evaluate_safety


def test_electrical_action_is_blocked_pending_loto():
    result = evaluate_safety("Check the input line voltage.")

    assert result["required"] is True
    assert result["blocked"] is True
    assert result["checklist_required"] is True
    assert result["checklist_status"] == "source_missing"
    assert result["status"] == "gate_required"


def test_tool_changer_jam_is_blocked_pending_loto():
    result = evaluate_safety("Check the tool-changer shuttle for a jam.")

    assert result["required"] is True
    assert result["blocked"] is True
    assert result["checklist_required"] is True
    assert result["checklist_status"] == "source_missing"
    assert "unexpected machine movement" in result["hazards"]


def test_high_risk_maintenance_without_energy_terms_is_blocked():
    result = evaluate_safety("Repair the machine.")

    assert result["blocked"] is True
    assert result["checklist_required"] is True
    assert result["checklist_status"] == "source_missing"


def test_alarm_description_review_does_not_trigger_loto_gate():
    result = evaluate_safety("Review the alarm description.")

    assert result["required"] is False
    assert result["blocked"] is False
    assert result["checklist_required"] is False
    assert result["status"] == "clear"


def test_blocked_action_warns_that_emergency_stop_is_not_isolation():
    result = evaluate_safety("Check the input line voltage.")

    assert "emergency stop alone" in result["message"].lower()
    assert "not evidence of energy isolation" in result["message"].lower()
