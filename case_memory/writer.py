"""Write completed investigations back to the graph provider."""
from __future__ import annotations

from typing import Any

from case_memory.schema import CaseRecord
from graph.toolkit import GraphToolkit


def persist_case(toolkit: GraphToolkit, record: CaseRecord, case_row: dict[str, Any]) -> tuple[bool, str]:
    graph_id = f"CASE-{record.case_id}"
    payload = {
        "case_id": record.case_id,
        "graph_case_id": graph_id,
        "customer_id": case_row.get("customer_id") or "",
        "card_id": case_row.get("card_id") or "",
        "flagged_txn_id": case_row.get("flagged_txn_id") or "",
        "status": record.case.status,
        "verdict": record.case.verdict,
        "fraud_probability": record.case.fraud_probability,
        "pattern": record.case.pattern,
        "pattern_description": record.case.pattern_description,
        "exposure_usd": record.case.exposure_usd,
        "summary": record.case.summary,
        "sar_filed": record.sar.file,
        "affected_txn_ids": record.case.affected_txn_ids,
        "connected_card_ids": record.case.connected_card_ids,
        "connected_device_profiles": record.case.connected_device_profiles,
        "similar_prior_cases": record.case.similar_prior_cases,
    }
    written_id = toolkit.write_case(payload)
    # Spec: written_to_graph is whether the case was stored in TigerGraph.
    live = not toolkit.mock_mode and bool(written_id)
    return live, written_id if live else (written_id if written_id and not toolkit.mock_mode else "")
