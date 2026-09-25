"""LangGraph investigation state machine.

trigger → gather evidence → assess → confidence check → (request evidence → gather)
→ final decision → policy validation → mock actions → case memory → output
"""
from __future__ import annotations

import time
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from actions.mock_actions.executor import execute_all
from actions.policy.engine import PolicyContext, recommend_actions
from actions.sar import (
    activity_dates_from,
    build_sar,
    empty_sar,
    reconcile_file_report,
    should_file_sar,
)
from agent.graphrag.bundle import assemble_evidence_bundle
from agent.llm import generate_text, template_sar_narrative, template_summary
from agent.reasoning.assess import assess as run_assess, attach_history_amounts
from agent.reasoning.confidence import should_stop
from agent.reasoning.evidence_requests import choose_request, simulate_response
from agent.reasoning.state import InvestigationState
from case_memory.schema import (
    CaseBody,
    CaseRecord,
    EvidenceItem,
    EvidenceRequest,
    NextBestActions,
    SAR,
)
from case_memory.writer import persist_case
from graph.toolkit import GraphToolkit
from validation.validator import validate_case_record

MAX_STEPS = 3


def build_app(toolkit: GraphToolkit):
    def trigger(state: InvestigationState) -> dict[str, Any]:
        case_row = state["case_row"]
        txn = toolkit.get_transaction(str(case_row["flagged_txn_id"]))
        return {
            "flagged_txn": txn,
            "step": 0,
            "max_steps": MAX_STEPS,
            "evidence_requests": list(state.get("evidence_requests") or []),
            "initial_snapshot_taken": False,
            "tokens": 0,
            "mock_mode": toolkit.mock_mode,
        }

    def gather_evidence(state: InvestigationState) -> dict[str, Any]:
        bundle = assemble_evidence_bundle(state["case_row"], toolkit)
        history = toolkit.card_history(str(state["case_row"]["card_id"]), limit=200)
        attach_history_amounts(bundle.signals, history)
        facts = list(bundle.graph_facts)
        for req in state.get("evidence_requests") or []:
            if req.assumed_response:
                source = "customer" if req.type == "customer_validation" else "external"
                facts.append(
                    EvidenceItem(
                        claim=req.assumed_response,
                        source=source,
                        ref=f"evidence_request:{req.type}",
                        entity_ids=[],
                    )
                )
        return {
            "graph_facts": facts,
            "evidence": facts,
            "prior_cases": bundle.similar_prior_cases,
            "policy_context": bundle.policy_context,
            "typology_matches": bundle.typology_matches,
            "signals": bundle.signals,
            "tool_calls": toolkit.calls,
        }

    def assess_node(state: InvestigationState) -> dict[str, Any]:
        assessment = run_assess(
            state["case_row"],
            state.get("signals") or {},
            state.get("graph_facts") or [],
            state.get("evidence_requests") or [],
            state.get("prior_cases") or [],
        )
        ctx = _policy_ctx(state["case_row"], assessment, bool(state.get("evidence_requests")))
        actions = recommend_actions(ctx)
        out: dict[str, Any] = {
            "assessment": assessment,
            "pattern": assessment["pattern"],
            "pattern_description": assessment["pattern_description"],
            "fraud_probability": assessment["fraud_probability"],
            "verdict": assessment["verdict"],
            "uncertainty": assessment["verdict"] == "uncertain",
            "independent_count": assessment["independent_count"],
            "independent_evidence": assessment["independent_evidence"],
            "customer_response": assessment.get("customer_response"),
            "final_actions": actions,
        }
        if not state.get("initial_snapshot_taken"):
            out["initial_actions"] = actions
            out["initial_snapshot_taken"] = True
        return out

    def confidence_check(state: InvestigationState) -> dict[str, Any]:
        assessment = state["assessment"]
        requests = list(state.get("evidence_requests") or [])
        settled = assessment.get("customer_response") in {"confirms", "denies"} and state.get("step", 0) >= 1
        # First pass: a customer_report is not yet a completed verification loop.
        stop, reason = should_stop(
            fraud_probability=assessment["fraud_probability"],
            independent_count=assessment["independent_count"],
            verification_settled=settled,
            step=int(state.get("step") or 0),
            max_steps=int(state.get("max_steps") or MAX_STEPS),
            no_new_signals=int(state.get("step") or 0) >= 1,
        )
        req = None
        if not stop:
            req = choose_request(
                step=int(state.get("step") or 0),
                already=requests,
                trigger_type=str(state["case_row"].get("trigger_type") or ""),
                single_signal=bool(assessment.get("single_signal")),
                fraud_probability=assessment["fraud_probability"],
                pattern=assessment["pattern"],
                card_testing=bool(assessment.get("card_testing")),
                disputed_but_legitimate=bool(assessment.get("disputed_but_legitimate")),
                shared_origin=bool(assessment.get("shared_origin")),
            )
            if req is None:
                stop = True
                reason = reason or (
                    "Additional evidence is unlikely to change the decision: no remaining evidence-request types apply."
                )
        return {
            "stop_reason": reason,
            "need_more_evidence": bool(req is not None and not stop),
            "pending_request": req,
        }

    def request_evidence(state: InvestigationState) -> dict[str, Any]:
        req: EvidenceRequest | None = state.get("pending_request")
        assessment = state["assessment"]
        if req is None:
            req = choose_request(
                step=int(state.get("step") or 0),
                already=state.get("evidence_requests") or [],
                trigger_type=str(state["case_row"].get("trigger_type") or ""),
                single_signal=bool(assessment.get("single_signal")),
                fraud_probability=assessment["fraud_probability"],
                pattern=assessment["pattern"],
                card_testing=bool(assessment.get("card_testing")),
                disputed_but_legitimate=bool(assessment.get("disputed_but_legitimate")),
                shared_origin=bool(assessment.get("shared_origin")),
            )
        if req is None:
            return {"step": int(state.get("step") or 0) + 1}
        text = simulate_response(
            req,
            case_row=state["case_row"],
            pattern=assessment["pattern"],
            fraud_probability=assessment["fraud_probability"],
            recurring=bool(assessment.get("disputed_but_legitimate")),
            strong_pattern=assessment["pattern"] in {
                "card_testing",
                "account_takeover",
                "card_not_present_new_device",
                "undocumented",
            }
            or bool(assessment.get("card_testing")),
        )
        filled = EvidenceRequest(type=req.type, asked_after_step=int(state.get("step") or 0), assumed_response=text)
        requests = list(state.get("evidence_requests") or []) + [filled]
        return {
            "evidence_requests": requests,
            "assumed_responses": [r.assumed_response for r in requests],
            "step": int(state.get("step") or 0) + 1,
        }

    def final_decision(state: InvestigationState) -> dict[str, Any]:
        assessment = state["assessment"]
        initial = list(state.get("initial_actions") or [])
        final = list(state.get("final_actions") or [])
        what = _what_changed(initial, final, state.get("evidence_requests") or [])
        summary_fb = template_summary(assessment, state["case_row"])
        summary, tok_s = generate_text("summary", _summary_prompt(assessment, state["case_row"]), summary_fb)
        sar, tok_sar = _build_sar(state, assessment, final)
        final, sar = reconcile_file_report(final, sar, assessment["exposure_usd"])
        if assessment["verdict"] == "legitimate":
            sar = empty_sar(sar.reason or "legitimate verdict — no SAR")
            final = [a for a in final if a.action != "FILE_REPORT"]
            assessment = {
                **assessment,
                "affected_txn_ids": [],
                "first_suspicious_txn_id": "",
                "exposure_usd": 0.0,
            }
        status = _status(assessment["verdict"], final)
        return {
            "assessment": assessment,
            "summary": summary,
            "final_actions": final,
            "what_changed": what,
            "sar_required": bool(sar.file),
            "sar_object": sar,
            "tokens": int(state.get("tokens") or 0) + tok_s + tok_sar,
            "case_status": status,
        }

    def policy_validate(state: InvestigationState) -> dict[str, Any]:
        # Routes already assigned by recommend_actions. Re-run once more on the
        # frozen assessment so R10 cannot be bypassed.
        assessment = state["assessment"]
        ctx = _policy_ctx(state["case_row"], assessment, True)
        # Keep the post-evidence recommendation already computed; only filter R10/routes.
        from actions.policy.engine import _finalize

        final = _finalize(list(state.get("final_actions") or []), ctx, allow_block=not assessment.get("disputed_but_legitimate"))
        if assessment["verdict"] == "legitimate":
            from actions.policy.rules import r3_customer_confirms
            from actions.policy.routing import assign_routes

            kept = [a for a in final if a.action in {"CLOSE_NO_FRAUD", "GENERATE_REPORT", "WARN_CUSTOMER", "CREATE_CASE", "VERIFY_WITH_CUSTOMER"}]
            if not any(a.action == "CLOSE_NO_FRAUD" for a in kept):
                kept.extend(assign_routes(r3_customer_confirms(), 0.0))
            final = kept
        return {"final_actions": final}

    def execute_actions(state: InvestigationState) -> dict[str, Any]:
        results = execute_all(str(state["case_row"]["case_id"]), state.get("final_actions") or [])
        return {"execution_results": results}

    def persist_memory(state: InvestigationState) -> dict[str, Any]:
        record = _to_record(state, toolkit)
        written, graph_id = persist_case(toolkit, record, state["case_row"])
        record.case.written_to_graph = written
        record.case.graph_case_id = graph_id
        return {
            "graph_write_status": written,
            "graph_case_id": graph_id,
            "record": record.model_dump(mode="json"),
            "tool_calls": toolkit.calls,
        }

    def emit_output(state: InvestigationState) -> dict[str, Any]:
        return {"tool_calls": toolkit.calls}

    def route_after_confidence(state: InvestigationState) -> Literal["request_evidence", "final_decision"]:
        if state.get("need_more_evidence"):
            return "request_evidence"
        return "final_decision"

    builder = StateGraph(InvestigationState)
    builder.add_node("trigger", trigger)
    builder.add_node("gather_evidence", gather_evidence)
    builder.add_node("assess", assess_node)
    builder.add_node("confidence_check", confidence_check)
    builder.add_node("request_evidence", request_evidence)
    builder.add_node("final_decision", final_decision)
    builder.add_node("policy_validate", policy_validate)
    builder.add_node("execute_actions", execute_actions)
    builder.add_node("persist_memory", persist_memory)
    builder.add_node("emit_output", emit_output)
    builder.add_edge(START, "trigger")
    builder.add_edge("trigger", "gather_evidence")
    builder.add_edge("gather_evidence", "assess")
    builder.add_edge("assess", "confidence_check")
    builder.add_conditional_edges(
        "confidence_check",
        route_after_confidence,
        {"request_evidence": "request_evidence", "final_decision": "final_decision"},
    )
    builder.add_edge("request_evidence", "gather_evidence")
    builder.add_edge("final_decision", "policy_validate")
    builder.add_edge("policy_validate", "execute_actions")
    builder.add_edge("execute_actions", "persist_memory")
    builder.add_edge("persist_memory", "emit_output")
    builder.add_edge("emit_output", END)
    return builder.compile()


