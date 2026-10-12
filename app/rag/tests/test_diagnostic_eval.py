from run_diagnostic_eval import evaluate_case, summarize


def test_empty_expected_causes_do_not_count_as_cause_accuracy():
    result = evaluate_case(
        {
            "case_id": "SYN-UNK-TEST",
            "case_type": "synthetic",
            "alarm_code": "999",
            "scenario": "Unsupported alarm with no evidence.",
            "observations": [],
            "expected_candidate_causes": [],
            "expected_abstain": True,
            "expected_next_check": None,
        }
    )

    assert result["expected_abstention_match"] is True
    assert result["expected_causes_present"] is False
    assert result["expected_cause_sets_exact"] is False


def test_summary_separates_synthetic_and_real_cases():
    results = [
        {
            "case_type": "synthetic",
            "expected_abstention_match": True,
            "expected_causes_present": True,
            "expected_cause_sets_exact": False,
            "next_check_exact_match": False,
            "confidence_band_status": "not_provided",
        },
        {
            "case_type": "real",
            "expected_abstention_match": False,
            "expected_causes_present": False,
            "expected_cause_sets_exact": False,
            "next_check_exact_match": False,
            "confidence_band_status": "not_provided",
        },
    ]

    summary = summarize(results)

    assert summary["case_type_counts"]["synthetic"] == 1
    assert summary["case_type_counts"]["real"] == 1
    assert summary["by_case_type"]["synthetic"]["expected_causes_present"] == 1
    assert summary["by_case_type"]["real"]["expected_causes_present"] == 0
    assert summary["model_calls_made"] == 0


def test_baseline_without_evidence_abstains_without_quota_or_model_call():
    from run_diagnostic_eval import evaluate_baseline_case

    class NeverCalled:
        class models:
            @staticmethod
            def generate_content(**kwargs):
                raise AssertionError("Model must not be called without evidence.")

    def quota_must_not_be_reserved():
        raise AssertionError("Quota must not be reserved without evidence.")

    result = evaluate_baseline_case(
        {
            "case_id": "SYN-UNK-TEST",
            "case_type": "synthetic",
            "alarm_code": "999",
            "scenario": "Unknown alarm",
            "observations": [],
            "expected_candidate_causes": [],
            "expected_abstain": True,
        },
        NeverCalled(),
        quota_must_not_be_reserved,
    )

    assert result["status"] == "abstained_no_evidence"
    assert result["model_call_made"] is False


def test_baseline_reserves_quota_before_calling_model():
    from run_diagnostic_eval import evaluate_baseline_case

    events = []

    class FakeModels:
        def generate_content(self, **kwargs):
            events.append("model")
            assert kwargs["model"] == "gemini-2.5-flash"
            return type("Response", (), {"text": "Possible jammed slide."})()

    class FakeClient:
        models = FakeModels()

    def reserve():
        events.append("quota")
        return {"reserved": True}

    result = evaluate_baseline_case(
        {
            "case_id": "SYN-113-TEST",
            "case_type": "synthetic",
            "alarm_code": "113",
            "scenario": "Shuttle fault",
            "observations": [],
            "expected_candidate_causes": ["jammed slide"],
            "expected_abstain": False,
        },
        FakeClient(),
        reserve,
    )

    assert events == ["quota", "model"]
    assert result["model_call_made"] is True
    assert result["expected_causes_present"] is True


def test_baseline_quota_failure_prevents_model_call():
    from run_diagnostic_eval import evaluate_baseline_case
    from rag.llm_quota import DailyQuotaExceeded

    class NeverCalled:
        class models:
            @staticmethod
            def generate_content(**kwargs):
                raise AssertionError("Model must not be called after quota failure.")

    def exhausted_quota():
        raise DailyQuotaExceeded("test quota exhausted")

    try:
        evaluate_baseline_case(
            {
                "case_id": "SYN-113-QUOTA",
                "case_type": "synthetic",
                "alarm_code": "113",
                "scenario": "Shuttle fault",
                "observations": [],
                "expected_candidate_causes": ["jammed slide"],
                "expected_abstain": False,
            },
            NeverCalled(),
            exhausted_quota,
        )
    except DailyQuotaExceeded:
        pass
    else:
        raise AssertionError("Expected quota exhaustion to stop evaluation.")
