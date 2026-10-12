from fastapi.testclient import TestClient
from fastapi import HTTPException

import main


def test_gemini_endpoint_blocks_call_when_quota_exhausted():
    client = TestClient(main.app)

    def reject_quota():
        raise main.DailyQuotaExceeded("Daily LLM-call limit reached (1/1 UTC).")

    main.reserve_llm_call = reject_quota

    def forbidden_model_call(*args, **kwargs):
        raise AssertionError("Gemini must not be called when quota is exhausted.")

    main.client.models.generate_content = forbidden_model_call

    response = client.get("/gemini-test")

    assert response.status_code == 429
    assert "limit reached" in response.json()["detail"]


def test_gemini_endpoint_fails_closed_if_quota_service_unavailable():
    client = TestClient(main.app)

    def unavailable_quota():
        raise RuntimeError("Firestore unavailable")

    main.reserve_llm_call = unavailable_quota

    def forbidden_model_call(*args, **kwargs):
        raise AssertionError("Gemini must not be called if quota check fails.")

    main.client.models.generate_content = forbidden_model_call

    response = client.get("/gemini-test")

    assert response.status_code == 503
    assert "blocked" in response.json()["detail"]
