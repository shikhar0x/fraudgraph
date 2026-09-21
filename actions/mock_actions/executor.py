"""
Mocked action execution. Nothing here calls a real API — everything is
logged/simulated per the challenge brief.
"""
import logging

logger = logging.getLogger("mock_actions")

# Guard against accidental real integrations.
FORBIDDEN_IMPORTS = ("stripe", "twilio", "sendgrid", "braintree")


def execute_action(action: str, case_id: str, route: str) -> dict:
    if route != "auto":
        logger.info(f"[{case_id}] {action} requires {route} approval — NOT executed, pending human.")
        return {
            "executed": False,
            "reason": f"awaiting {route} approval",
            "action": action,
            "route": route,
            "pending_human_approval": True,
        }
    logger.info(f"[{case_id}] MOCK EXECUTED: {action}")
    return {
        "executed": True,
        "action": action,
        "route": "auto",
        "pending_human_approval": False,
        "mock": True,
    }


def execute_all(case_id: str, actions: list) -> list[dict]:
    results = []
    for item in actions:
        action = item.action if hasattr(item, "action") else item["action"]
        route = item.route if hasattr(item, "route") else item["route"]
        results.append(execute_action(action, case_id, route))
    return results
