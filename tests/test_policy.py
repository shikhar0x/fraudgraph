from actions.policy import rules
from actions.policy.engine import PolicyContext, recommend_actions
from actions.policy.routing import route_for, validate_actions, RouteError
import pytest


def test_r1():
    acts = rules.r1_verify_before_block(0.4, True)
    assert acts and acts[0].action == "VERIFY_WITH_CUSTOMER"
    assert rules.r1_verify_before_block(0.8, True) is None
    assert rules.r1_verify_before_block(0.4, False) is None


def test_r2():
    acts = rules.r2_customer_denies(268.43, True)
    names = [a.action for a in acts]
    assert names[:2] == ["BLOCK_CARD", "CREATE_CASE"]
    assert "FILE_REPORT" in names
    assert next(a for a in acts if a.action == "BLOCK_CARD").route == "L1"
    high = rules.r2_customer_denies(3000, False)
    assert next(a for a in high if a.action == "BLOCK_CARD").route == "L2"
    assert any(a.action == "FILE_REPORT" for a in high)


def test_r3():
    acts = rules.r3_customer_confirms()
    assert acts[0].action == "CLOSE_NO_FRAUD"
    assert acts[0].route == "auto"


def test_r4():
    acts = rules.r4_no_reply(100, True)
    names = [a.action for a in acts]
    assert names == ["MONITOR_CARD", "DECLINE_TRANSACTION"]
    acts = rules.r4_no_reply(600, True)
    assert any(a.action == "ESCALATE_TO_ANALYST" for a in acts)


def test_r5():
    acts = rules.r5_card_testing(False)
    names = [a.action for a in acts]
    assert names == ["DECLINE_TRANSACTION", "STEP_UP_AUTH"]
    acts = rules.r5_card_testing(True, exposure_usd=200)
    assert any(a.action == "BLOCK_CARD" for a in acts)


def test_r6():
    acts = rules.r6_shared_origin("device")
    names = [a.action for a in acts]
    assert names == ["CREATE_CASE", "FILE_REPORT", "MONITOR_CONNECTED_CARDS"]
    assert "device" in acts[0].reason


def test_r7():
    acts = rules.r7_disputed_legitimate()
    names = [a.action for a in acts]
    assert names == ["CREATE_CASE", "VERIFY_WITH_CUSTOMER", "WARN_CUSTOMER"]
    assert "BLOCK_CARD" not in names


def test_r8():
    assert rules.r8_escalate_uncertain("uncertain", 600, False)
    assert rules.r8_escalate_uncertain("fraud", 100, True)
    assert rules.r8_escalate_uncertain("uncertain", 100, False) is None


def test_r9():
    names = [a.action for a in rules.r9_undocumented()]
    assert names == ["CREATE_CASE", "FILE_REPORT", "ESCALATE_TO_ANALYST"]


def test_r10():
    assert not rules.r10_block_all_allowed(1, False)
    assert rules.r10_block_all_allowed(2, False)
    assert rules.r10_block_all_allowed(0, True)
    from case_memory.schema import ActionItem

    blocked = [
        ActionItem(action="BLOCK_ALL_CARDS", route="L2", reason="x"),
        ActionItem(action="CREATE_CASE", route="auto", reason="x"),
    ]
    out = rules.r10_filter_block_all(blocked, 1, False)
    assert [a.action for a in out] == ["CREATE_CASE"]


def test_route_validation():
    assert route_for("VERIFY_WITH_CUSTOMER", 9999) == "auto"
    assert route_for("DECLINE_TRANSACTION", 10) == "L1"
    assert route_for("BLOCK_CARD", 100) == "L1"
    assert route_for("BLOCK_CARD", 2500) == "L1"
    assert route_for("BLOCK_CARD", 2500.01) == "L2"
    assert route_for("BLOCK_ALL_CARDS", 1) == "L2"
    assert route_for("FILE_REPORT", 1) == "L2"
    with pytest.raises(RouteError):
        validate_actions(
            [__import__("case_memory.schema", fromlist=["ActionItem"]).ActionItem(action="BLOCK_CARD", route="auto", reason="nope")],
            100,
        )


def test_engine_r7_never_blocks():
    ctx = PolicyContext(
        fraud_probability=0.4,
        verdict="uncertain",
        pattern="none",
        exposure_usd=40,
        disputed_but_legitimate=True,
        customer_response="denies",
        trigger_type="customer_report",
    )
    names = [a.action for a in recommend_actions(ctx)]
    assert "BLOCK_CARD" not in names
    assert "CREATE_CASE" in names