def run_investigation(case_row: dict[str, Any], toolkit: GraphToolkit) -> CaseRecord:
    t0 = time.perf_counter()
    app = build_app(toolkit)
    state = app.invoke({"case_row": case_row})
    latency = time.perf_counter() - t0
    raw = state.get("record")
    if not raw:
        raise RuntimeError("investigation produced no case record")
    raw["latency_s"] = round(latency, 3)
    raw["tool_calls"] = int(state.get("tool_calls") or toolkit.calls)
    raw["tokens"] = int(state.get("tokens") or 0)
    record = CaseRecord.model_validate(raw)
    problems = validate_case_record(record.model_dump(mode="json"), toolkit.known_ids())
    if problems:
        # Auto-repair only contract-level legitimate constraints we own.
        record = _repair(record, problems)
        problems = validate_case_record(record.model_dump(mode="json"), toolkit.known_ids())
        if problems:
            raise ValueError("case record failed validation: " + "; ".join(problems))
    return record


def _policy_ctx(case_row: dict[str, Any], assessment: dict[str, Any], evidence_requested: bool) -> PolicyContext:
    return PolicyContext(
        fraud_probability=assessment["fraud_probability"],
        verdict=assessment["verdict"],
        pattern=assessment["pattern"],
        pattern_description=assessment.get("pattern_description") or "",
        exposure_usd=float(assessment.get("exposure_usd") or 0.0),
        single_signal=bool(assessment.get("single_signal")),
        customer_response=assessment.get("customer_response"),
        shared_origin=assessment.get("shared_origin"),
        shared_origin_cards=list(assessment.get("connected_card_ids") or []),
        card_testing=bool(assessment.get("card_testing")),
        testing_large_cleared=bool(assessment.get("testing_large_cleared")),
        disputed_but_legitimate=bool(assessment.get("disputed_but_legitimate")),
        evidence_conflicts=bool(assessment.get("conflicts")),
        independent_evidence_count=int(assessment.get("independent_count") or 0),
        confirmed_fraud_card_count=0,
        credentials_compromised=bool(assessment.get("credentials_compromised")),
        evidence_requested=evidence_requested,
        pending_authorizations=True,
        coordinated_undocumented=bool(assessment.get("coordinated_undocumented")),
        prefer_step_up=assessment.get("pattern") in {"card_testing", "card_not_present_new_device"},
        trigger_type=str(case_row.get("trigger_type") or ""),
    )


