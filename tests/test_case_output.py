from actions.sar import build_sar, empty_sar, reconcile_file_report, should_file_sar
from case_memory.schema import ActionItem, CaseBody, CaseRecord, NextBestActions, SAR
from validation.validator import validate_case_record


def test_legitimate_rules_enforced():
    rec = CaseRecord(
        case_id="HHG-X",
        case=CaseBody(
            status="closed_legitimate",
            verdict="legitimate",
            fraud_probability=0.1,
            pattern="none",
            affected_txn_ids=[],
            exposure_usd=0,
            summary="cleared",
            written_to_graph=False,
        ),
        next_best_actions=NextBestActions(
            initial=[ActionItem(action="VERIFY_WITH_CUSTOMER", route="auto", reason="R1")],
            final=[ActionItem(action="CLOSE_NO_FRAUD", route="auto", reason="R3")],
            what_changed="customer confirmed",
        ),
        sar=empty_sar("legitimate"),
        stop_reason="verified",
        tool_calls=2,
        tokens=0,
        latency_s=0.2,
    )
    assert validate_case_record(rec.model_dump(mode="json")) == []


def test_sar_consistency():
    assert should_file_sar(
        verdict="fraud",
        fraud_probability=0.9,
        exposure_usd=1500,
        shared_origin=False,
        pattern="card_testing",
        coordinated_undocumented=False,
    )
    assert not should_file_sar(
        verdict="legitimate",
        fraud_probability=0.1,
        exposure_usd=5000,
        shared_origin=True,
        pattern="none",
        coordinated_undocumented=False,
    )
    sar = empty_sar("no")
    actions = [ActionItem(action="FILE_REPORT", route="L2", reason="R2")]
    actions, sar = reconcile_file_report(actions, sar, 2000)
    assert sar.file is True
    assert any(a.action == "FILE_REPORT" for a in actions)


def test_action_enums_match_spec():
    from validation.validator import ACTIONS

    expected = {
        "ALLOW_TRANSACTION",
        "DECLINE_TRANSACTION",
        "MONITOR_CARD",
        "MONITOR_CONNECTED_CARDS",
        "WARN_CUSTOMER",
        "VERIFY_WITH_CUSTOMER",
        "STEP_UP_AUTH",
        "BLOCK_CARD",
        "BLOCK_ALL_CARDS",
        "GENERATE_REPORT",
        "CREATE_CASE",
        "FILE_REPORT",
        "ESCALATE_TO_ANALYST",
        "CLOSE_NO_FRAUD",
    }
    assert ACTIONS == expected


def test_exposure_equals_amounts_in_sar():
    sar = build_sar(
        file=True,
        reason="R2",
        narrative="Who. What. When. Where. How. Why it is suspicious. Additional context. Final sentence.",
        subjects=["C1", "C1-K1"],
        total_amount_usd=12.34,
        activity_dates=["2016-11-01", "2016-11-01"],
    )
    rec = CaseRecord(
        case_id="HHG-X",
        case=CaseBody(
            status="closed_fraud",
            verdict="fraud",
            fraud_probability=0.9,
            pattern="card_testing",
            affected_txn_ids=["T1"],
            first_suspicious_txn_id="T1",
            exposure_usd=12.34,
            summary="fraud",
            written_to_graph=False,
        ),
        next_best_actions=NextBestActions(
            initial=[],
            final=[
                ActionItem(action="BLOCK_CARD", route="L1", reason="R2"),
                ActionItem(action="CREATE_CASE", route="auto", reason="R2"),
                ActionItem(action="FILE_REPORT", route="L2", reason="R2"),
            ],
            what_changed="nothing",
        ),
        sar=sar,
        stop_reason="done",
        tool_calls=1,
        tokens=0,
        latency_s=0.1,
    )
    errs = validate_case_record(rec.model_dump(mode="json"))
    assert errs == []
