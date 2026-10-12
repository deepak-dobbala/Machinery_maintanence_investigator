from rag.history_ranking import apply_history_ranking


def test_confirmed_non_synthetic_history_changes_tie_break_order():
    candidates = [
        {"cause": "Cause A", "sourced": True, "confidence_band": "unlikely"},
        {"cause": "Cause B", "sourced": True, "confidence_band": "unlikely"},
    ]
    records = [{
        "diagnosis": "Cause B",
        "confirmation_status": "confirmed",
        "resolution_status": "confirmed",
        "synthetic": False,
    }]

    ranked = apply_history_ranking(candidates, records)

    assert ranked[0]["cause"] == "Cause B"
    assert ranked[0]["history_match"] is True
    assert ranked[0]["confidence_band"] == "unlikely"


def test_synthetic_or_unconfirmed_history_does_not_change_order():
    candidates = [
        {"cause": "Cause A", "sourced": True},
        {"cause": "Cause B", "sourced": True},
    ]
    records = [
        {
            "diagnosis": "Cause B",
            "confirmation_status": "confirmed",
            "resolution_status": "confirmed",
            "synthetic": True,
        },
        {
            "diagnosis": "Cause A",
            "confirmation_status": "possible",
            "resolution_status": "confirmed",
            "synthetic": False,
        },
    ]

    ranked = apply_history_ranking(candidates, records)

    assert [item["cause"] for item in ranked] == ["Cause A", "Cause B"]
    assert not any(item["history_match"] for item in ranked)


def test_history_never_moves_unsourced_candidate_ahead_of_sourced():
    candidates = [
        {"cause": "Cause A", "sourced": True},
        {"cause": "Cause B", "sourced": False},
    ]
    records = [{
        "diagnosis": "Cause B",
        "confirmation_status": "confirmed",
        "resolution_status": "confirmed",
        "synthetic": False,
    }]

    ranked = apply_history_ranking(candidates, records)

    assert ranked[0]["cause"] == "Cause A"
    assert ranked[1]["cause"] == "Cause B"
