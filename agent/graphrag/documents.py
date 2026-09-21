"""Policy, typology, and regulatory guidance chunks for GraphRAG.

Text is taken from docs/fraud_policy.md (verbatim excerpts) and short internal
summaries of public SAR-writing requirements. We do not invent quotes from
PDFs that were not loaded.
"""
from __future__ import annotations

from typing import Any

POLICY_CHUNKS: list[dict[str, str]] = [
    {
        "chunk_id": "policy-r1",
        "title": "R1 Verify before you block on a weak signal",
        "kind": "policy",
        "body": (
            "R1. Verify before you block on a weak signal. If the case rests on a single signal "
            "(including a risk score alone) and your assessed fraud probability is below 0.70, "
            "recommend VERIFY_WITH_CUSTOMER or STEP_UP_AUTH before any block. Blocking a legitimate "
            "customer on one signal is a policy breach."
        ),
    },
    {
        "chunk_id": "policy-r2",
        "title": "R2 Customer denies the transaction",
        "kind": "policy",
        "body": (
            "R2. Customer denies the transaction. Recommend BLOCK_CARD and CREATE_CASE. Add FILE_REPORT "
            "if exposure exceeds $1,000 or the case connects to a shared device profile or another card's fraud."
        ),
    },
    {
        "chunk_id": "policy-r3",
        "title": "R3 Customer confirms the transaction",
        "kind": "policy",
        "body": "R3. Customer confirms the transaction. Recommend CLOSE_NO_FRAUD. Note the confirmation in the case file.",
    },
    {
        "chunk_id": "policy-r4",
        "title": "R4 No reply within 24 hours",
        "kind": "policy",
        "body": (
            "R4. No reply within 24 hours. Recommend MONITOR_CARD and DECLINE_TRANSACTION for pending "
            "authorizations. Escalate if exposure exceeds $500."
        ),
    },
    {
        "chunk_id": "policy-r5",
        "title": "R5 Card testing",
        "kind": "policy",
        "body": (
            "R5. Card testing. Three or more small online authorizations on one card within an hour, "
            "followed by a larger purchase: recommend DECLINE_TRANSACTION and STEP_UP_AUTH. If a purchase "
            "over $100 has already cleared, recommend BLOCK_CARD."
        ),
    },
    {
        "chunk_id": "policy-r6",
        "title": "R6 Shared origin",
        "kind": "policy",
        "body": (
            "R6. Shared origin. When several cards show fraud from the same device profile, the same billing "
            "region, or the same recipient email in one window, name the shared element, recommend CREATE_CASE "
            "and FILE_REPORT, and MONITOR_CONNECTED_CARDS for every card that shares it."
        ),
    },
    {
        "chunk_id": "policy-r7",
        "title": "R7 Disputed but legitimate",
        "kind": "policy",
        "body": (
            "R7. Disputed but legitimate. When the customer disputes a charge that matches their own recurring "
            "pattern (same merchant, same amount, monthly), recommend CREATE_CASE, VERIFY_WITH_CUSTOMER, and "
            "WARN_CUSTOMER. Do not block."
        ),
    },
    {
        "chunk_id": "policy-r8",
        "title": "R8 Escalate when uncertain and exposed",
        "kind": "policy",
        "body": (
            "R8. Escalate when uncertain and exposed. If the verdict is uncertain and exposure exceeds $500, "
            "or the evidence conflicts, recommend ESCALATE_TO_ANALYST."
        ),
    },
    {
        "chunk_id": "policy-r9",
        "title": "R9 Undocumented patterns",
        "kind": "policy",
        "body": (
            "R9. Undocumented patterns. When activity fits none of the known patterns but the evidence shows "
            "coordinated or repeated abuse across customers, recommend CREATE_CASE, FILE_REPORT, and "
            "ESCALATE_TO_ANALYST, and describe the pattern in your own words. Do not force it into a known category."
        ),
    },
    {
        "chunk_id": "policy-r10",
        "title": "R10 Never BLOCK_ALL_CARDS without confirmation",
        "kind": "policy",
        "body": (
            "R10. Never BLOCK_ALL_CARDS unless at least two of the customer's cards show confirmed fraud or "
            "the customer's credentials are confirmed compromised."
        ),
    },
    {
        "chunk_id": "policy-sar",
        "title": "3a Case vs report (SAR)",
        "kind": "policy",
        "body": (
            "A suspicious activity report (FILE_REPORT) is a regulatory filing. File one when fraud is confirmed "
            "or strongly suspected AND at least one of these holds: exposure exceeds $1,000; the activity connects "
            "to a shared device profile, a shared region cluster, or another customer's fraud; the pattern is "
            "coordinated or undocumented (rule R9). A report always has a case behind it. The narrative must stand "
            "on its own: who, what, when, where, how, and why."
        ),
    },
    {
        "chunk_id": "policy-stop",
        "title": "Stopping condition",
        "kind": "policy",
        "body": (
            "Stop investigating when fraud probability is at or above 0.85, or at or below 0.15, supported by at "
            "least two independent pieces of evidence; OR a verification response settles the question; OR further "
            "steps are unlikely to change the decision (state why in stop_reason)."
        ),
    },
    {
        "chunk_id": "policy-risk",
        "title": "Risk score is not a verdict",
        "kind": "policy",
        "body": (
            "Every transaction carries a risk_score between 0 and 1 from the bank's detection model. The model is "
            "useful and imperfect: many high scores are legitimate, and some fraud scores low. A score is a reason "
            "to look, never a verdict. The only confirmed outcomes are in the closed cases."
        ),
    },
]

