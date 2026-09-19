"""
Fraud policy rule engine — deterministic, per docs/fraud_policy.md.
The LLM proposes a verdict + evidence; this module decides the action
and route. Nothing here should be "ask the LLM to remember the rule."
"""
from case_memory.schema import ActionItem

def r1_verify_before_block(fraud_probability: float, single_signal: bool) -> list[ActionItem] | None:
    if single_signal and fraud_probability < 0.70:
        return [ActionItem(action="VERIFY_WITH_CUSTOMER", route="auto", reason="R1")]
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

# TODO (Day 1-2): r4_no_reply, r5_card_testing, r6_shared_origin,
# r7_disputed_legitimate, r8_escalate_uncertain, r9_undocumented, r10_never_block_all
# Each takes the minimal structured inputs it needs and returns list[ActionItem].
# Write a test per rule against a hand-constructed case before wiring into the agent loop.
