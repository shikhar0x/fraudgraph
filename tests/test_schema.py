from case_memory.schema import CaseBody, CaseRecord, NextBestActions, ActionItem, SAR, EvidenceRequest, EvidenceItem
from actions.schema import ActionRequest
import pytest
from pydantic import ValidationError


def _record(**kwargs) -> CaseRecord:
    body = CaseBody(
        status="closed_fraud",
        verdict="fraud",
        fraud_probability=0.86,
        pattern="card_testing",
        affected_txn_ids=["T1"],
        exposure_usd=10.0,
        summary="ok",
        written_to_graph=False,
    )
    rec = CaseRecord(
        case_id="HHG-TEST",
        case=body,
        next_best_actions=NextBestActions(
            initial=[ActionItem(action="VERIFY_WITH_CUSTOMER", route="auto", reason="R1")],
            final=[ActionItem(action="BLOCK_CARD", route="L1", reason="R2")],
            what_changed="denied",
        ),
        sar=SAR(file=False, reason="no"),
        stop_reason="done",
        tool_calls=1,
        tokens=0,
        latency_s=0.1,
    )
    return rec.model_copy(update=kwargs) if kwargs else rec


def test_valid_case_record():
    rec = _record()
    assert rec.case.pattern == "card_testing"


def test_invalid_action():
    with pytest.raises(ValidationError):
        ActionItem(action="FREEZE_THE_MOON", route="auto", reason="x")


def test_invalid_route():
    with pytest.raises(ValidationError):
        ActionItem(action="BLOCK_CARD", route="L3", reason="x")


def test_invalid_pattern():
    with pytest.raises(ValidationError):
        CaseBody(
            status="open",
            verdict="fraud",
            fraud_probability=0.5,
            pattern="skimming",
            summary="x",
            written_to_graph=False,
        )


def test_malformed_evidence_request():
    with pytest.raises(ValidationError):
        EvidenceRequest(type="phone_call", asked_after_step=1, assumed_response="hi")


def test_malformed_sar():
    with pytest.raises(ValidationError):
        SAR(reason="x")  # file is required


def test_action_request_validates():
    req = ActionRequest(action="BLOCK_CARD", requires_approval=True, route="L1", justification="R2")
    assert req.route == "L1"


def test_evidence_item_source():
    with pytest.raises(ValidationError):
        EvidenceItem(claim="x", source="dream", ref="y", entity_ids=[])
