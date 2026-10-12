from unittest.mock import patch

import pytest

from rag.llm_quota import DailyQuotaExceeded, reserve_llm_call


def test_exhausted_quota_raises_before_any_model_call():
    with patch("rag.llm_quota.firestore.Client") as client_factory:
        with patch.dict("os.environ", {"DAILY_LLM_CALL_LIMIT": "1"}):
            db = client_factory.return_value
            ref = db.collection.return_value.document.return_value
            snapshot = ref.get.return_value
            snapshot.to_dict.return_value = {"count": 1}

            with pytest.raises(DailyQuotaExceeded, match="limit reached"):
                reserve_llm_call()

            # No quota write is made once the limit is exhausted.
            db.transaction.assert_called_once()
            db.batch.assert_not_called()
            db.collection.return_value.document.assert_called_once()
