"""GraphRAG evidence bundle — architecture.md section 4.1."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agent.graphrag.documents import retrieve_chunks
from case_memory.schema import EvidenceItem
from graph.toolkit import GraphToolkit

PATTERN_ENUM = [
    "card_testing",
    "card_not_present_fraud",
    "card_not_present_new_device",
    "out_of_region_use",
    "account_takeover",
    "undocumented",
    "none",
]


class EvidenceBundle(BaseModel):
    case_id: str
    flagged_txn_id: str
    graph_facts: list[EvidenceItem] = Field(default_factory=list)
    policy_context: list[str] = Field(default_factory=list)
    typology_matches: list[str] = Field(default_factory=list)
    similar_prior_cases: list[str] = Field(default_factory=list)
    signals: dict[str, Any] = Field(default_factory=dict)


def assemble_evidence_bundle(
    case_row: dict[str, Any],
    toolkit: GraphToolkit,
) -> EvidenceBundle:
    case_id = str(case_row["case_id"])
    txn_id = str(case_row["flagged_txn_id"])
    card_id = str(case_row["card_id"])
    customer_id = str(case_row["customer_id"])
    facts: list[EvidenceItem] = []
    signals: dict[str, Any] = {}

    facts.append(
        EvidenceItem(
            claim=f"Alert {case_id} trigger_type={case_row.get('trigger_type')}: {case_row.get('trigger_text')}",
            source="external",
            ref="case_pack.csv",
            entity_ids=[txn_id, card_id, customer_id],
        )
    )

    txn = toolkit.get_transaction(txn_id)
    if txn:
        amount = txn.get("amount")
        amt_s = f"${float(amount):.2f}" if amount not in (None, "") else "unknown amount"
        facts.append(
            EvidenceItem(
                claim=(
                    f"Flagged transaction {txn_id} {amt_s}, channel={txn.get('channel') or 'unknown'}, "
                    f"risk_score={txn.get('risk_score')}, billing_region={txn.get('addr1') or 'unknown'}"
                ),
                source="graph",
                ref=f"query:get_transaction(txn_id={txn_id})",
                entity_ids=[txn_id],
            )
        )
        signals["txn"] = txn

    history = toolkit.card_history(card_id, limit=200)
    signals["card_history_n"] = len(history)
    if len(history) > 1:
        facts.append(
            EvidenceItem(
                claim=f"Card {card_id} has {len(history)} indexed transactions in the graph",
                source="graph",
                ref=f"query:card_history(card_id={card_id})",
                entity_ids=[card_id] + [str(h.get("txn_id")) for h in history[:8] if h.get("txn_id")],
            )
        )

    window = toolkit.transaction_window(txn_id, hours=24.0)
    if window:
        facts.append(
            EvidenceItem(
                claim=f"{len(window)} transaction(s) on the same card within a 24h window of {txn_id}",
                source="graph",
                ref=f"query:card_window(card_id={card_id}, hours=24)",
                entity_ids=[str(w.get("txn_id")) for w in window if w.get("txn_id")],
            )
        )

    testing = toolkit.detect_card_testing(card_id, around_txn_id=txn_id)
    signals["card_testing"] = testing
    if testing.get("matched"):
        facts.append(
            EvidenceItem(
                claim=testing["details"],
                source="graph",
                ref=f"query:detect_card_testing(card_id={card_id})",
                entity_ids=list(testing.get("entity_ids") or []),
            )
        )

    cnp = toolkit.detect_cnp(card_id, around_txn_id=txn_id)
    signals["cnp"] = cnp
    if cnp.get("matched"):
        facts.append(
            EvidenceItem(
                claim=cnp["details"],
                source="graph",
                ref=f"query:detect_cnp(card_id={card_id})",
                entity_ids=list(cnp.get("entity_ids") or []),
            )
        )

    new_dev = toolkit.detect_new_device_cnp(card_id, around_txn_id=txn_id)
    signals["new_device_cnp"] = new_dev
    if new_dev.get("matched"):
        facts.append(
            EvidenceItem(
                claim=new_dev["details"],
                source="graph",
                ref=f"query:detect_new_device_cnp(card_id={card_id})",
                entity_ids=list(new_dev.get("entity_ids") or []),
            )
        )

    oor = toolkit.detect_out_of_region(card_id, around_txn_id=txn_id)
    signals["out_of_region"] = oor
    if oor.get("matched"):
        facts.append(
            EvidenceItem(
                claim=oor["details"],
                source="graph",
                ref=f"query:detect_out_of_region(card_id={card_id})",
                entity_ids=list(oor.get("entity_ids") or []),
            )
        )

    ato = toolkit.detect_account_takeover(card_id, around_txn_id=txn_id)
    signals["account_takeover"] = ato
    if ato.get("matched"):
        facts.append(
            EvidenceItem(
                claim=ato["details"],
                source="graph",
                ref=f"query:detect_account_takeover(card_id={card_id})",
                entity_ids=list(ato.get("entity_ids") or []),
            )
        )

    shared = toolkit.detect_shared_origin(card_id, around_txn_id=txn_id)
    signals["shared_origin"] = shared
    if shared.get("matched"):
        facts.append(
            EvidenceItem(
                claim=shared["details"],
                source="graph",
                ref=f"query:detect_shared_origin(card_id={card_id})",
                entity_ids=list(shared.get("entity_ids") or []),
            )
        )

    recurring = toolkit.detect_recurring(card_id, around_txn_id=txn_id)
    signals["recurring"] = recurring
    if recurring.get("matched"):
        facts.append(
            EvidenceItem(
                claim=recurring["details"],
                source="graph",
                ref=f"query:detect_recurring(card_id={card_id})",
                entity_ids=list(recurring.get("entity_ids") or []),
            )
        )

    device_id = ""
    if txn:
        device_id = str(txn.get("device_id") or "")
    if device_id:
        neigh = toolkit.device_neighbors(device_id)
        signals["device_neighbors"] = neigh
        cards = neigh.get("cards") or []
        if cards:
            facts.append(
                EvidenceItem(
                    claim=f"Device profile seen on {len(cards)} card(s)",
                    source="graph",
                    ref=f"query:device_neighbors(device_id={device_id})",
                    entity_ids=[device_id] + list(cards)[:12],
                )
            )

    typology: list[str] = []
    if testing.get("matched"):
        typology.append("card_testing")
    if new_dev.get("matched"):
        typology.append("card_not_present_new_device")
    elif cnp.get("matched"):
        typology.append("card_not_present_fraud")
    if oor.get("matched"):
        typology.append("out_of_region_use")
    if ato.get("matched"):
        typology.append("account_takeover")
    if not typology:
        typology = ["none"]

    query = " ".join(
        typology
        + [str(case_row.get("trigger_type") or ""), "risk score SAR stopping verify"]
    )
    policy_hits = retrieve_chunks(query, kinds=["policy", "regulatory"], limit=6)
    typ_hits = retrieve_chunks(" ".join(typology), kinds=["typology"], limit=4)
    policy_context = [c["body"] for c in policy_hits]
    for chunk in policy_hits[:3]:
        facts.append(
            EvidenceItem(
                claim=chunk["body"],
                source="document",
                ref=f"docs/fraud_policy.md#{chunk['chunk_id']}",
                entity_ids=[],
            )
        )

    prior = toolkit.related_closed_cases(card_id, customer_id, device_id=device_id or None, pattern=typology[0])
    if not prior:
        prior = toolkit.search_closed_cases(query=" ".join(typology), pattern=typology[0], limit=5)
    similar_ids = []
    for rec in prior:
        cid = rec.get("case_id") or ""
        if cid.startswith("CC-") and cid not in similar_ids:
            similar_ids.append(cid)
            facts.append(
                EvidenceItem(
                    claim=(
                        f"Prior closed case {cid} outcome={rec.get('outcome')} pattern={rec.get('pattern')} "
                        f"notes={(rec.get('analyst_notes') or '')[:180]}"
                    ),
                    source="graph",
                    ref=f"query:related_closed_cases(card_id={card_id})",
                    entity_ids=[cid],
                )
            )

    signals["typology_raw"] = typology
    signals["typology_docs"] = [c["title"] for c in typ_hits]
    return EvidenceBundle(
        case_id=case_id,
        flagged_txn_id=txn_id,
        graph_facts=facts,
        policy_context=policy_context,
        typology_matches=typology,
        similar_prior_cases=similar_ids,
        signals=signals,
    )
