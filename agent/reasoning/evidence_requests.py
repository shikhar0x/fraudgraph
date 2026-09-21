"""Evidence-request selection and deterministic assumed-response simulation."""
from __future__ import annotations

from typing import Any

from case_memory.schema import EvidenceRequest


def choose_request(
    *,
    step: int,
    already: list[EvidenceRequest],
    trigger_type: str,
    single_signal: bool,
    fraud_probability: float,
    pattern: str,
    card_testing: bool,
    disputed_but_legitimate: bool,
    shared_origin: bool,
) -> EvidenceRequest | None:
    used = {r.type for r in already}
    if len(already) >= 2:
        return None
    if trigger_type == "analyst_request" and "analyst_info" not in used:
        return EvidenceRequest(type="analyst_info", asked_after_step=step, assumed_response="")
    if card_testing and "step_up_auth" not in used and fraud_probability >= 0.45:
        return EvidenceRequest(type="step_up_auth", asked_after_step=step, assumed_response="")
    if "customer_validation" not in used:
        if single_signal or disputed_but_legitimate or trigger_type == "customer_report" or fraud_probability < 0.85:
            return EvidenceRequest(type="customer_validation", asked_after_step=step, assumed_response="")
    if shared_origin and "analyst_info" not in used:
        return EvidenceRequest(type="analyst_info", asked_after_step=step, assumed_response="")
    return None


def simulate_response(
    req: EvidenceRequest,
    *,
    case_row: dict[str, Any],
    pattern: str,
    fraud_probability: float,
    recurring: bool,
    strong_pattern: bool,
) -> str:
    trigger = str(case_row.get("trigger_type") or "")
    if req.type == "customer_validation":
        if recurring:
            return "Customer confirms this is a recurring charge they recognize."
        if trigger == "customer_report":
            return "Customer reaffirms they did not authorize the flagged transaction and still have the card."
        if strong_pattern and fraud_probability >= 0.50:
            return "Customer states they did not make these purchases and still has the card."
        if fraud_probability < 0.45 or pattern == "none":
            return "Customer confirms they made the transaction."
        return "Customer states they did not make this purchase."
    if req.type == "step_up_auth":
        if strong_pattern or fraud_probability >= 0.60:
            return "Step-up authentication failed; no confirmation from the registered device."
        return "Step-up authentication succeeded; cardholder confirmed the session."
    # analyst_info
    card_id = case_row.get("card_id")
    return (
        f"Analyst notes: reviewed graph neighbourhood for {card_id}. "
        f"Working hypothesis is pattern={pattern}. "
        f"{'Related-card activity is flagged for monitoring.' if strong_pattern else 'No additional confirmed-fraud neighbours were documented in retrieved closed cases.'}"
    )


def interpret_customer_response(requests: list[EvidenceRequest]) -> str | None:
    for req in reversed(requests):
        text = (req.assumed_response or "").lower()
        if req.type == "customer_validation":
            if any(p in text for p in ("did not", "didn't", "not authorize", "not make", "reaffirms they did not")):
                return "denies"
            if any(p in text for p in ("confirm", "recognize", "made the transaction")):
                return "confirms"
        if req.type == "step_up_auth" and ("no confirmation" in text or "failed" in text or "no response" in text):
            return "no_reply"
    return None
