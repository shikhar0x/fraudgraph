"""
Case Record schema — matches docs/architecture.md Section 4.2 exactly.
This is the submitted output shape. Field names/enums are locked to the
dataset README's Answer Format — do not rename or restructure without
updating architecture.md and telling the other two.
"""
from pydantic import BaseModel
from typing import Literal

ACTIONS = Literal[
    "ALLOW_TRANSACTION", "DECLINE_TRANSACTION", "MONITOR_CARD",
    "MONITOR_CONNECTED_CARDS", "WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER",
    "STEP_UP_AUTH", "BLOCK_CARD", "BLOCK_ALL_CARDS", "GENERATE_REPORT",
    "CREATE_CASE", "FILE_REPORT", "ESCALATE_TO_ANALYST", "CLOSE_NO_FRAUD",
]
ROUTES = Literal["auto", "L1", "L2"]
PATTERNS = Literal[
    "card_testing", "card_not_present_fraud", "card_not_present_new_device",
    "out_of_region_use", "account_takeover", "undocumented", "none",
]

class EvidenceItem(BaseModel):
    claim: str
    source: Literal["graph", "document", "customer", "external"]
    ref: str
    entity_ids: list[str]

class CaseBody(BaseModel):
    status: Literal["open", "closed_fraud", "closed_legitimate", "escalated"]
    verdict: Literal["fraud", "legitimate", "uncertain"]
    fraud_probability: float
    pattern: PATTERNS
    pattern_description: str = ""
    affected_txn_ids: list[str] = []
    first_suspicious_txn_id: str = ""
    connected_card_ids: list[str] = []
    connected_device_profiles: list[str] = []
    exposure_usd: float = 0.0
    evidence: list[EvidenceItem] = []
    similar_prior_cases: list[str] = []
    summary: str
    written_to_graph: bool
    graph_case_id: str = ""

class ActionItem(BaseModel):
    action: ACTIONS
    route: ROUTES
    reason: str  # must cite a policy rule, e.g. "R5"

class NextBestActions(BaseModel):
    initial: list[ActionItem]
    final: list[ActionItem]
    what_changed: str

class EvidenceRequest(BaseModel):
    type: Literal["customer_validation", "step_up_auth", "analyst_info"]
    asked_after_step: int
    assumed_response: str

class SAR(BaseModel):
    file: bool
    reason: str
    narrative: str = ""
    subjects: list[str] = []
    total_amount_usd: float = 0.0
    activity_dates: list[str] = []

class CaseRecord(BaseModel):
    case_id: str
    case: CaseBody
    evidence_requests: list[EvidenceRequest] = []
    next_best_actions: NextBestActions
    sar: SAR
    stop_reason: str
    tool_calls: int
    tokens: int
    latency_s: float
