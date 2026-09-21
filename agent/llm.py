"""Optional LLM for summary / SAR prose. Deterministic templates otherwise."""
from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger("fraudgraph.llm")


def generate_text(kind: str, prompt: str, fallback: str) -> tuple[str, int]:
    """Return (text, token_estimate). Never used for verdicts or actions."""
    settings = get_settings()
    if not settings.llm_enabled:
        return fallback, _estimate_tokens(fallback)
    try:
        text = _call_llm(settings, prompt)
        if text.strip():
            return text.strip(), _estimate_tokens(prompt) + _estimate_tokens(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM %s failed (%s); using template", kind, exc)
    return fallback, _estimate_tokens(fallback)


def _call_llm(settings: Any, prompt: str) -> str:
    import httpx

    provider = settings.llm_provider
    model = settings.llm_model
    if provider == "groq":
        url = settings.llm_base_url or "https://api.groq.com/openai/v1/chat/completions"
        model = model or "llama-3.1-8b-instant"
    elif provider == "anthropic":
        url = settings.llm_base_url or "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": settings.llm_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model or "claude-3-haiku-20240307",
            "max_tokens": settings.llm_max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    else:
        url = settings.llm_base_url or "https://api.openai.com/v1/chat/completions"
        model = model or "gpt-4o-mini"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "max_tokens": settings.llm_max_tokens,
        "messages": [
            {"role": "system", "content": "You write concise bank-investigation prose. Do not invent IDs or amounts."},
            {"role": "user", "content": prompt},
        ],
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def template_summary(assessment: dict[str, Any], case_row: dict[str, Any]) -> str:
    txn_id = case_row["flagged_txn_id"]
    card_id = case_row["card_id"]
    verdict = assessment["verdict"]
    pattern = assessment["pattern"]
    p = assessment["fraud_probability"]
    n = assessment["independent_count"]
    if verdict == "legitimate":
        return (
            f"Investigation of {txn_id} on card {card_id} did not establish a fraud episode. "
            f"Assessed fraud probability is {p:.2f} from {n} independent evidence group(s). "
            f"Risk score was treated as a reason to look, not a verdict. "
            f"Recommended action is to close the alert as no fraud."
        )
    bits = [
        f"Investigation of flagged transaction {txn_id} on card {card_id} concludes {verdict} "
        f"(probability {p:.2f}, pattern {pattern})."
    ]
    if assessment.get("affected_txn_ids"):
        bits.append(f"Episode includes {len(assessment['affected_txn_ids'])} transaction(s), exposure ${assessment['exposure_usd']:.2f}.")
    if assessment.get("customer_response"):
        bits.append(f"Customer response interpreted as {assessment['customer_response']}.")
    if assessment.get("connected_card_ids"):
        bits.append(f"Connected cards: {', '.join(assessment['connected_card_ids'][:5])}.")
    bits.append("Actions follow the fraud policy rule engine, not the raw risk score.")
    return " ".join(bits)


def template_sar_narrative(
    *,
    case_row: dict[str, Any],
    assessment: dict[str, Any],
    txn: dict[str, Any] | None,
    dates: list[str],
) -> str:
    customer_id = case_row["customer_id"]
    card_id = case_row["card_id"]
    txn_id = case_row["flagged_txn_id"]
    opened = str(case_row.get("opened_at") or "")[:10]
    amount = assessment.get("exposure_usd") or 0.0
    pattern = assessment.get("pattern") or "none"
    channel = (txn or {}).get("channel") or "unknown"
    region = (txn or {}).get("addr1") or "unknown"
    who = f"Customer {customer_id} and card {card_id}"
    when = f"between {dates[0]} and {dates[-1]}" if dates else f"around {opened}"
    what = (
        f"the flagged transaction {txn_id} and {max(len(assessment.get('affected_txn_ids') or []) - 1, 0)} "
        f"related transaction(s) totaling ${amount:.2f}"
    )
    how = assessment.get("pattern_description") or f"activity consistent with {pattern.replace('_', ' ')}"
    denial = ""
    if assessment.get("customer_response") == "denies":
        denial = " The cardholder stated they did not authorize the activity and remained in possession of the card."
    s1 = f"{who} are the subjects of this report."
    s2 = f"On review of graph evidence, {what} were identified as the suspicious episode {when}."
    s3 = f"The activity occurred on the {channel} channel, billed in region {region}."
    s4 = f"How it was carried out: {how}."
    s5 = f"Why it is suspicious: assessed fraud probability {assessment['fraud_probability']:.2f} with pattern {pattern}."
    s6 = f"The investigation used graph neighbourhood queries and closed-case memory; the bank risk score was an input only.{denial}"
    s7 = "The bank is filing this report under the internal fraud policy (case plus regulatory report) because the activity is confirmed or strongly suspected and meets the filing criteria."
    s8 = "Recommended protective actions are recorded in the case file, including any card block pending the required approval route."
    return " ".join([s1, s2, s3, s4, s5, s6, s7, s8])