def _status(verdict: str, actions) -> str:
    if any(getattr(a, "action", None) == "ESCALATE_TO_ANALYST" for a in actions) and verdict == "uncertain":
        return "escalated"
    if verdict == "fraud":
        return "closed_fraud"
    if verdict == "legitimate":
        return "closed_legitimate"
    return "escalated" if any(getattr(a, "action", None) == "ESCALATE_TO_ANALYST" for a in actions) else "open"


def _what_changed(initial, final, requests: list[EvidenceRequest]) -> str:
    i_set = [a.action for a in initial]
    f_set = [a.action for a in final]
    if i_set == f_set and not requests:
        return "nothing"
    if not requests:
        return "nothing"
    bits = [r.assumed_response for r in requests]
    return (
        "Evidence requests updated the recommendation. "
        + " ".join(bits)[:400]
        + f" Initial actions {i_set} became {f_set}."
    )


def _summary_prompt(assessment: dict[str, Any], case_row: dict[str, Any]) -> str:
    return (
        "Write 2-6 sentences for a fraud analyst summarizing this investigation. "
        f"Use only these facts: case_id={case_row['case_id']}, txn={case_row['flagged_txn_id']}, "
        f"card={case_row['card_id']}, verdict={assessment['verdict']}, p={assessment['fraud_probability']}, "
        f"pattern={assessment['pattern']}, exposure={assessment['exposure_usd']}. Do not invent IDs."
    )


