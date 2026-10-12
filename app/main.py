from fastapi import FastAPI, HTTPException
from google import genai
from agents.investigator.tools import lookup_alarm
from rag.llm_quota import DailyQuotaExceeded, reserve_llm_call


app = FastAPI()


def require_llm_enabled():
    """Fail closed unless model calls are explicitly enabled."""
    import os
    if os.environ.get("LLM_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(
            status_code=503,
            detail="LLM calls are disabled by the deployment kill switch.",
        )


client = genai.Client(
    vertexai=True,
    project="maintenance-investigator",
    location="global",
)

@app.get("/health")
def return_health():
    return {"status":"ok"}


@app.get("/gemini-test")
def gemini_test():
    try:
        quota = reserve_llm_call()
    except DailyQuotaExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        # Fail closed: never invoke the model if quota enforcement is unavailable.
        raise HTTPException(
            status_code=503,
            detail="LLM quota service unavailable; model call blocked.",
        ) from exc

    require_llm_enabled()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Reply with exactly: GEMINI_OK",
    )

    return {
        "status": "ok",
        "response": response.text,
        "quota": quota,
    }




@app.get("/baseline-qa")
def baseline_qa(query: str, alarm_code: str = ""):
    """One-shot retrieval Q&A baseline using the same manuals and model."""
    retrieved = lookup_alarm(query=query, alarm_code=alarm_code)

    if not retrieved.get("found") or not retrieved.get("evidence"):
        return {
            "status": "abstained",
            "answer": "The available manual evidence does not establish that.",
            "evidence": [],
            "retrieval": retrieved,
        }

    passages = "\\n\\n".join(
        f"[{item.get('evidence_id', 'unknown')}] "
        f"Citation: {item.get('citation', 'citation unavailable')}\\n"
        f"{item.get('text', '')}"
        for item in retrieved["evidence"]
    )
    prompt = (
        "Answer the question using only the manual passages below. "
        "Cite supporting evidence IDs and citations for each factual claim. "
        "If the passages do not support an answer, say so. Do not invent "
        "maintenance procedures or recommend hazardous actions.\n\n"
        f"Question: {query or ('Alarm ' + alarm_code)}\n\n"
        f"Manual passages:\n{passages}"
    )

    try:
        quota = reserve_llm_call()
    except DailyQuotaExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="LLM quota service unavailable; model call blocked.",
        ) from exc

    require_llm_enabled()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return {
        "status": "ok",
        "answer": response.text,
        "evidence": retrieved["evidence"],
        "retrieval": {
            "exact_alarm_count": retrieved.get("exact_alarm_count", 0),
            "semantic_result_count": retrieved.get("semantic_result_count", 0),
        },
        "quota": quota,
    }



    # Both approaches receive exactly the same manual passages.
    # History is an additional ranking signal for the investigator only.
    history_records = []
    history_status = "unavailable"
    if alarm_code:
        try:
            history_result = get_work_order_history(
                alarm_code=alarm_code,
                machine_model=machine_model or None,
            )
            history_records = history_result.get("records", [])
            history_status = "available"
        except Exception:
            # History is optional; preserve manual-only diagnosis on failure.
            history_records = []
            history_status = "unavailable"

    diagnostic = diagnose(
        alarm_code,
        evidence,
        history_records=history_records,
    )

    retrieved = lookup_alarm(query=query, alarm_code=alarm_code)
    evidence = retrieved.get("evidence", [])

    if not retrieved.get("found") or not evidence:
        abstention = "The available manual evidence does not establish that."
        return {
            "status": "abstained",
            "question": query,
            "alarm_code": alarm_code,
            "baseline": {"answer": abstention, "evidence": []},
            "investigator": {
                "candidate_causes": [],
                "next_check": None,
                "abstained": True,
            },
            "comparison_note": "No retrieved manual evidence; neither approach may infer a cause.",
        }

    # Both approaches receive exactly the same retrieved passages.
    diagnostic = diagnose(alarm_code, evidence)

    passages = "\\n\\n".join(
        f"[{item.get('evidence_id', 'unknown')}] "
        f"Citation: {item.get('citation', 'citation unavailable')}\\n"
        f"{item.get('text', '')}"
        for item in evidence
    )
    prompt = (
        "Answer using only the supplied manual passages. Cite evidence IDs "
        "and citations for factual claims. If unsupported, say the manual "
        "does not establish the answer. Do not invent maintenance procedures.\n\n"
        f"Question: {query or ('Alarm ' + alarm_code)}\n\n"
        f"Manual passages:\n{passages}"
    )

    try:
        quota = reserve_llm_call()
    except DailyQuotaExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="LLM quota service unavailable; model call blocked.",
        ) from exc

    require_llm_enabled()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return {
        "status": "ok",
        "question": query,
        "alarm_code": alarm_code,
        "baseline": {
            "answer": response.text,
            "evidence": evidence,
            "model": "gemini-2.5-flash",
        },
        "investigator": {
            "candidate_causes": diagnostic["candidate_causes"],
            "next_check": diagnostic["next_check"],
            "abstained": diagnostic["abstained"],
            "evidence": evidence,
        },
        "history_status": history_status,
        "history_records_used": len(history_records),
        "comparison_note": (
            "Both approaches received the same retrieved manual passages. "
            "Only the investigator uses confirmed, non-synthetic history as a "
            "ranking tie-breaker; history does not prove causation or increase "
            "confidence. If history retrieval fails, diagnosis falls back to "
            "manual evidence only."
        ),
        "quota": quota,
    }


