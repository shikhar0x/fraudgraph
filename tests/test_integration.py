"""case input -> evidence -> agent -> policy -> case record (mocked graph)."""
from __future__ import annotations

from app.config import ROOT
from agent.graphrag.bundle import assemble_evidence_bundle
from agent.reasoning.graph import run_investigation
from graph.ingestion.pipeline import ingest
from graph.toolkit import GraphToolkit
from validation.validator import validate_case_record


def test_pipeline_card_testing(fixture_store):
    toolkit = GraphToolkit(fixture_store)
    row = fixture_store.case_pack["HHG-TEST-001"]
    rec = run_investigation(row, toolkit)
    payload = rec.model_dump(mode="json")
    errs = validate_case_record(payload, toolkit.known_ids())
    assert errs == [], errs
    assert rec.case.pattern == "card_testing"
    assert rec.tool_calls >= 1
    assert rec.next_best_actions.initial
    assert rec.next_best_actions.final
    assert rec.stop_reason


def test_pipeline_recurring_dispute(fixture_store):
    toolkit = GraphToolkit(fixture_store)
    row = fixture_store.case_pack["HHG-TEST-002"]
    rec = run_investigation(row, toolkit)
    errs = validate_case_record(rec.model_dump(mode="json"), toolkit.known_ids())
    assert errs == [], errs
    names = [a.action for a in rec.next_best_actions.final]
    assert "BLOCK_CARD" not in names
    assert rec.case.verdict in {"legitimate", "uncertain"}


def test_evidence_bundle_contract(fixture_store):
    toolkit = GraphToolkit(fixture_store)
    bundle = assemble_evidence_bundle(fixture_store.case_pack["HHG-TEST-001"], toolkit)
    assert bundle.case_id == "HHG-TEST-001"
    assert bundle.graph_facts
    assert "card_testing" in bundle.typology_matches
    for item in bundle.graph_facts:
        assert item.source in {"graph", "document", "customer", "external"}
        assert item.claim


def test_ingest_validates_headers(tmp_path):
    from graph.ingestion.pipeline import IngestError, _require_headers

    p = tmp_path / "x.csv"
    p.write_text("foo,bar\n1,2\n", encoding="utf-8")
    try:
        _require_headers(p, ["foo", "missing"])
        raise AssertionError("expected IngestError")
    except IngestError:
        pass
