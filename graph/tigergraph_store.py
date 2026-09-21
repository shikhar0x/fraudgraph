"""Live TigerGraph provider via pyTigerGraph. Optional — local store is the default."""
from __future__ import annotations

import logging
from typing import Any

from graph.local_store import LocalGraphStore
from graph.patterns import (
    detect_account_takeover,
    detect_card_testing,
    detect_cnp,
    detect_new_device_cnp,
    detect_out_of_region,
    detect_shared_origin,
)

logger = logging.getLogger("fraudgraph.tigergraph")


class TigerGraphStore:
    """Wraps pyTigerGraph for the GraphProvider contract.

    Pattern detection still runs in Python on the retrieved window so GSQL
    and local mode produce the same evidence structure. GSQL queries are
    used for retrieval (and optional native flags).
    """

    name = "tigergraph"
    mock_mode = False

    def __init__(self, conn: Any, fallback: LocalGraphStore | None = None) -> None:
        self.conn = conn
        self.fallback = fallback or LocalGraphStore()

    def _run(self, query: str, params: dict[str, Any] | None = None) -> Any:
        try:
            return self.conn.runInstalledQuery(query, params or {})
        except Exception as exc:  # noqa: BLE001 — live cluster optional
            logger.warning("TigerGraph query %s failed: %s", query, exc)
            return None

    def get_transaction(self, txn_id: str) -> dict[str, Any] | None:
        result = self._run("get_transaction", {"txn_id": txn_id})
        parsed = _first_vertex(result)
        return parsed or self.fallback.get_transaction(txn_id)

    def get_card(self, card_id: str) -> dict[str, Any] | None:
        result = self._run("get_card", {"card_id": card_id})
        return _first_vertex(result) or self.fallback.get_card(card_id)

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        result = self._run("get_customer", {"customer_id": customer_id})
        return _first_vertex(result) or self.fallback.get_customer(customer_id)

    def card_history(self, card_id: str, limit: int = 200) -> list[dict[str, Any]]:
        result = self._run("card_history", {"card_id": card_id, "limit_n": int(limit)})
        rows = _accum_rows(result, "@@rows")
        return rows or self.fallback.card_history(card_id, limit)

    def customer_history(self, customer_id: str, limit: int = 400) -> list[dict[str, Any]]:
        result = self._run("customer_history", {"customer_id": customer_id, "limit_n": int(limit)})
        rows = _accum_rows(result, "@@rows")
        return rows or self.fallback.customer_history(customer_id, limit)

    def transaction_window(self, txn_id: str, hours: float = 24.0) -> list[dict[str, Any]]:
        result = self._run("transaction_window", {"txn_id": txn_id})
        rows = _accum_rows(result, "@@rows")
        if rows:
            return rows
        return self.fallback.transaction_window(txn_id, hours)

    def device_neighbors(self, device_id: str) -> dict[str, Any]:
        result = self._run("device_neighbors", {"device_id": device_id})
        if result:
            return {
                "device_id": device_id,
                "cards": list(_accum_set(result, "@@cards")),
                "txns": list(_accum_set(result, "@@txns")),
                "customers": list(_accum_set(result, "@@customers")),
            }
        return self.fallback.device_neighbors(device_id)

    def region_neighbors(self, region: str) -> dict[str, Any]:
        result = self._run("region_neighbors", {"region": region})
        if result:
            return {
                "region": region,
                "cards": list(_accum_set(result, "@@cards")),
                "txn_count": _accum_num(result, "@@txn_count"),
            }
        return self.fallback.region_neighbors(region)

    def connected_cards(self, card_id: str) -> dict[str, Any]:
        result = self._run("connected_cards", {"card_id": card_id})
        if result:
            return {
                "via_device": list(_accum_set(result, "@@via_device")),
                "via_email": list(_accum_set(result, "@@via_email")),
                "via_region": [],
            }
        return self.fallback.connected_cards(card_id)

    def detect_card_testing(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        hist = self._history_dicts(card_id)
        return detect_card_testing(hist, around_txn_id)

    def detect_cnp(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return detect_cnp(self._history_dicts(card_id), around_txn_id)

    def detect_new_device_cnp(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return detect_new_device_cnp(self._history_dicts(card_id), around_txn_id)

    def detect_out_of_region(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return detect_out_of_region(self._history_dicts(card_id), around_txn_id)

    def detect_account_takeover(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return detect_account_takeover(self._history_dicts(card_id), around_txn_id)

    def detect_shared_origin(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        hist = self._history_dicts(card_id)
        connected = self.connected_cards(card_id)
        device_cards = {}
        email_cards = {}
        region_cards = {}
        for txn in hist:
            if txn.get("device_id"):
                device_cards.setdefault(txn["device_id"], set()).update(connected.get("via_device") or [])
                device_cards[txn["device_id"]].add(card_id)
            if txn.get("r_email"):
                email_cards.setdefault(txn["r_email"], set()).update(connected.get("via_email") or [])
                email_cards[txn["r_email"]].add(card_id)
        return detect_shared_origin(hist, card_id, device_cards, email_cards, region_cards, around_txn_id)

    def related_closed_cases(
        self,
        card_id: str,
        customer_id: str,
        device_id: str | None = None,
        pattern: str | None = None,
    ) -> list[dict[str, Any]]:
        result = self._run("related_closed_cases", {"card_id": card_id, "customer_id": customer_id})
        ids = list(_accum_set(result, "@@ids")) if result else []
        if ids:
            out = []
            for cid in ids:
                rec = self.fallback.closed_cases.get(cid)
                if rec:
                    out.append(self.fallback._public_closed(rec))
                else:
                    out.append({"case_id": cid, "pattern": "", "outcome": "", "analyst_notes": ""})
            return out[:8]
        return self.fallback.related_closed_cases(card_id, customer_id, device_id, pattern)

    def search_closed_cases(self, query: str, pattern: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        return self.fallback.search_closed_cases(query, pattern, limit)

    def write_case(self, payload: dict[str, Any]) -> str:
        graph_id = payload.get("graph_case_id") or f"CASE-{payload.get('case_id', '')}"
        params = {
            "case_id": graph_id,
            "customer_id": payload.get("customer_id") or "",
            "card_id": payload.get("card_id") or "",
            "status": payload.get("status") or "",
            "verdict": payload.get("verdict") or "",
            "fraud_probability": float(payload.get("fraud_probability") or 0),
            "pattern": payload.get("pattern") or "",
            "pattern_description": payload.get("pattern_description") or "",
            "exposure_usd": float(payload.get("exposure_usd") or 0),
            "summary": payload.get("summary") or "",
            "sar_filed": bool(payload.get("sar_filed")),
            "flagged_txn_id": payload.get("flagged_txn_id") or "",
        }
        result = self._run("write_investigation_case", params)
        self.fallback.write_case({**payload, "graph_case_id": graph_id})
        if result is None:
            logger.info("TigerGraph write_case fell back to local memory for %s", graph_id)
            return ""
        return graph_id

    def known_ids(self) -> dict[str, set[str]]:
        return self.fallback.known_ids()

    def dataset_status(self) -> dict[str, Any]:
        status = self.fallback.dataset_status()
        status["tigergraph"] = True
        return status

    def _history_dicts(self, card_id: str) -> list[dict[str, Any]]:
        rows = self.card_history(card_id, limit=400)
        from graph.local_store import parse_ts

        out = []
        for r in rows:
            item = dict(r)
            if "txn_id" not in item and "id" in item:
                item["txn_id"] = item["id"]
            if not isinstance(item.get("ts"), type(parse_ts("2016-01-01"))):
                item["ts"] = parse_ts(item.get("ts"))
            out.append(item)
        return out


def connect_tigergraph(settings: Any) -> Any:
    try:
        import pyTigerGraph as tg  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pyTigerGraph is not installed") from exc
    kwargs: dict[str, Any] = {
        "host": settings.tg_host,
        "graphname": settings.tg_graphname,
        "username": settings.tg_username,
        "password": settings.tg_password or "tigergraph",
    }
    if settings.tg_restpp_port:
        kwargs["restppPort"] = settings.tg_restpp_port
    if settings.tg_gs_port:
        kwargs["gsPort"] = settings.tg_gs_port
    conn = tg.TigerGraphConnection(**kwargs)
    if settings.tg_api_token:
        conn.apiToken = settings.tg_api_token
    elif settings.tg_secret:
        try:
            conn.getToken(settings.tg_secret)
        except Exception as exc:  # noqa: BLE001
            logger.warning("getToken failed: %s", exc)
    return conn


def _first_vertex(result: Any) -> dict[str, Any] | None:
    if not result:
        return None
    rows = result if isinstance(result, list) else [result]
    for block in rows:
        if not isinstance(block, dict):
            continue
        for value in block.values():
            if isinstance(value, list) and value:
                item = value[0]
                if isinstance(item, dict):
                    attrs = item.get("attributes") or item
                    vid = item.get("v_id") or attrs.get("txn_id") or attrs.get("card_id") or attrs.get("customer_id")
                    if isinstance(attrs, dict):
                        out = dict(attrs)
                        if vid and "txn_id" not in out and "card_id" not in out:
                            out.setdefault("id", vid)
                        return out
            if isinstance(value, dict) and value.get("attributes"):
                return dict(value["attributes"])
    return None


def _accum_rows(result: Any, key: str) -> list[dict[str, Any]]:
    if not result:
        return []
    rows = result if isinstance(result, list) else [result]
    out: list[dict[str, Any]] = []
    for block in rows:
        if isinstance(block, dict) and key in block:
            for item in block[key] or []:
                if isinstance(item, dict):
                    if "id" in item and "txn_id" not in item:
                        item = {**item, "txn_id": item["id"]}
                    out.append(item)
    return out


def _accum_set(result: Any, key: str) -> list[str]:
    if not result:
        return []
    rows = result if isinstance(result, list) else [result]
    for block in rows:
        if isinstance(block, dict) and key in block:
            val = block[key]
            if isinstance(val, (list, set, tuple)):
                return [str(x) for x in val]
    return []


def _accum_num(result: Any, key: str) -> int:
    if not result:
        return 0
    rows = result if isinstance(result, list) else [result]
    for block in rows:
        if isinstance(block, dict) and key in block:
            try:
                return int(block[key])
            except (TypeError, ValueError):
                return 0
    return 0
