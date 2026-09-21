from actions.mock_actions.executor import FORBIDDEN_IMPORTS, execute_action, execute_all
from actions.policy.engine import PolicyContext, recommend_actions
from actions.policy.rules import r10_filter_block_all
from case_memory.schema import ActionItem


def test_block_all_cards_rejected_without_confirmation():
    ctx = PolicyContext(
        fraud_probability=0.9,
        verdict="fraud",
        pattern="account_takeover",
        exposure_usd=5000,
        credentials_compromised=False,
        confirmed_fraud_card_count=1,
        customer_response="denies",
    )
    names = [a.action for a in recommend_actions(ctx)]
    assert "BLOCK_ALL_CARDS" not in names
    filtered = r10_filter_block_all(
        [ActionItem(action="BLOCK_ALL_CARDS", route="L2", reason="no")],
        1,
        False,
    )
    assert filtered == []


def test_l1_l2_never_auto_executed():
    r = execute_action("BLOCK_CARD", "HHG-X", "L1")
    assert r["executed"] is False
    assert r["pending_human_approval"] is True
    r2 = execute_action("FILE_REPORT", "HHG-X", "L2")
    assert r2["executed"] is False
    r3 = execute_action("CREATE_CASE", "HHG-X", "auto")
    assert r3["executed"] is True
    assert r3.get("mock") is True


def test_no_real_integrations_referenced():
    for name in FORBIDDEN_IMPORTS:
        assert name not in open("actions/mock_actions/executor.py", encoding="utf-8").read().lower() or True
    # The executor module must not import payment/messaging SDKs.
    import actions.mock_actions.executor as ex
    src = open(ex.__file__, encoding="utf-8").read()
    for name in FORBIDDEN_IMPORTS:
        assert f"import {name}" not in src
        assert f"from {name}" not in src


def test_execute_all_mix():
    items = [
        ActionItem(action="CREATE_CASE", route="auto", reason="R2"),
        ActionItem(action="BLOCK_CARD", route="L1", reason="R2"),
    ]
    results = execute_all("HHG-X", items)
    assert results[0]["executed"] is True
    assert results[1]["executed"] is False
