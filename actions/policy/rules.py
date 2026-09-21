"""
Fraud policy rule engine — deterministic, per docs/fraud_policy.md.
The LLM proposes a verdict + evidence; this module decides the action
and route. Nothing here should be "ask the LLM to remember the rule."
"""
from case_memory.schema import ActionItem


def r1_verify_before_block(
    fraud_probability: float,
    single_signal: bool,
    prefer_step_up: bool = False,
) -> list[ActionItem] | None:
    if single_signal and fraud_probability < 0.70:
        action = "STEP_UP_AUTH" if prefer_step_up else "VERIFY_WITH_CUSTOMER"
        return [ActionItem(action=action, route="auto", reason="R1")]
    return None


def r2_customer_denies(exposure_usd: float, shared_device_or_linked_fraud: bool) -> list[ActionItem]:
    actions = [
        ActionItem(action="BLOCK_CARD", route="L1" if exposure_usd <= 2500 else "L2", reason="R2"),
        ActionItem(action="CREATE_CASE", route="auto", reason="R2"),
    ]
    if exposure_usd > 1000 or shared_device_or_linked_fraud:
        actions.append(ActionItem(action="FILE_REPORT", route="L2", reason="R2"))
    return actions


def r3_customer_confirms() -> list[ActionItem]:
    return [ActionItem(action="CLOSE_NO_FRAUD", route="auto", reason="R3")]


def r4_no_reply(exposure_usd: float, pending_authorizations: bool = True) -> list[ActionItem]:
    actions = [ActionItem(action="MONITOR_CARD", route="auto", reason="R4")]
    if pending_authorizations:
        actions.append(ActionItem(action="DECLINE_TRANSACTION", route="L1", reason="R4"))
    if exposure_usd > 500:
        actions.append(ActionItem(action="ESCALATE_TO_ANALYST", route="auto", reason="R4"))
    return actions


def r5_card_testing(purchase_over_100_cleared: bool, exposure_usd: float = 0.0) -> list[ActionItem]:
    actions = [
        ActionItem(action="DECLINE_TRANSACTION", route="L1", reason="R5"),
        ActionItem(action="STEP_UP_AUTH", route="auto", reason="R5"),
    ]
    if purchase_over_100_cleared:
        route = "L1" if exposure_usd <= 2500 else "L2"
        actions.append(ActionItem(action="BLOCK_CARD", route=route, reason="R5"))
    return actions


def r6_shared_origin(shared_element: str) -> list[ActionItem]:
    label = shared_element or "shared element"
    return [
        ActionItem(action="CREATE_CASE", route="auto", reason=f"R6: shared {label}"),
        ActionItem(action="FILE_REPORT", route="L2", reason=f"R6: shared {label}"),
        ActionItem(action="MONITOR_CONNECTED_CARDS", route="auto", reason=f"R6: shared {label}"),
    ]


def r7_disputed_legitimate() -> list[ActionItem]:
    return [
        ActionItem(action="CREATE_CASE", route="auto", reason="R7"),
        ActionItem(action="VERIFY_WITH_CUSTOMER", route="auto", reason="R7"),
        ActionItem(action="WARN_CUSTOMER", route="auto", reason="R7"),
    ]


def r8_escalate_uncertain(
    verdict: str,
    exposure_usd: float,
    evidence_conflicts: bool,
) -> list[ActionItem] | None:
    if (verdict == "uncertain" and exposure_usd > 500) or evidence_conflicts:
        return [ActionItem(action="ESCALATE_TO_ANALYST", route="auto", reason="R8")]
    return None


def r9_undocumented() -> list[ActionItem]:
    return [
        ActionItem(action="CREATE_CASE", route="auto", reason="R9"),
        ActionItem(action="FILE_REPORT", route="L2", reason="R9"),
        ActionItem(action="ESCALATE_TO_ANALYST", route="auto", reason="R9"),
    ]


def r10_block_all_allowed(confirmed_fraud_card_count: int, credentials_compromised: bool) -> bool:
    return confirmed_fraud_card_count >= 2 or credentials_compromised


def r10_filter_block_all(
    actions: list[ActionItem],
    confirmed_fraud_card_count: int,
    credentials_compromised: bool,
) -> list[ActionItem]:
    if r10_block_all_allowed(confirmed_fraud_card_count, credentials_compromised):
        return actions
    return [a for a in actions if a.action != "BLOCK_ALL_CARDS"]
