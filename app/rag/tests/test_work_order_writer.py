import pytest

from rag.work_order_writer import record_confirmed_work_order


def test_unconfirmed_diagnosis_is_rejected_before_firestore():
    with pytest.raises(ValueError, match="without explicit confirmation"):
        record_confirmed_work_order(
            alarm_code="123",
            machine_model="VF-series",
            symptom="Spindle drive alarm",
            diagnosis="Possible spindle-drive fault",
            action_taken="None recorded",
            confirmation_status="possible",
        )
