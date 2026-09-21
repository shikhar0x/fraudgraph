"""Explicit, inspectable fraud-probability and stopping logic.

These weights are heuristic, not statistically calibrated.
"""
from __future__ import annotations

from typing import Any

PRIOR = 0.25
WEIGHTS = {
    "risk_score_scale": 0.18,
    "card_testing": 0.40,
    "cnp_burst": 0.18,
    "cnp_single": 0.08,
    "new_device": 0.12,
    "proxy": 0.08,
    "out_of_region": 0.28,
    "account_takeover": 0.28,
    "shared_origin": 0.22,
    "prior_fraud_similar": 0.12,
    "customer_denies": 0.30,
    "customer_confirms": -0.55,
    "recurring_legitimate": -0.40,
    "step_up_fail": 0.15,
    "step_up_success": -0.22,
    "analyst_supports": 0.08,
}


def compute_probability(signals: dict[str, Any], responses: list[dict[str, str]]) -> dict[str, Any]:
    score = PRIOR
    independent: list[str] = []
    contributions: dict[str, float] = {}

    txn = signals.get("txn") or {}
    try:
        risk = float(txn.get("risk_score") or 0.0)
    except (TypeError, ValueError):
        risk = 0.0
    risk_part = (risk - 0.5) * WEIGHTS["risk_score_scale"]
    score += risk_part
    contributions["risk_score"] = risk_part
    # Risk score is never an independent evidence piece by itself.

    def add(name: str, matched: bool, weight: float, independent_name: str | None = None) -> None:
        nonlocal score
        if not matched:
            contributions[name] = 0.0
            return
        score += weight
        contributions[name] = weight
        if independent_name:
            independent.append(independent_name)

    testing = signals.get("card_testing") or {}
    add("card_testing", bool(testing.get("matched")), WEIGHTS["card_testing"], "card_testing")

    cnp = signals.get("cnp") or {}
    if cnp.get("matched"):
        w = WEIGHTS["cnp_single"] if cnp.get("single_unusual") else WEIGHTS["cnp_burst"]
        add("cnp", True, w, "cnp")
    else:
        contributions["cnp"] = 0.0

    new_dev = signals.get("new_device_cnp") or {}
    add("new_device", bool(new_dev.get("is_new")), WEIGHTS["new_device"], "new_device")
    add("proxy", bool(new_dev.get("proxy")), WEIGHTS["proxy"], "proxy" if new_dev.get("proxy") else None)

    oor = signals.get("out_of_region") or {}
    add("out_of_region", bool(oor.get("matched")), WEIGHTS["out_of_region"] * float(oor.get("strength") or 1), "out_of_region")

    ato = signals.get("account_takeover") or {}
    add("account_takeover", bool(ato.get("matched")), WEIGHTS["account_takeover"] * float(ato.get("strength") or 1), "account_takeover")

    shared = signals.get("shared_origin") or {}
    add("shared_origin", bool(shared.get("matched")), WEIGHTS["shared_origin"], "shared_origin")

    recurring = signals.get("recurring") or {}
    add("recurring_legitimate", bool(recurring.get("matched")), WEIGHTS["recurring_legitimate"], "recurring")

    if signals.get("similar_fraud"):
        add("prior_fraud_similar", True, WEIGHTS["prior_fraud_similar"], "prior_case")

    for resp in responses:
        text = (resp.get("assumed_response") or "").lower()
        rtype = resp.get("type") or ""
        if rtype == "customer_validation":
            if _denies(text):
                add("customer_denies", True, WEIGHTS["customer_denies"], "customer")
            elif _confirms(text):
                add("customer_confirms", True, WEIGHTS["customer_confirms"], "customer")
        elif rtype == "step_up_auth":
            if "fail" in text or "no confirmation" in text or "no response" in text:
                add("step_up_fail", True, WEIGHTS["step_up_fail"], "step_up")
            elif "succeed" in text or "confirmed the session" in text:
                add("step_up_success", True, WEIGHTS["step_up_success"], "step_up")
        elif rtype == "analyst_info" and "related" in text:
            add("analyst_supports", True, WEIGHTS["analyst_supports"], "analyst")

    # Conflicting evidence pulls toward 0.5. Ignore the weak risk-score prior.
    pos = [k for k, v in contributions.items() if v > 0.05 and k != "risk_score"]
    neg = [k for k, v in contributions.items() if v < -0.05 and k != "risk_score"]
    conflicts = bool(pos and neg)
    if conflicts:
        score = 0.5 * score + 0.5 * 0.5
        contributions["conflict_shrink"] = 0.0

    score = max(0.02, min(0.98, score))
    unique_independent = list(dict.fromkeys([i for i in independent if i]))
    return {
        "fraud_probability": round(score, 4),
        "independent_evidence": unique_independent,
        "independent_count": len(unique_independent),
        "contributions": contributions,
        "conflicts": conflicts,
        "single_signal": len(unique_independent) <= 1,
        "calibrated": False,
    }


def _denies(text: str) -> bool:
    return any(p in text for p in ("did not", "didn't", "deny", "not make", "not authorize", "still has the card"))


def _confirms(text: str) -> bool:
    return any(p in text for p in ("confirm", "recognize", "i made", "they made", "authorized"))


def should_stop(
    *,
    fraud_probability: float,
    independent_count: int,
    verification_settled: bool,
    step: int,
    max_steps: int,
    no_new_signals: bool,
) -> tuple[bool, str]:
    if verification_settled:
        return True, "A verification response settled the question."
    if fraud_probability >= 0.85 and independent_count >= 2:
        return True, "Fraud probability >= 0.85 with at least 2 independent evidence pieces."
    if fraud_probability <= 0.15 and independent_count >= 2:
        return True, "Fraud probability <= 0.15 with at least 2 independent evidence pieces."
    if no_new_signals and step >= 1:
        return True, "Additional evidence is unlikely to change the decision: remaining graph queries repeat cached facts."
    if step >= max_steps:
        return True, "Further steps are unlikely to change the decision; investigation step budget reached."
    return False, ""
