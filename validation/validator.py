"""Strict validator for the dataset answer format."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from actions.policy.routing import RouteError, validate_route
from case_memory.schema import CaseRecord

ACTIONS = {
    "ALLOW_TRANSACTION",
    "DECLINE_TRANSACTION",
    "MONITOR_CARD",
    "MONITOR_CONNECTED_CARDS",
    "WARN_CUSTOMER",
    "VERIFY_WITH_CUSTOMER",
    "STEP_UP_AUTH",
    "BLOCK_CARD",
    "BLOCK_ALL_CARDS",
    "GENERATE_REPORT",
    "CREATE_CASE",
    "FILE_REPORT",
    "ESCALATE_TO_ANALYST",
    "CLOSE_NO_FRAUD",
}
ROUTES = {"auto", "L1", "L2"}
PATTERNS = {
    "card_testing",
    "card_not_present_fraud",
    "card_not_present_new_device",
    "out_of_region_use",
    "account_takeover",
    "undocumented",
    "none",
}
STATUSES = {"open", "closed_fraud", "closed_legitimate", "escalated"}
VERDICTS = {"fraud", "legitimate", "uncertain"}
SOURCES = {"graph", "document", "customer", "external"}
REQ_TYPES = {"customer_validation", "step_up_auth", "analyst_info"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_file(path: Path, known_ids: dict[str, set[str]] | None = None) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return validate_case_record(data, known_ids)


def validate_case_record(data: dict[str, Any], known_ids: dict[str, set[str]] | None = None) -> list[str]:
    errors: list[str] = []
    try:
        record = CaseRecord.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        return [f"schema: {exc}"]

    case = record.case
    if record.case_id == "":
        errors.append("case_id is empty")
    if case.status not in STATUSES:
        errors.append(f"invalid status {case.status}")
    if case.verdict not in VERDICTS:
        errors.append(f"invalid verdict {case.verdict}")
    if case.pattern not in PATTERNS:
        errors.append(f"invalid pattern {case.pattern}")
    if not (0.0 <= case.fraud_probability <= 1.0):
        errors.append("fraud_probability out of range")
    if case.pattern == "undocumented" and not case.pattern_description.strip():
        errors.append("pattern_description required when pattern is undocumented")
    if case.pattern != "undocumented" and case.pattern_description not in {"", None}:
        # Spec: required only when undocumented, else "".
        if case.pattern_description.strip():
            errors.append("pattern_description must be empty unless pattern is undocumented")

    if case.verdict == "legitimate":
        if case.affected_txn_ids:
            errors.append("legitimate verdict requires affected_txn_ids == []")
        if case.exposure_usd != 0:
            errors.append("legitimate verdict requires exposure_usd == 0")
        if record.sar.file:
            errors.append("legitimate verdict requires sar.file == false")

    file_report = any(a.action == "FILE_REPORT" for a in record.next_best_actions.final)
    if file_report != record.sar.file:
        errors.append("FILE_REPORT in final actions must agree with sar.file")

    if record.sar.file:
        if not record.sar.narrative.strip():
            errors.append("sar.narrative required when sar.file is true")
        sentences = [s for s in re.split(r"[.!?]+", record.sar.narrative) if s.strip()]
        if not (6 <= len(sentences) <= 14):
            errors.append(f"sar.narrative should be 6-12 sentences (counted {len(sentences)})")
        if not record.sar.subjects:
            errors.append("sar.subjects required when filing")
        if len(record.sar.activity_dates) != 2:
            errors.append("sar.activity_dates must be two YYYY-MM-DD strings when filing")
        for d in record.sar.activity_dates:
            if not DATE_RE.match(d):
                errors.append(f"bad activity date {d}")
        if abs(record.sar.total_amount_usd - case.exposure_usd) > 0.05:
            errors.append("sar.total_amount_usd must equal case.exposure_usd when filing")
    else:
        if record.sar.narrative != "":
            errors.append("sar.narrative must be empty when not filing")
        if record.sar.subjects:
            errors.append("sar.subjects must be [] when not filing")
        if record.sar.total_amount_usd != 0:
            errors.append("sar.total_amount_usd must be 0 when not filing")
        if record.sar.activity_dates:
            errors.append("sar.activity_dates must be [] when not filing")

    for bucket, items in (
        ("initial", record.next_best_actions.initial),
        ("final", record.next_best_actions.final),
    ):
        for item in items:
            if item.action not in ACTIONS:
                errors.append(f"invalid action {item.action} in {bucket}")
            if item.route not in ROUTES:
                errors.append(f"invalid route {item.route} in {bucket}")
            try:
                validate_route(item.action, item.route, case.exposure_usd)
            except RouteError as exc:
                errors.append(str(exc))
            if not item.reason:
                errors.append(f"action {item.action} missing reason")

    for ev in case.evidence:
        if ev.source not in SOURCES:
            errors.append(f"invalid evidence source {ev.source}")
        if not ev.claim:
            errors.append("evidence claim empty")

    for req in record.evidence_requests:
        if req.type not in REQ_TYPES:
            errors.append(f"invalid evidence request type {req.type}")
        if not req.assumed_response:
            errors.append("evidence request missing assumed_response")

    if known_ids:
        txn_ids = known_ids.get("txn") or set()
        card_ids = known_ids.get("card") or set()
        cust_ids = known_ids.get("customer") or set()
        closed = known_ids.get("closed_case") or set()
        devices = known_ids.get("device") or set()
        for tid in case.affected_txn_ids:
            if txn_ids and tid not in txn_ids:
                errors.append(f"unknown transaction id {tid}")
        if case.first_suspicious_txn_id:
            if case.first_suspicious_txn_id not in case.affected_txn_ids and case.verdict != "legitimate":
                errors.append("first_suspicious_txn_id must be in affected_txn_ids")
            if txn_ids and case.first_suspicious_txn_id not in txn_ids:
                errors.append(f"unknown first_suspicious_txn_id {case.first_suspicious_txn_id}")
        for cid in case.connected_card_ids:
            if card_ids and cid not in card_ids:
                errors.append(f"unknown card id {cid}")
        for did in case.connected_device_profiles:
            if devices and did not in devices:
                errors.append(f"unknown device id {did}")
        for cc in case.similar_prior_cases:
            if closed and cc not in closed:
                errors.append(f"similar_prior_cases id {cc} not in closed_cases_history")
            if not cc.startswith("CC-"):
                errors.append(f"similar_prior_cases should be ClosedCase ids, got {cc}")

    if record.tool_calls < 0 or record.tokens < 0 or record.latency_s < 0:
        errors.append("metrics must be non-negative")
    if not record.stop_reason:
        errors.append("stop_reason empty")
    return errors
