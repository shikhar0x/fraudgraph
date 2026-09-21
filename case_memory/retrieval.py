"""Retrieve similar prior ClosedCase records for a new investigation."""
from __future__ import annotations

from typing import Any

from graph.toolkit import GraphToolkit


def similar_closed_cases(
    toolkit: GraphToolkit,
    *,
    card_id: str,
    customer_id: str,
    device_id: str | None,
    pattern: str | None,
    query: str,
    limit: int = 5,
) -> list[str]:
    rows = toolkit.related_closed_cases(card_id, customer_id, device_id=device_id, pattern=pattern)
    if len(rows) < limit:
        extra = toolkit.search_closed_cases(query=query, pattern=pattern, limit=limit)
        seen = {r.get("case_id") for r in rows}
        for rec in extra:
            if rec.get("case_id") not in seen:
                rows.append(rec)
    ids = []
    for rec in rows:
        cid = rec.get("case_id") or ""
        if cid.startswith("CC-") and cid not in ids:
            ids.append(cid)
        if len(ids) >= limit:
            break
    return ids
