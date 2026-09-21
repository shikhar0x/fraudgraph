"""Deterministic action → route assignment and validation."""
from __future__ import annotations

from case_memory.schema import ActionItem

AUTO_ACTIONS = {
    "ALLOW_TRANSACTION",
    "MONITOR_CARD",
    "MONITOR_CONNECTED_CARDS",
    "WARN_CUSTOMER",
    "VERIFY_WITH_CUSTOMER",
    "STEP_UP_AUTH",
    "GENERATE_REPORT",
    "CREATE_CASE",
    "ESCALATE_TO_ANALYST",
    "CLOSE_NO_FRAUD",
}

ALL_ACTIONS = AUTO_ACTIONS | {
    "DECLINE_TRANSACTION",
    "BLOCK_CARD",
    "BLOCK_ALL_CARDS",
    "FILE_REPORT",
}


class RouteError(ValueError):
    pass


def route_for(action: str, exposure_usd: float) -> str:
    if action in AUTO_ACTIONS:
        return "auto"
    if action == "DECLINE_TRANSACTION":
        return "L1"
    if action == "BLOCK_CARD":
        return "L1" if exposure_usd <= 2500 else "L2"
    if action in {"BLOCK_ALL_CARDS", "FILE_REPORT"}:
        return "L2"
    raise RouteError(f"unknown action {action}")


def assign_routes(actions: list[ActionItem], exposure_usd: float) -> list[ActionItem]:
    out: list[ActionItem] = []
    for item in actions:
        out.append(ActionItem(action=item.action, route=route_for(item.action, exposure_usd), reason=item.reason))
    return out


def validate_route(action: str, route: str, exposure_usd: float) -> None:
    expected = route_for(action, exposure_usd)
    if route != expected:
        raise RouteError(f"{action} must use route {expected}, not {route} (exposure={exposure_usd})")


def validate_actions(actions: list[ActionItem], exposure_usd: float) -> None:
    for item in actions:
        if item.action not in ALL_ACTIONS:
            raise RouteError(f"invalid action {item.action}")
        validate_route(item.action, item.route, exposure_usd)
