from fastapi.testclient import TestClient

import main


def fake_retrieval(query="", alarm_code=""):
    return {
        "found": True,
        "alarm_code": alarm_code or "123",
        "query": query,
        "exact_alarm_count": 1,
        "semantic_result_count": 2,
        "evidence": [
            {
                "evidence_id": "E1",
                "citation": "VF Series Service Manual, page 53",
                "chunk_type": "alarm",
                "text": "Alarm 123 Spindle Drive Fault. Possible causes include overvoltage and overcurrent.",
            }
        ],
    }


class FakeResponse:
    text = "The manual identifies Alarm 123 as a spindle drive fault. [E1]"


def fake_model_call(**kwargs):
    return FakeResponse()


def fake_quota():
    return {"allowed": True, "used": 1, "limit": 100}


def test_baseline_qa_returns_answer_and_evidence(monkeypatch):
    monkeypatch.setenv('LLM_ENABLED', 'true')
    monkeypatch.setattr(main, "lookup_alarm", fake_retrieval)
    monkeypatch.setattr(main, "reserve_llm_call", fake_quota)
    monkeypatch.setattr(main.client.models, "generate_content", fake_model_call)

    response = TestClient(main.app).get(
        "/baseline-qa",
        params={"query": "What does Alarm 123 mean?", "alarm_code": "123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["answer"].startswith("The manual identifies")
    assert body["evidence"][0]["evidence_id"] == "E1"


def test_compare_returns_baseline_and_investigator(monkeypatch):
    monkeypatch.setenv('LLM_ENABLED', 'true')
    monkeypatch.setattr(main, "lookup_alarm", fake_retrieval)
    monkeypatch.setattr(main, "reserve_llm_call", fake_quota)
    monkeypatch.setattr(main.client.models, "generate_content", fake_model_call)

    response = TestClient(main.app).get(
        "/compare",
        params={"query": "What does Alarm 123 mean?", "alarm_code": "123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "answer" in body["baseline"]
    assert "candidate_causes" in body["investigator"]
    assert body["baseline"]["evidence"] == body["investigator"]["evidence"]


def test_baseline_abstains_when_retrieval_has_no_evidence(monkeypatch):
    monkeypatch.setattr(
        main,
        "lookup_alarm",
        lambda **kwargs: {"found": False, "evidence": []},
    )
    monkeypatch.setattr(
        main.client.models,
        "generate_content",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("Gemini must not be called without evidence.")
        ),
    )

    response = TestClient(main.app).get(
        "/baseline-qa",
        params={"query": "Unsupported question"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "abstained"
