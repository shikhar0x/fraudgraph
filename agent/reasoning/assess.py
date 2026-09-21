"""Turn GraphRAG signals + evidence responses into a structured assessment."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from agent.reasoning.confidence import compute_probability
from agent.reasoning.evidence_requests import interpret_customer_response
from case_memory.schema import EvidenceItem, EvidenceRequest
from graph.local_store import parse_ts

KNOWN = {
    "card_testing",
    "card_not_present_fraud",
    "card_not_present_new_device",
    "out_of_region_use",
    "account_takeover",
}


def assess(
    case_row: dict[str, Any],
    bundle_signals: dict[str, Any],
    graph_facts: list[EvidenceItem],
    requests: list[EvidenceRequest],
    similar_prior_cases: list[str],
) -> dict[str, Any]:
    signals = dict(bundle_signals)
    if similar_prior_cases:
        # Only treat as similar-fraud if we actually retrieved confirmed-fraud notes.
        signals["similar_fraud"] = True

    responses = [{"type": r.type, "assumed_response": r.assumed_response} for r in requests]
    conf = compute_probability(signals, responses)
    customer_resp = interpret_customer_response(requests)
    trigger = str(case_row.get("trigger_type") or "")
    if customer_resp is None and trigger == "customer_report":
        # The trigger itself is a customer complaint, not yet a completed evidence request.
        customer_resp = None

    testing = signals.get("card_testing") or {}
    new_dev = signals.get("new_device_cnp") or {}
    cnp = signals.get("cnp") or {}
    oor = signals.get("out_of_region") or {}
    ato = signals.get("account_takeover") or {}
    shared = signals.get("shared_origin") or {}
    recurring = signals.get("recurring") or {}

    pattern = "none"
    pattern_description = ""
    ranked = [
        ("card_testing", testing),
        ("card_not_present_new_device", new_dev),
        ("account_takeover", ato),
        ("out_of_region_use", oor),
        ("card_not_present_fraud", cnp),
    ]
    matched = [(name, sig) for name, sig in ranked if sig.get("matched")]
    if len(matched) >= 2 and not testing.get("matched") and not ato.get("matched") and not oor.get("matched") and not cnp.get("matched") and not new_dev.get("matched"):
        pass
    if matched:
        pattern = matched[0][0]
    elif shared.get("matched") and (shared.get("connected_card_ids") or []):
        pattern = "undocumented"
        pattern_description = (
            f"Coordinated activity across {1 + len(shared.get('connected_card_ids') or [])} cards sharing "
            f"{shared.get('shared_element')} {shared.get('shared_value')}. The sequence does not match the five "
            f"documented typologies; it was found by traversing shared-origin neighbours of the flagged card."
        )

    p = conf["fraud_probability"]
    if customer_resp == "confirms" and not testing.get("matched"):
        p = min(p, 0.12)
        conf["fraud_probability"] = p
        pattern = "none"
        pattern_description = ""
    if recurring.get("matched") and trigger == "customer_report":
        # R7 path: dispute of a recurring charge.
        p = min(p, 0.22)
        conf["fraud_probability"] = p

    if customer_resp == "confirms" and not testing.get("matched"):
        verdict = "legitimate"
    elif recurring.get("matched") and trigger == "customer_report" and customer_resp in {None, "confirms"}:
        verdict = "legitimate" if customer_resp == "confirms" else "uncertain"
    elif customer_resp == "denies" and p >= 0.40:
        verdict = "fraud"
    elif p >= 0.70:
        verdict = "fraud"
    elif p <= 0.15 and conf["independent_count"] >= 2:
        verdict = "legitimate"
    else:
        verdict = "uncertain"

    if verdict == "legitimate":
        affected: list[str] = []
        first = ""
        exposure = 0.0
        connected_cards: list[str] = []
        devices: list[str] = []
    else:
        affected = _affected_ids(case_row, testing, cnp, new_dev, oor, ato)
        first = affected[0] if affected else ""
        exposure = _exposure(signals, affected)
        connected_cards = list(shared.get("connected_card_ids") or [])
        devices = []
        txn = signals.get("txn") or {}
        if txn.get("device_id"):
            devices.append(str(txn["device_id"]))
        if new_dev.get("device_id"):
            devices.append(str(new_dev["device_id"]))
        devices = list(dict.fromkeys(devices))

    if verdict != "fraud" and pattern == "undocumented":
        # undocumented is for confirmed/coordinated abuse
        if p < 0.55:
            pattern = "none"
            pattern_description = ""

    if pattern != "undocumented":
        pattern_description = ""

    return {
        "pattern": pattern,
        "pattern_description": pattern_description,
        "fraud_probability": p,
        "verdict": verdict,
        "independent_evidence": conf["independent_evidence"],
        "independent_count": conf["independent_count"],
        "contributions": conf["contributions"],
        "conflicts": conf["conflicts"],
        "single_signal": conf["single_signal"],
        "customer_response": customer_resp,
        "affected_txn_ids": affected,
        "first_suspicious_txn_id": first,
        "connected_card_ids": connected_cards,
        "connected_device_profiles": devices,
        "exposure_usd": exposure,
        "card_testing": bool(testing.get("matched")),
        "testing_large_cleared": bool(testing.get("large_cleared")),
        "shared_origin": shared.get("shared_element") if shared.get("matched") else None,
        "shared_origin_cards": connected_cards,
        "disputed_but_legitimate": bool(recurring.get("matched") and trigger == "customer_report"),
        "credentials_compromised": bool(ato.get("credentials_compromised_hint") and customer_resp == "denies"),
        "coordinated_undocumented": pattern == "undocumented",
        "calibrated": False,
        "evidence": graph_facts,
        "similar_prior_cases": similar_prior_cases,
    }


def _affected_ids(case_row: dict[str, Any], *matches: dict[str, Any]) -> list[str]:
    flagged = str(case_row["flagged_txn_id"])
    ids: list[str] = []
    for m in matches:
        if m.get("matched"):
            for tid in m.get("txn_ids") or []:
                if tid and tid not in ids:
                    ids.append(str(tid))
    if flagged not in ids:
        ids.insert(0, flagged)
    return ids


def _exposure(signals: dict[str, Any], affected: list[str]) -> float:
    by_id = dict(signals.get("history_by_id") or {})
    txn = signals.get("txn")
    if txn and txn.get("txn_id"):
        by_id[str(txn["txn_id"])] = txn
    # card history isn't always in signals as list of dicts with amounts
    total = 0.0
    known = 0
    for tid in affected:
        row = by_id.get(tid)
        if not row:
            continue
        if row.get("amount_known") is False:
            continue
        try:
            total += abs(float(row.get("amount") or 0.0))
            known += 1
        except (TypeError, ValueError):
            continue
    if known == 0:
        # Flagged amount from the transaction record if present.
        if txn:
            try:
                if txn.get("amount_known") is False:
                    return 0.0
                amt = abs(float(txn.get("amount") or 0.0))
                return round(amt, 2) if amt else 0.0
            except (TypeError, ValueError):
                return 0.0
        return 0.0
    return round(total, 2)


def attach_history_amounts(signals: dict[str, Any], history: list[dict[str, Any]]) -> None:
    txn_map = {str(h.get("txn_id")): h for h in history if h.get("txn_id")}
    signals["history_by_id"] = txn_map
