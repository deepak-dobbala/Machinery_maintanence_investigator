import unittest
from rag.diagnostic_engine import diagnose
from rag.diagnostic_session import DiagnosticSession

class DiagnosticRegressionTests(unittest.TestCase):
    def test_unknown_alarm_abstains(self):
        result = diagnose("999", [])
        self.assertTrue(result["abstained"])
        self.assertEqual(result["candidate_causes"], [])
        self.assertIsNone(result["next_check"]["check"])

    def test_irrelevant_evidence_abstains(self):
        evidence = [{"evidence_id": "E1", "citation": "Test manual, p. 1", "chunk_type": "troubleshooting", "text": "General machine maintenance information."}]
        result = diagnose("113", evidence)
        self.assertTrue(result["abstained"])
        self.assertEqual(result["candidate_causes"], [])
        self.assertIsNone(result["next_check"]["check"])

    def test_normal_shuttle_text_does_not_propose_jam(self):
        evidence = [{"evidence_id": "E1", "citation": "Test manual, p. 1", "chunk_type": "troubleshooting", "text": "The shuttle moves normally during the inspection."}]
        result = diagnose("113", evidence)
        self.assertTrue(result["abstained"])
        self.assertEqual(result["candidate_causes"], [])
        self.assertIsNone(result["next_check"]["check"])

    def test_bare_k9_reference_does_not_propose_electrical_fault(self):
        evidence = [{"evidence_id": "E1", "citation": "Test manual, p. 1", "chunk_type": "troubleshooting", "text": "The machine display shows K9 during normal operation."}]
        result = diagnose("113", evidence)
        self.assertTrue(result["abstained"])
        self.assertEqual(result["candidate_causes"], [])
        self.assertIsNone(result["next_check"]["check"])

    def test_alarm_113_proposes_candidates(self):
        evidence = [{"evidence_id": "E1", "citation": "Test manual, p. 1", "chunk_type": "alarm", "text": "Tool changer shuttle is jammed."}]
        result = diagnose("113", evidence)
        self.assertFalse(result["abstained"])
        self.assertTrue(result["candidate_causes"])
        self.assertTrue(result["next_check"]["check"])

    def test_alarm_122_proposes_candidates(self):
        evidence = [{"evidence_id": "E1", "citation": "Test manual, p. 1", "chunk_type": "alarm", "text": "Input line voltage too high."}]
        result = diagnose("122", evidence)
        self.assertFalse(result["abstained"])
        self.assertTrue(any(c["cause"] == "Input line voltage too high" for c in result["candidate_causes"]))
        self.assertEqual(result["next_check"]["check"], "Check the input line voltage.")

    def test_supporting_observation_does_not_confirm_cause(self):
        evidence = [
            {
                "evidence_id": "E1",
                "citation": "Test manual, p. 1",
                "chunk_type": "alarm",
                "text": "A loss of power to the tool changer can cause Alarm 113.",
            }
        ]

        session = DiagnosticSession(
            "113",
            "Alarm 113 Shuttle In Fault",
            evidence,
        )

        state = session.record_observation(
            "Tool changer power problem found."
        )

        electrical = next(
            c for c in state["candidate_causes"]
            if "electrical/power" in c["cause"]
        )

        self.assertEqual(electrical["status"], "supported")
        self.assertIsNone(state["confirmed_cause"])
        self.assertFalse(state["complete"])

    def test_ruling_out_jam_preserves_electrical_candidate(self):
        evidence = [
            {
                "evidence_id": "E1",
                "citation": "Test manual, p. 1",
                "chunk_type": "alarm",
                "text": (
                    "Alarm 113 can be caused by a jammed shuttle. "
                    "A loss of power to the tool changer can also cause this."
                ),
            }
        ]

        session = DiagnosticSession(
            "113",
            "Alarm 113 Shuttle In Fault",
            evidence,
        )

        state = session.record_observation(
            "No jam or obstruction was found."
        )

        mechanical = next(
            c for c in state["candidate_causes"]
            if "mechanical obstruction" in c["cause"]
        )
        electrical = next(
            c for c in state["candidate_causes"]
            if "electrical/power" in c["cause"]
        )

        self.assertEqual(mechanical["status"], "ruled_out")
        self.assertEqual(electrical["status"], "possible")
        self.assertIsNone(state["confirmed_cause"])
        self.assertIsNotNone(state["next_check"]["check"])

if __name__ == "__main__":
    unittest.m
