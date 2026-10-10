from typing import Any, Dict, List, Literal, Optional, TypedDict

ConfidenceBand = Literal["likely", "probable", "unlikely"]

class EvidenceRef(TypedDict):
    evidence_id: str
    citation: str
    chunk_type: str
    text: str

class CandidateCause(TypedDict):
    cause: str
    confidence_band: ConfidenceBand
    status: str
    next_check: str
    evidence: List[EvidenceRef]
    sourced: bool

class NextCheck(TypedDict):
    check: Optional[str]
    reason: str
    evidence: List[EvidenceRef]

class DiagnosticResult(TypedDict):
    alarm_number: str
    candidate_causes: List[CandidateCause]
    next_check: NextCheck
    abstained: bool
    source: str