def _build_sar(state: InvestigationState, assessment: dict[str, Any], final) -> tuple[SAR, int]:
    file_flag = should_file_sar(
        verdict=assessment["verdict"],
        fraud_probability=assessment["fraud_probability"],
        exposure_usd=float(assessment.get("exposure_usd") or 0),
        shared_origin=bool(assessment.get("shared_origin")),
        pattern=assessment.get("pattern") or "none",
        coordinated_undocumented=bool(assessment.get("coordinated_undocumented")),
    )
    if assessment["verdict"] == "legitimate":
        file_flag = False
    if not file_flag:
        reason = "Policy 3a: SAR not required (not confirmed/strong fraud with a filing trigger)."
        return empty_sar(reason), 0
    reason = "Policy 3a: confirmed or strongly suspected fraud meeting a filing criterion."
    txn = state.get("flagged_txn")
    dates = activity_dates_from(
        [txn] if txn else [],
        fallback=str(state["case_row"].get("opened_at") or ""),
    )
    narrative_fb = template_sar_narrative(
        case_row=state["case_row"],
        assessment=assessment,
        txn=txn,
        dates=dates,
    )
    narrative, tokens = generate_text("sar", narrative_fb, narrative_fb)
    subjects = [
        str(s)
        for s in [state["case_row"]["customer_id"], state["case_row"]["card_id"]]
        + list(assessment.get("connected_card_ids") or [])
        + list(assessment.get("connected_device_profiles") or [])
        if s
    ]
    subjects = list(dict.fromkeys(subjects))
    sar = build_sar(
        file=True,
        reason=reason,
        narrative=narrative,
        subjects=subjects,
        total_amount_usd=float(assessment.get("exposure_usd") or 0),
        activity_dates=dates or [str(state["case_row"].get("opened_at") or "")[:10]] * 2,
    )
    return sar, tokens


