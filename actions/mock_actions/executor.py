"""
Mocked action execution. Nothing here calls a real API — everything is
logged/simulated per the challenge brief.
"""
import logging

logger = logging.getLogger("mock_actions")

def execute_action(action: str, case_id: str, route: str) -> dict:
    if route != "auto":
        logger.info(f"[{case_id}] {action} requires {route} approval — NOT executed, pending human.")
        return {"executed": False, "reason": f"awaiting {route} approval"}
    logger.info(f"[{case_id}] MOCK EXECUTED: {action}")
    return {"executed": True, "action": action}
