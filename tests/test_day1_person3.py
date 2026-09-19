"""
Day 1 exit test: prove the Case Record schema, Action Request schema,
and rule engine stubs actually validate together against one fake case.
Not testing correctness of policy logic yet — that's Day 2.
"""
from case_memory.schema import CaseRecord, CaseBody, NextBestActions, ActionItem, SAR
from actions.schema import ActionRequest
from actions.policy.rules import r2_customer_denies

def test_case_record_validates():
    body = CaseBody(
        status="closed_fraud", verdict="fraud", fraud_probability=0.86,
        pattern="card_testing", affected_txn_ids=["T0412877"], exposure_usd=268.43,
        summary="Test case for schema validation.", written_to_graph=True,
        graph_case_id="CASE-TEST-001",
    )
    final_actions = r2_customer_denies(exposure_usd=268.43, shared_device_or_linked_fraud=True)
    record = CaseRecord(
        case_id="HHG-TEST", case=body,
        next_best_actions=NextBestActions(initial=[], final=final_actions, what_changed="test"),
        sar=SAR(file=False, reason="test — no SAR needed"),
        stop_reason="test", tool_calls=0, tokens=0, latency_s=0.0,
    )
    assert record.case.pattern == "card_testing"
    assert any(a.action == "BLOCK_CARD" for a in record.next_best_actions.final)

def test_action_request_validates():
    req = ActionRequest(action="BLOCK_CARD", requires_approval=True, route="L1", justification="R2")
    assert req.route == "L1"
