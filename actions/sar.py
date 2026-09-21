"""Policy-driven SAR generation. FILE_REPORT and sar.file must agree."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from case_memory.schema import ActionItem, SAR


def should_file_sar(
    *,
    verdict: str,
    fraud_probability: float,
    exposure_usd: float,
    shared_origin: bool,
    pattern: str,
    coordinated_undocumented: bool,
) -> bool:
    if verdict == "legitimate":
        return False
    strong = verdict == "fraud" or fraud_probability >= 0.75
    if not strong:
        return False
    if exposure_usd > 1000:
        return True
    if shared_origin:
        return True
    if pattern == "undocumented" or coordinated_undocumented:
        return True
    return False


def empty_sar(reason: str) -> SAR:
    return SAR(file=False, reason=reason, narrative="", subjects=[], total_amount_usd=0.0, activity_dates=[])


def build_sar(
    *,
    file: bool,
    reason: str,
    narrative: str,
    subjects: list[str],
    total_amount_usd: float,
    activity_dates: list[str],
) -> SAR:
    if not file:
        return empty_sar(reason)
    dates = activity_dates
    if len(dates) == 1:
        dates = [dates[0], dates[0]]
    if len(dates) > 2:
        dates = [dates[0], dates[-1]]
    return SAR(
        file=True,
        reason=reason,
        narrative=narrative.strip(),
        subjects=list(dict.fromkeys(subjects)),
        total_amount_usd=round(float(total_amount_usd), 2),
        activity_dates=dates,
    )


def reconcile_file_report(actions: list[ActionItem], sar: SAR, exposure_usd: float) -> tuple[list[ActionItem], SAR]:
    has_file = any(a.action == "FILE_REPORT" for a in actions)
    if sar.file and not has_file:
        from actions.policy.routing import route_for

        actions = list(actions) + [
            ActionItem(action="FILE_REPORT", route=route_for("FILE_REPORT", exposure_usd), reason=sar.reason or "policy 3a")
        ]
    if has_file and not sar.file:
        sar = SAR(
            file=True,
            reason=next(a.reason for a in actions if a.action == "FILE_REPORT"),
            narrative=sar.narrative,
            subjects=sar.subjects,
            total_amount_usd=sar.total_amount_usd,
            activity_dates=sar.activity_dates,
        )
    if not sar.file:
        sar = empty_sar(sar.reason)
        actions = [a for a in actions if a.action != "FILE_REPORT"]
    return actions, sar


def activity_dates_from(txns: list[dict[str, Any]], fallback: str | None = None) -> list[str]:
    dates: list[str] = []
    for t in txns:
        ts = t.get("ts")
        if isinstance(ts, datetime):
            dates.append(ts.strftime("%Y-%m-%d"))
        elif isinstance(ts, str) and len(ts) >= 10:
            dates.append(ts[:10])
    dates = [d for d in dates if d]
    if not dates and fallback:
        dates = [fallback[:10]]
    if not dates:
        return []
    dates.sort()
    return [dates[0], dates[-1]]