@app.get("/compare")
def compare_investigator_baseline(
    query: str,
    alarm_code: str = "",
    machine_model: str = "",
):
    """Compare baseline Q&A with diagnosis informed by eligible history."""
    from rag.diagnostic_engine import diagnose
    from rag.work_order_history import get_work_order_history

    retrieved = lookup_alarm(query=query, alarm_code=alarm_code)
    evidence = retrieved.get("evidence", [])

    if not retrieved.get("found") or not evidence:
        abstention = "The available manual evidence does not establish that."
        return {
            "status": "abstained",
            "question": query,
            "alarm_code": alarm_code,
            "baseline": {"answer": abstention, "evidence": []},
            "investigator": {
                "candidate_causes": [],
                "next_check": None,
                "abstained": True,
                "evidence": [],
            },
            "history_status": "not_used",
            "history_records_used": 0,
            "comparison_note": (
                "No retrieved manual evidence; neither approach may infer a cause."
            ),
        }

    history_records = []
    history_status = "unavailable"
    if alarm_code:
        try:
            history_result = get_work_order_history(
                alarm_code=alarm_code,
                machine_model=machine_model or None,
            )
            history_records = history_result.get("records", [])
            history_status = "available"
        except Exception:
            # History is optional; keep diagnosis grounded in manual evidence.
            history_records = []
            history_status = "unavailable"

    diagnostic = diagnose(
        alarm_code,
        evidence,
        history_records=history_records,
    )

    passages = "\n\n".join(
        f"[{item.get('evidence_id', 'unknown')}] "
        f"Citation: {item.get('citation', 'citation unavailable')}\n"
        f"{item.get('text', '')}"
        for item in evidence
    )
    prompt = (
        "Answer using only the supplied manual passages. Cite evidence IDs "
        "and citations for factual claims. If unsupported, say the manual "
        "does not establish the answer. Do not invent maintenance procedures.\n\n"
        f"Question: {query or ('Alarm ' + alarm_code)}\n\n"
        f"Manual passages:\n{passages}"
    )

    try:
        quota = reserve_llm_call()
    except DailyQuotaExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="LLM quota service unavailable; model call blocked.",
        ) from exc

    require_llm_enabled()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return {
        "status": "ok",
        "question": query,
        "alarm_code": alarm_code,
        "baseline": {
            "answer": response.text,
            "evidence": evidence,
            "model": "gemini-2.5-flash",
        },
        "investigator": {
            "candidate_causes": diagnostic["candidate_causes"],
            "next_check": diagnostic["next_check"],
            "abstained": diagnostic["abstained"],
            "evidence": evidence,
        },
        "history_status": history_status,
        "history_records_used": len(history_records),
        "comparison_note": (
            "Both approaches received the same retrieved manual passages. "
            "Only the investigator uses confirmed, non-synthetic history as a "
            "ranking tie-breaker; history does not prove causation or increase "
            "confidence. If history retrieval fails, diagnosis falls back to "
            "manual evidence only."
        ),
        "quota": quota,
    }
