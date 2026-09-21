"""Compose R1–R10 into a single deterministic recommendation."""
from __future__ import annotations

from dataclasses import dataclass, field

from actions.policy import rules
from actions.policy.routing import assign_routes, validate_actions
from case_memory.schema import ActionItem

ACTION_ORDER = [
    "VERIFY_WITH_CUSTOMER",
    "STEP_UP_AUTH",
    "DECLINE_TRANSACTION",
    "MONITOR_CARD",
    "MONITOR_CONNECTED_CARDS",
    "WARN_CUSTOMER",
    "ALLOW_TRANSACTION",
    "BLOCK_CARD",
    "BLOCK_ALL_CARDS",
    "CREATE_CASE",
    "GENERATE_REPORT",
    "FILE_REPORT",
    "ESCALATE_TO_ANALYST",
    "CLOSE_NO_FRAUD",
]
BLOCKING = {"BLOCK_CARD", "BLOCK_ALL_CARDS", "DECLINE_TRANSACTION"}


@dataclass
class PolicyContext:
    fraud_probability: float
    verdict: str
    pattern: str
    pattern_description: str = ""
    exposure_usd: float = 0.0
    single_signal: bool = True
    customer_response: str | None = None  # denies | confirms | no_reply | None
    shared_origin: str | None = None
    shared_origin_cards: list[str] = field(default_factory=list)
    card_testing: bool = False
    testing_large_cleared: bool = False
    disputed_but_legitimate: bool = False
    evidence_conflicts: bool = False
    independent_evidence_count: int = 0
    confirmed_fraud_card_count: int = 0
    credentials_compromised: bool = False
    evidence_requested: bool = False
    pending_authorizations: bool = True
    coordinated_undocumented: bool = False
    prefer_step_up: bool = False
    trigger_type: str = ""


def recommend_actions(ctx: PolicyContext) -> list[ActionItem]:
    actions: list[ActionItem] = []

    if ctx.disputed_but_legitimate:
        actions.extend(rules.r7_disputed_legitimate())
        extra = rules.r8_escalate_uncertain(ctx.verdict, ctx.exposure_usd, ctx.evidence_conflicts)
        if extra:
            actions.extend(extra)
        return _finalize(actions, ctx, allow_block=False)

    if ctx.customer_response == "confirms":
        actions.extend(rules.r3_customer_confirms())
        return _finalize(actions, ctx, allow_block=False)

    if ctx.customer_response == "no_reply":
        actions.extend(rules.r4_no_reply(ctx.exposure_usd, ctx.pending_authorizations))

    if ctx.card_testing:
        actions.extend(rules.r5_card_testing(ctx.testing_large_cleared, ctx.exposure_usd))

    if ctx.customer_response == "denies":
        linked = bool(ctx.shared_origin) or ctx.confirmed_fraud_card_count > 0
        actions.extend(rules.r2_customer_denies(ctx.exposure_usd, linked))

    if ctx.shared_origin and ctx.verdict == "fraud":
        actions.extend(rules.r6_shared_origin(ctx.shared_origin))

    if ctx.pattern == "undocumented" and ctx.coordinated_undocumented:
        actions.extend(rules.r9_undocumented())

    r1 = rules.r1_verify_before_block(ctx.fraud_probability, ctx.single_signal, ctx.prefer_step_up)
    # R2 (customer denies) is an explicit block rule — do not let R1 strip it.
    if r1 and ctx.customer_response != "denies":
        actions = [a for a in actions if a.action not in BLOCKING]
        actions.extend(r1)

    r8 = rules.r8_escalate_uncertain(ctx.verdict, ctx.exposure_usd, ctx.evidence_conflicts)
    if r8:
        actions.extend(r8)

    if ctx.verdict == "legitimate" and not any(a.action == "CLOSE_NO_FRAUD" for a in actions):
        actions.append(ActionItem(action="CLOSE_NO_FRAUD", route="auto", reason="R3" if ctx.customer_response == "confirms" else "no fraud episode identified"))

    if ctx.verdict == "fraud" and not any(a.action == "CREATE_CASE" for a in actions):
        actions.append(ActionItem(action="CREATE_CASE", route="auto", reason="policy 3a: fraud probability supports a case"))

    need_case = ctx.fraud_probability >= 0.30 or ctx.evidence_requested or ctx.trigger_type == "customer_report"
    if need_case and ctx.verdict != "legitimate" and not any(a.action == "CREATE_CASE" for a in actions):
        actions.append(ActionItem(action="CREATE_CASE", route="auto", reason="policy 3a: open a case"))

    if ctx.verdict == "uncertain" and not any(a.action in {"VERIFY_WITH_CUSTOMER", "STEP_UP_AUTH", "ESCALATE_TO_ANALYST"} for a in actions):
        actions.extend(
            r1
            or [ActionItem(action="VERIFY_WITH_CUSTOMER", route="auto", reason="R1")]
        )

    return _finalize(actions, ctx, allow_block=True)


def _finalize(actions: list[ActionItem], ctx: PolicyContext, allow_block: bool) -> list[ActionItem]:
    if not allow_block:
        actions = [a for a in actions if a.action not in BLOCKING]
    actions = rules.r10_filter_block_all(actions, ctx.confirmed_fraud_card_count, ctx.credentials_compromised)
    actions = _dedupe(actions)
    actions = assign_routes(actions, ctx.exposure_usd)
    actions = _sort(actions)
    validate_actions(actions, ctx.exposure_usd)
    return actions


def _dedupe(actions: list[ActionItem]) -> list[ActionItem]:
    seen: set[str] = set()
    out: list[ActionItem] = []
    for item in actions:
        if item.action in seen:
            continue
        seen.add(item.action)
        out.append(item)
    return out


def _sort(actions: list[ActionItem]) -> list[ActionItem]:
    rank = {name: i for i, name in enumerate(ACTION_ORDER)}
    return sorted(actions, key=lambda a: rank.get(a.action, 99))
