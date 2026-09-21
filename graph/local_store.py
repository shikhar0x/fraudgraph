"""Pandas/dict graph store. Used when TigerGraph is unavailable and for tests."""
from __future__ import annotations

import json
import pickle
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from graph.ids import device_profile_id, stringify
from graph.patterns import (
    detect_account_takeover,
    detect_card_testing,
    detect_cnp,
    detect_new_device_cnp,
    detect_out_of_region,
    detect_recurring_legitimate,
    detect_shared_origin,
    empty_match,
)

_AMOUNT_RE = re.compile(r"\$([0-9,]+\.\d{2})")
_REGION_RE = re.compile(r"billing region ([0-9.]+)", re.I)


def parse_ts(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19].replace("T", " "), fmt if fmt != "%Y-%m-%d %H:%M:%S" else "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    try:
        from dateutil import parser as date_parser

        return date_parser.parse(text)
    except Exception:
        return None


def parse_trigger_text(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {"amount": None, "channel": None, "region": None}
    if not text:
        return out
    m = _AMOUNT_RE.search(text)
    if m:
        out["amount"] = float(m.group(1).replace(",", ""))
    m = _REGION_RE.search(text)
    if m:
        out["region"] = m.group(1)
        out["channel"] = "in_person"
    if re.search(r"\bonline\b", text, re.I):
        out["channel"] = "online"
    return out


def _jsonable_txn(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    ts = out.get("ts")
    if isinstance(ts, datetime):
        out["ts"] = ts.isoformat(sep=" ")
    return out


class LocalGraphStore:
    name = "local"
    mock_mode = True

    def __init__(self) -> None:
        self.transactions: dict[str, dict[str, Any]] = {}
        self.cards: dict[str, dict[str, Any]] = {}
        self.customers: dict[str, dict[str, Any]] = {}
        self.devices: dict[str, dict[str, Any]] = {}
        self.closed_cases: dict[str, dict[str, Any]] = {}
        self.investigation_cases: dict[str, dict[str, Any]] = {}
        self.case_pack: dict[str, dict[str, Any]] = {}
        self.card_txns: dict[str, list[str]] = defaultdict(list)
        self.customer_cards: dict[str, set[str]] = defaultdict(set)
        self.device_txns: dict[str, list[str]] = defaultdict(list)
        self.device_cards: dict[str, set[str]] = defaultdict(set)
        self.email_cards: dict[str, set[str]] = defaultdict(set)
        self.region_cards: dict[str, set[str]] = defaultdict(set)
        self.region_txns: dict[str, list[str]] = defaultdict(list)
        self.status: dict[str, Any] = {
            "transactions_csv": False,
            "identity_csv": False,
            "closed_cases_history_csv": False,
            "case_pack_csv": False,
            "used_fallback_case_pack": False,
            "txn_count": 0,
            "closed_case_count": 0,
        }

    # ----- mutations -----
    def add_transaction(self, row: dict[str, Any]) -> None:
        txn_id = stringify(row.get("txn_id"))
        if not txn_id:
            return
        card_id = stringify(row.get("card_id"))
        customer_id = stringify(row.get("customer_id"))
        row = dict(row)
        row["txn_id"] = txn_id
        row["card_id"] = card_id
        row["customer_id"] = customer_id
        if not isinstance(row.get("ts"), datetime):
            row["ts"] = parse_ts(row.get("ts"))
        try:
            row["amount"] = float(row.get("amount") or 0.0)
        except (TypeError, ValueError):
            row["amount"] = 0.0
        try:
            row["risk_score"] = float(row.get("risk_score") or 0.0)
        except (TypeError, ValueError):
            row["risk_score"] = 0.0
        self.transactions[txn_id] = row
        if card_id:
            self.card_txns[card_id].append(txn_id)
            if card_id not in self.cards:
                self.cards[card_id] = {
                    "card_id": card_id,
                    "customer_id": customer_id,
                    "network": row.get("network") or "",
                    "card_type": row.get("card_type") or "",
                    "card1": row.get("card1") or "",
                }
            if customer_id:
                self.customer_cards[customer_id].add(card_id)
        if customer_id and customer_id not in self.customers:
            self.customers[customer_id] = {"customer_id": customer_id}
        device_id = stringify(row.get("device_id"))
        if device_id:
            self.device_txns[device_id].append(txn_id)
            if card_id:
                self.device_cards[device_id].add(card_id)
            if device_id not in self.devices:
                self.devices[device_id] = {
                    "device_id": device_id,
                    "device_info": row.get("device_info") or "",
                    "os": row.get("os") or "",
                    "browser": row.get("browser") or "",
                    "screen": row.get("screen") or "",
                    "device_type": row.get("device_type") or "",
                }
        email = stringify(row.get("r_email") or row.get("p_email"))
        if email and card_id:
            self.email_cards[email].add(card_id)
        region = stringify(row.get("addr1"))
        if region:
            self.region_txns[region].append(txn_id)
            if card_id:
                self.region_cards[region].add(card_id)

    def finalize_indexes(self) -> None:
        for card_id, ids in self.card_txns.items():
            uniq = list(dict.fromkeys(ids))
            uniq.sort(key=lambda i: ((self.transactions[i].get("ts") or datetime.min), i))
            self.card_txns[card_id] = uniq
        self.status["txn_count"] = len(self.transactions)
        self.status["closed_case_count"] = len(self.closed_cases)

    def add_closed_case(self, row: dict[str, Any]) -> None:
        case_id = stringify(row.get("case_id"))
        if not case_id:
            return
        txn_ids = stringify(row.get("txn_ids"))
        connected = stringify(row.get("connected_card_ids"))
        rec = dict(row)
        rec["case_id"] = case_id
        rec["txn_id_list"] = [p for p in txn_ids.split("|") if p] if txn_ids else []
        rec["connected_list"] = [p for p in connected.split("|") if p] if connected else []
        rec["opened_at"] = parse_ts(row.get("opened_at"))
        rec["closed_at"] = parse_ts(row.get("closed_at"))
        try:
            rec["exposure_usd"] = float(row.get("exposure_usd") or 0.0)
        except (TypeError, ValueError):
            rec["exposure_usd"] = 0.0
        rf = str(row.get("report_filed") or "").strip().lower()
        rec["report_filed"] = rf in {"1", "true", "yes", "y"}
        rec["analyst_notes"] = stringify(row.get("analyst_notes"))
        rec["pattern"] = stringify(row.get("pattern")) or "none"
        rec["outcome"] = stringify(row.get("outcome"))
        rec["card_id"] = stringify(row.get("card_id"))
        rec["customer_id"] = stringify(row.get("customer_id"))
        self.closed_cases[case_id] = rec

    def seed_case_pack(self, rows: list[dict[str, Any]], used_fallback: bool = False) -> None:
        for raw in rows:
            case_id = stringify(raw.get("case_id"))
            if not case_id:
                continue
            parsed = parse_trigger_text(stringify(raw.get("trigger_text")))
            risk = raw.get("risk_score")
            try:
                risk_f = float(risk) if risk not in (None, "") else 0.0
            except (TypeError, ValueError):
                risk_f = 0.0
            rec = {
                "case_id": case_id,
                "opened_at": stringify(raw.get("opened_at")),
                "trigger_type": stringify(raw.get("trigger_type")),
                "trigger_text": stringify(raw.get("trigger_text")),
                "flagged_txn_id": stringify(raw.get("flagged_txn_id")),
                "card_id": stringify(raw.get("card_id")),
                "customer_id": stringify(raw.get("customer_id")),
                "risk_score": risk_f,
            }
            self.case_pack[case_id] = rec
            txn_id = rec["flagged_txn_id"]
            if txn_id and txn_id not in self.transactions:
                self.add_transaction(
                    {
                        "txn_id": txn_id,
                        "card_id": rec["card_id"],
                        "customer_id": rec["customer_id"],
                        "ts": parse_ts(rec["opened_at"]),
                        "amount": parsed["amount"] if parsed["amount"] is not None else 0.0,
                        "amount_known": parsed["amount"] is not None,
                        "product_cd": "",
                        "channel": parsed["channel"] or "",
                        "risk_score": risk_f,
                        "addr1": parsed["region"] or "",
                        "addr2": "",
                        "p_email": "",
                        "r_email": "",
                        "device_id": "",
                        "device_status": "",
                        "proxy": "",
                        "source": "case_pack",
                    }
                )
            elif txn_id and txn_id in self.transactions:
                # Preserve dataset amounts; attach trigger metadata only.
                self.transactions[txn_id]["from_case_pack"] = True
        self.status["used_fallback_case_pack"] = used_fallback
        self.status["case_pack_csv"] = not used_fallback
        self.finalize_indexes()

    # ----- queries -----
    def get_transaction(self, txn_id: str) -> dict[str, Any] | None:
        row = self.transactions.get(str(txn_id))
        return _jsonable_txn(row) if row else None

    def get_card(self, card_id: str) -> dict[str, Any] | None:
        return self.cards.get(str(card_id))

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        rec = self.customers.get(str(customer_id))
        if not rec:
            return None
        return {**rec, "card_ids": sorted(self.customer_cards.get(str(customer_id), set()))}

    def _txns_for_card(self, card_id: str) -> list[dict[str, Any]]:
        return [self.transactions[i] for i in self.card_txns.get(str(card_id), []) if i in self.transactions]

    def card_history(self, card_id: str, limit: int = 200) -> list[dict[str, Any]]:
        rows = self._txns_for_card(card_id)
        rows = sorted(rows, key=lambda t: (t.get("ts") or datetime.min, t["txn_id"]), reverse=True)
        return [_jsonable_txn(r) for r in rows[:limit]]

    def customer_history(self, customer_id: str, limit: int = 400) -> list[dict[str, Any]]:
        ids: list[str] = []
        for card_id in self.customer_cards.get(str(customer_id), set()):
            ids.extend(self.card_txns.get(card_id, []))
        rows = [self.transactions[i] for i in ids if i in self.transactions]
        rows = sorted(rows, key=lambda t: (t.get("ts") or datetime.min, t["txn_id"]), reverse=True)
        return [_jsonable_txn(r) for r in rows[:limit]]

    def transaction_window(self, txn_id: str, hours: float = 24.0) -> list[dict[str, Any]]:
        row = self.transactions.get(str(txn_id))
        if not row or not row.get("ts") or not row.get("card_id"):
            return [self.get_transaction(str(txn_id))] if row else []
        delta = timedelta(hours=hours)
        out = []
        for other in self._txns_for_card(row["card_id"]):
            if other.get("ts") and abs(other["ts"] - row["ts"]) <= delta:
                out.append(other)
        out.sort(key=lambda t: (t.get("ts") or datetime.min, t["txn_id"]))
        return [_jsonable_txn(r) for r in out]

    def device_neighbors(self, device_id: str) -> dict[str, Any]:
        if not device_id:
            return {"device_id": "", "cards": [], "txns": [], "customers": []}
        txns = self.device_txns.get(device_id, [])
        cards = sorted(self.device_cards.get(device_id, set()))
        customers = sorted({self.cards[c].get("customer_id", "") for c in cards if c in self.cards and self.cards[c].get("customer_id")})
        return {
            "device_id": device_id,
            "device": self.devices.get(device_id),
            "cards": cards,
            "txns": txns[:200],
            "customers": customers,
        }

    def region_neighbors(self, region: str) -> dict[str, Any]:
        if not region:
            return {"region": "", "cards": [], "txn_count": 0}
        cards = sorted(self.region_cards.get(str(region), set()))
        return {"region": str(region), "cards": cards[:200], "txn_count": len(self.region_txns.get(str(region), []))}

    def connected_cards(self, card_id: str) -> dict[str, Any]:
        via_device: set[str] = set()
        via_email: set[str] = set()
        via_region: set[str] = set()
        for txn in self._txns_for_card(card_id):
            d = txn.get("device_id") or ""
            if d:
                via_device |= self.device_cards.get(d, set())
            e = txn.get("r_email") or txn.get("p_email") or ""
            if e:
                via_email |= self.email_cards.get(e, set())
            r = stringify(txn.get("addr1"))
            if r and len(self.region_cards.get(r, set())) <= 12:
                via_region |= self.region_cards.get(r, set())
        via_device.discard(card_id)
        via_email.discard(card_id)
        via_region.discard(card_id)
        return {
            "via_device": sorted(via_device),
            "via_email": sorted(via_email),
            "via_region": sorted(via_region),
        }

    def detect_card_testing(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return detect_card_testing(self._txns_for_card(card_id), around_txn_id)

    def detect_cnp(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return detect_cnp(self._txns_for_card(card_id), around_txn_id)

    def detect_new_device_cnp(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return detect_new_device_cnp(self._txns_for_card(card_id), around_txn_id)

    def detect_out_of_region(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return detect_out_of_region(self._txns_for_card(card_id), around_txn_id)

    def detect_account_takeover(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return detect_account_takeover(self._txns_for_card(card_id), around_txn_id)

    def detect_shared_origin(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return detect_shared_origin(
            self._txns_for_card(card_id),
            card_id,
            self.device_cards,
            self.email_cards,
            self.region_cards,
            around_txn_id,
        )

    def detect_recurring(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return detect_recurring_legitimate(self._txns_for_card(card_id), around_txn_id)

    def related_closed_cases(
        self,
        card_id: str,
        customer_id: str,
        device_id: str | None = None,
        pattern: str | None = None,
    ) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        for rec in self.closed_cases.values():
            score = 0.0
            reasons = []
            if card_id and rec.get("card_id") == card_id:
                score += 3
                reasons.append("same_card")
            if card_id and card_id in rec.get("connected_list", []):
                score += 2.5
                reasons.append("connected_card")
            if customer_id and rec.get("customer_id") == customer_id:
                score += 1.5
                reasons.append("same_customer")
            if pattern and rec.get("pattern") == pattern and rec.get("outcome") == "confirmed_fraud":
                score += 1.0
                reasons.append("same_pattern")
            if device_id:
                notes = (rec.get("analyst_notes") or "") + " " + " ".join(rec.get("connected_list", []))
                if device_id in notes:
                    score += 1.5
                    reasons.append("device_note")
            if score <= 0:
                continue
            hits.append({**self._public_closed(rec), "score": score, "reasons": reasons})
        hits.sort(key=lambda r: r["score"], reverse=True)
        return hits[:8]

    def search_closed_cases(self, query: str, pattern: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        tokens = {t.lower() for t in re.findall(r"[a-zA-Z0-9_\-]+", query or "") if len(t) > 2}
        hits: list[dict[str, Any]] = []
        for rec in self.closed_cases.values():
            if pattern and rec.get("pattern") not in {pattern, "undocumented"} and rec.get("pattern") != pattern:
                if pattern != rec.get("pattern"):
                    pass
            blob = " ".join(
                [
                    rec.get("analyst_notes") or "",
                    rec.get("pattern") or "",
                    rec.get("outcome") or "",
                    rec.get("card_id") or "",
                    rec.get("customer_id") or "",
                ]
            ).lower()
            note_tokens = set(re.findall(r"[a-zA-Z0-9_\-]+", blob))
            overlap = len(tokens & note_tokens) if tokens else 0
            score = overlap
            if pattern and rec.get("pattern") == pattern:
                score += 3
            if rec.get("outcome") == "confirmed_fraud":
                score += 0.5
            if score <= 0:
                continue
            hits.append({**self._public_closed(rec), "score": float(score)})
        hits.sort(key=lambda r: r["score"], reverse=True)
        return hits[:limit]

    def _public_closed(self, rec: dict[str, Any]) -> dict[str, Any]:
        return {
            "case_id": rec["case_id"],
            "customer_id": rec.get("customer_id") or "",
            "card_id": rec.get("card_id") or "",
            "outcome": rec.get("outcome") or "",
            "pattern": rec.get("pattern") or "",
            "exposure_usd": rec.get("exposure_usd") or 0.0,
            "analyst_notes": rec.get("analyst_notes") or "",
            "txn_ids": rec.get("txn_id_list") or [],
            "connected_card_ids": rec.get("connected_list") or [],
        }

    def write_case(self, payload: dict[str, Any]) -> str:
        case_id = stringify(payload.get("graph_case_id") or payload.get("case_id"))
        if not case_id:
            return ""
        self.investigation_cases[case_id] = dict(payload)
        return case_id

    def known_ids(self) -> dict[str, set[str]]:
        devices = set(self.devices)
        return {
            "txn": set(self.transactions),
            "card": set(self.cards),
            "customer": set(self.customers),
            "device": devices,
            "closed_case": set(self.closed_cases),
            "case_pack": set(self.case_pack),
        }

    def dataset_status(self) -> dict[str, Any]:
        return dict(self.status)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            pickle.dump(self, fh, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def load(path: Path) -> "LocalGraphStore":
        with path.open("rb") as fh:
            obj = pickle.load(fh)
        if not isinstance(obj, LocalGraphStore):
            raise TypeError(f"unexpected object in {path}")
        return obj