TYPOLOGY_CHUNKS: list[dict[str, str]] = [
    {
        "chunk_id": "typology-card_testing",
        "title": "Card testing",
        "kind": "typology",
        "body": (
            "Card testing. A stolen card number is checked before use: three or more tiny online authorizations, "
            "often under $5, then a larger purchase. Confirmed by the sequence itself. Policy R5."
        ),
    },
    {
        "chunk_id": "typology-card_not_present_fraud",
        "title": "Card-not-present fraud",
        "kind": "typology",
        "body": (
            "Card-not-present fraud. The number is used online without the card. Amounts and products that don't fit "
            "the cardholder's history, often in a burst of two to four within 48 hours. On its own, one unusual "
            "online purchase is ambiguous: verify. Policy R1 to R4."
        ),
    },
    {
        "chunk_id": "typology-card_not_present_new_device",
        "title": "Card-not-present fraud from a new device",
        "kind": "typology",
        "body": (
            "Card-not-present fraud from a new device. Same as CNP, with the identity record marking the device as "
            "New for this account, sometimes behind a proxy. Stronger than pattern 2, still not proof: people buy new phones."
        ),
    },
    {
        "chunk_id": "typology-out_of_region_use",
        "title": "Out-of-region use",
        "kind": "typology",
        "body": (
            "Out-of-region use. Card-present purchases in a billing region the cardholder has no history in, while "
            "their normal activity continues at home. Several days of purchases in one new region is a trip, not a clone. "
            "Policy R2, R3."
        ),
    },
    {
        "chunk_id": "typology-account_takeover",
        "title": "Account takeover",
        "kind": "typology",
        "body": (
            "Account takeover. Mixed-channel activity inconsistent with the cardholder, often with device and "
            "match-flag anomalies, pointing to stolen credentials rather than a stolen number."
        ),
    },
    {
        "chunk_id": "typology-undocumented",
        "title": "Undocumented",
        "kind": "typology",
        "body": (
            "undocumented — activity the analysts confirmed as fraud but could not match to a known pattern. "
            "Noticing it, describing it in your own words, and recommending a defensible action is scored (R9)."
        ),
    },
]

REGULATORY_CHUNKS: list[dict[str, str]] = [
    {
        "chunk_id": "reg-sar-narrative",
        "title": "SAR narrative requirements (internal summary)",
        "kind": "regulatory",
        "body": (
            "Internal summary of public FinCEN SAR narrative guidance: a SAR narrative must stand on its own and "
            "answer who (subjects, accounts, devices), what (the suspicious activity), when (date range), where "
            "(locations, channels), how (method), and why the activity is suspicious. Six to twelve sentences. "
            "Do not rely on attachments to explain the activity."
        ),
    },
    {
        "chunk_id": "reg-sar-threshold",
        "title": "When to file (internal policy 3a)",
        "kind": "regulatory",
        "body": (
            "Under this bank's policy (not a substitute for BSA dollar thresholds), file when fraud is confirmed or "
            "strongly suspected and exposure exceeds $1,000, or the activity links to another customer via a shared "
            "device/region, or the pattern is coordinated/undocumented."
        ),
    },
]


def all_chunks() -> list[dict[str, str]]:
    return [*POLICY_CHUNKS, *TYPOLOGY_CHUNKS, *REGULATORY_CHUNKS]


def retrieve_chunks(query: str, kinds: list[str] | None = None, limit: int = 6) -> list[dict[str, str]]:
    tokens = {t.lower() for t in query.replace("|", " ").split() if len(t) > 2}
    scored: list[tuple[int, dict[str, str]]] = []
    for chunk in all_chunks():
        if kinds and chunk["kind"] not in kinds:
            continue
        blob = f"{chunk['title']} {chunk['body']}".lower()
        score = sum(1 for t in tokens if t in blob)
        if chunk["chunk_id"].split("-")[-1] in tokens:
            score += 3
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        base = [c for c in POLICY_CHUNKS if c["chunk_id"] in {"policy-risk", "policy-r1"}]
        return base[:limit]
    return [c for _, c in scored[:limit]]