def _to_record(state: InvestigationState, toolkit: GraphToolkit) -> CaseRecord:
    assessment = state["assessment"]
    case_row = state["case_row"]
    sar: SAR = state.get("sar_object") or empty_sar(
        "Policy 3a: SAR not required (not confirmed/strong fraud with a filing trigger)."
    )  # type: ignore[assignment]
    initial = state.get("initial_actions") or []
    final = state.get("final_actions") or []
    if not initial:
        initial = final
    verdict = assessment["verdict"]
    body = CaseBody(
        status=state.get("case_status") or _status(verdict, final),
        verdict=verdict,
        fraud_probability=float(assessment["fraud_probability"]),
        pattern=assessment["pattern"],
        pattern_description=assessment.get("pattern_description") or "",
        affected_txn_ids=[] if verdict == "legitimate" else list(assessment.get("affected_txn_ids") or []),
        first_suspicious_txn_id="" if verdict == "legitimate" else (assessment.get("first_suspicious_txn_id") or ""),
        connected_card_ids=list(assessment.get("connected_card_ids") or []),
        connected_device_profiles=list(assessment.get("connected_device_profiles") or []),
        exposure_usd=0.0 if verdict == "legitimate" else float(assessment.get("exposure_usd") or 0.0),
        evidence=list(state.get("evidence") or []),
        similar_prior_cases=list(assessment.get("similar_prior_cases") or []),
        summary=state.get("summary") or template_summary(assessment, case_row),
        written_to_graph=bool(state.get("graph_write_status")),
        graph_case_id=str(state.get("graph_case_id") or ""),
    )
    return CaseRecord(
        case_id=str(case_row["case_id"]),
        case=body,
        evidence_requests=list(state.get("evidence_requests") or []),
        next_best_actions=NextBestActions(
            initial=initial,
            final=final,
            what_changed=state.get("what_changed") or "nothing",
        ),
        sar=sar,
        stop_reason=state.get("stop_reason") or "Investigation complete.",
        tool_calls=int(state.get("tool_calls") or toolkit.calls),
        tokens=int(state.get("tokens") or 0),
        latency_s=float(state.get("latency_s") or 0.0),
    )


def _repair(record: CaseRecord, problems: list[str]) -> CaseRecord:
    if record.case.verdict == "legitimate":
        record.case.affected_txn_ids = []
        record.case.exposure_usd = 0.0
        record.case.first_suspicious_txn_id = ""
        record.sar = empty_sar(record.sar.reason or "legitimate verdict — no SAR")
        record.next_best_actions.final = [
            a for a in record.next_best_actions.final if a.action != "FILE_REPORT"
        ]
    if record.case.pattern != "undocumented":
        record.case.pattern_description = ""
    if not record.sar.file:
        record.sar.narrative = ""
        record.sar.subjects = []
        record.sar.total_amount_usd = 0.0
        record.sar.activity_dates = []
        record.next_best_actions.final = [
            a for a in record.next_best_actions.final if a.action != "FILE_REPORT"
        ]
    return record
