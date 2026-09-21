from case_memory.schema import ActionItem, CaseBody, CaseRecord, NextBestActions, SAR
from validation.validator import validate_case_record


def test_rejects_route_mismatch():
    rec = CaseRecord(
        case_id="HHG-X",
        case=CaseBody(
            status="closed_fraud",
            verdict="fraud",
            fraud_probability=0.9,
            pattern="none",
            summary="x",
            written_to_graph=False,
            exposure_usd=100,
            affected_txn_ids=["T1"],
            first_suspicious_txn_id="T1",
        ),
        next_best_actions=NextBestActions(
            initial=[],
            final=[ActionItem(action="BLOCK_CARD", route="auto", reason="R2")],
            what_changed="nothing",
        ),
        sar=SAR(file=False, reason="no"),
        stop_reason="x",
        tool_calls=0,
        tokens=0,
        latency_s=0,
    )
    errs = validate_case_record(rec.model_dump(mode="json"))
    assert any("route" in e.lower() or "BLOCK_CARD" in e for e in errs)


def test_undocumented_requires_description():
    rec = CaseRecord(
        case_id="HHG-X",
        case=CaseBody(
            status="closed_fraud",
            verdict="fraud",
            fraud_probability=0.9,
            pattern="undocumented",
            pattern_description="",
            summary="x",
            written_to_graph=False,
            exposure_usd=10,
            affected_txn_ids=["T1"],
            first_suspicious_txn_id="T1",
        ),
        next_best_actions=NextBestActions(
            initial=[],
            final=[ActionItem(action="CREATE_CASE", route="auto", reason="R9")],
            what_changed="nothing",
        ),
        sar=SAR(file=False, reason="no"),
        stop_reason="x",
        tool_calls=0,
        tokens=0,
        latency_s=0,
    )
    errs = validate_case_record(rec.model_dump(mode="json"))
    assert any("pattern_description" in e for e in errs)
