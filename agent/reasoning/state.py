"""LangGraph investigation state."""
from __future__ import annotations

from typing import Any, TypedDict

from case_memory.schema import ActionItem, EvidenceItem, EvidenceRequest


class InvestigationState(TypedDict, total=False):
    case_row: dict[str, Any]
    flagged_txn: dict[str, Any] | None
    evidence: list[EvidenceItem]
    graph_facts: list[EvidenceItem]
    prior_cases: list[str]
    policy_context: list[str]
    typology_matches: list[str]
    signals: dict[str, Any]
    pattern: str
    pattern_description: str
    fraud_probability: float
    uncertainty: bool
    verdict: str
    independent_count: int
    independent_evidence: list[str]
    evidence_requests: list[EvidenceRequest]
    customer_response: str | None
    assumed_responses: list[str]
    initial_actions: list[ActionItem]
    final_actions: list[ActionItem]
    what_changed: str
    sar_required: bool
    summary: str
    stop_reason: str
    graph_write_status: bool
    graph_case_id: str
    tool_calls: int
    tokens: int
    latency_s: float
    step: int
    max_steps: int
    initial_snapshot_taken: bool
    assessment: dict[str, Any]
    execution_results: list[dict[str, Any]]
    record: dict[str, Any]
    mock_mode: bool
    need_more_evidence: bool
    pending_request: EvidenceRequest | None
    case_status: str
    sar_object: Any
