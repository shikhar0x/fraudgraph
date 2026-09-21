"""Chunked, rerunnable ingestion of the HHGOA IEEE dataset into the local graph
and (optionally) export of slim CSVs for TigerGraph loading jobs.

Never loads the 708MB file into an LLM prompt. Streams transactions.csv.
"""
from __future__ import annotations

import csv
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from app.config import (
    CASE_PACK_REQUIRED_HEADERS,
    CLOSED_REQUIRED_HEADERS,
    IDENTITY_OPTIONAL_HEADERS,
    IDENTITY_REQUIRED_HEADERS,
    RAW_FILES,
    TXN_OPTIONAL_HEADERS,
    TXN_REQUIRED_HEADERS,
    Settings,
    get_settings,
)
from graph.factory import default_pickle_path
from graph.ids import device_profile_id, stringify
from graph.local_store import LocalGraphStore, parse_ts

logger = logging.getLogger("fraudgraph.ingest")

CHUNK = 50_000


class IngestError(RuntimeError):
    pass


def _require_headers(path: Path, required: list[str]) -> list[str]:
    if not path.exists():
        raise IngestError(f"missing file: {path}")
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        try:
            headers = next(reader)
        except StopIteration as exc:
            raise IngestError(f"empty CSV: {path}") from exc
    missing = [h for h in required if h not in headers]
    if missing:
        raise IngestError(f"{path.name} missing required headers: {missing}")
    return headers


def _present(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def load_case_pack_rows(settings: Settings | None = None) -> tuple[list[dict[str, Any]], bool]:
    """Return (rows, used_fallback)."""
    settings = settings or get_settings()
    primary = settings.data_dir / RAW_FILES["case_pack"]
    fallback = settings.fallback_case_pack
    path = primary if _present(primary) else fallback
    used_fallback = path == fallback
    if not _present(path):
        raise IngestError("no case_pack.csv and no fallback pack")
    _require_headers(path, CASE_PACK_REQUIRED_HEADERS)
    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) < 1:
        raise IngestError("case pack is empty")
    return rows, used_fallback


def _iter_csv_chunks(path: Path, usecols: list[str], chunksize: int = CHUNK) -> Iterable[Any]:
    import pandas as pd

    headers = _peek_headers(path)
    cols = [c for c in usecols if c in headers]
    for chunk in pd.read_csv(path, usecols=cols, chunksize=chunksize, dtype=str, keep_default_na=False):
        yield chunk


def _peek_headers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        return next(reader)


def _card_key_map(txn_path: Path, headers: list[str]) -> dict[tuple[str, str], str]:
    """If card_id is absent, assign {customer_id}-K{n} from sorted unique card1 values."""
    if "card_id" in headers:
        return {}
    if "card1" not in headers or "customer_id" not in headers:
        return {}
    pairs: dict[str, set[str]] = defaultdict(set)
    logger.info("Pass 1/2: collecting (customer_id, card1) for card_id assignment")
    n = 0
    for chunk in _iter_csv_chunks(txn_path, ["customer_id", "card1"]):
        for rec in chunk.itertuples(index=False):
            cust = stringify(rec.customer_id)
            card1 = stringify(rec.card1)
            if cust:
                pairs[cust].add(card1)
            n += 1
        logger.info("  scanned %s transaction rows", f"{n:,}")
    mapping: dict[tuple[str, str], str] = {}
    for cust, card1s in pairs.items():
        for i, card1 in enumerate(sorted(card1s), start=1):
            mapping[(cust, card1)] = f"{cust}-K{i}"
    logger.info("Assigned card_ids for %s customers", f"{len(pairs):,}")
    return mapping


def ingest(
    settings: Settings | None = None,
    *,
    export: bool = False,
    persist: bool = True,
    store: LocalGraphStore | None = None,
) -> LocalGraphStore:
    settings = settings or get_settings()
    data_dir = settings.data_dir
    store = store or LocalGraphStore()
    logger.info("Ingest starting. data_dir=%s", data_dir)

    txn_path = data_dir / RAW_FILES["transactions"]
    ident_path = data_dir / RAW_FILES["identity"]
    closed_path = data_dir / RAW_FILES["closed_cases"]

    identity_by_txn: dict[str, dict[str, str]] = {}
    if _present(ident_path):
        headers = _require_headers(ident_path, IDENTITY_REQUIRED_HEADERS)
        logger.info("Loading identity.csv in chunks")
        usecols = IDENTITY_REQUIRED_HEADERS + [h for h in IDENTITY_OPTIONAL_HEADERS if h in headers]
        n = 0
        for chunk in _iter_csv_chunks(ident_path, usecols):
            for rec in chunk.to_dict(orient="records"):
                tid = stringify(rec.get("TransactionID"))
                if not tid:
                    continue
                identity_by_txn[tid] = {k: stringify(v) for k, v in rec.items()}
                n += 1
            logger.info("  identity rows %s", f"{n:,}")
        store.status["identity_csv"] = True
        logger.info("Identity records: %s", f"{len(identity_by_txn):,}")
    else:
        logger.warning("identity.csv not present — online device edges will be empty")

    card_map: dict[tuple[str, str], str] = {}
    if _present(txn_path):
        headers = _require_headers(txn_path, TXN_REQUIRED_HEADERS)
        card_map = _card_key_map(txn_path, headers)
        usecols = [h for h in TXN_REQUIRED_HEADERS + TXN_OPTIONAL_HEADERS if h in headers]
        logger.info("Loading transactions.csv in chunks (usecols=%s)", usecols)
        n = 0
        errors = 0
        for chunk in _iter_csv_chunks(txn_path, usecols):
            records = chunk.to_dict(orient="records")
            for rec in records:
                try:
                    _add_txn_row(store, rec, identity_by_txn, card_map, headers)
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    if errors <= 5:
                        logger.warning("txn row skipped: %s", exc)
                n += 1
            logger.info("  transactions loaded %s (errors=%s)", f"{n:,}", errors)
        store.status["transactions_csv"] = True
        logger.info("Transactions indexed: %s", f"{len(store.transactions):,}")
    else:
        logger.warning("transactions.csv not present — graph will be seeded from the case pack only")

    # Free identity map
    identity_by_txn.clear()

    if _present(closed_path):
        _require_headers(closed_path, CLOSED_REQUIRED_HEADERS)
        logger.info("Loading closed_cases_history.csv")
        with closed_path.open("r", encoding="utf-8", newline="") as fh:
            for rec in csv.DictReader(fh):
                store.add_closed_case(rec)
        store.status["closed_cases_history_csv"] = True
        logger.info("Closed cases: %s", f"{len(store.closed_cases):,}")
    else:
        logger.warning("closed_cases_history.csv not present — similar_prior_cases will be empty")

    pack_rows, used_fallback = load_case_pack_rows(settings)
    store.seed_case_pack(pack_rows, used_fallback=used_fallback)
    logger.info("Case pack: %s rows (fallback=%s)", len(pack_rows), used_fallback)

    store.finalize_indexes()

    if persist:
        out = default_pickle_path(settings)
        store.save(out)
        logger.info("Wrote local graph to %s", out)

    if export:
        export_dir = settings.processed_dir / "tigergraph_csv"
        export_slim_csvs(store, export_dir)
        logger.info("Exported TigerGraph CSVs to %s", export_dir)

    return store


def _add_txn_row(
    store: LocalGraphStore,
    rec: dict[str, Any],
    identity_by_txn: dict[str, dict[str, str]],
    card_map: dict[tuple[str, str], str],
    headers: list[str],
) -> None:
    txn_id = stringify(rec.get("TransactionID"))
    if not txn_id:
        return
    customer_id = stringify(rec.get("customer_id"))
    if "card_id" in headers:
        card_id = stringify(rec.get("card_id"))
    else:
        card_id = card_map.get((customer_id, stringify(rec.get("card1"))), "")
        if not card_id and customer_id:
            card_id = f"{customer_id}-K1"
    ident = identity_by_txn.get(txn_id, {})
    device_id = device_profile_id(
        ident.get("DeviceInfo", ""),
        ident.get("id_30", ""),
        ident.get("id_31", ""),
        ident.get("id_33", ""),
    )
    channel = stringify(rec.get("channel")).lower()
    if not channel:
        product = stringify(rec.get("ProductCD"))
        channel = "in_person" if product == "W" else ("online" if product else "")
    store.add_transaction(
        {
            "txn_id": txn_id,
            "card_id": card_id,
            "customer_id": customer_id,
            "ts": parse_ts(rec.get("ts")),
            "amount": rec.get("TransactionAmt") or 0,
            "product_cd": stringify(rec.get("ProductCD")),
            "channel": channel,
            "risk_score": rec.get("risk_score") or 0,
            "addr1": stringify(rec.get("addr1")),
            "addr2": stringify(rec.get("addr2")),
            "p_email": stringify(rec.get("P_emaildomain")),
            "r_email": stringify(rec.get("R_emaildomain")),
            "dist1": rec.get("dist1") or 0,
            "dist2": rec.get("dist2") or 0,
            "network": stringify(rec.get("card4")),
            "card_type": stringify(rec.get("card6")),
            "card1": stringify(rec.get("card1")),
            "device_id": device_id,
            "device_info": ident.get("DeviceInfo", ""),
            "os": ident.get("id_30", ""),
            "browser": ident.get("id_31", ""),
            "screen": ident.get("id_33", ""),
            "device_type": ident.get("DeviceType", ""),
            "device_status": ident.get("id_15", ""),
            "proxy": ident.get("id_23", ""),
            "amount_known": True,
            "source": "transactions.csv",
        }
    )


def export_slim_csvs(store: LocalGraphStore, export_dir: Path) -> None:
    """Write entity/edge CSVs for the TigerGraph loading job. Batched files, not per-row API calls."""
    export_dir.mkdir(parents=True, exist_ok=True)

    def dump(name: str, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
        path = export_dir / name
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for row in rows:
                w.writerow({k: _csv_val(row.get(k)) for k in fieldnames})

    dump("customers.csv", ["customer_id"], ({"customer_id": c} for c in store.customers))
    dump(
        "cards.csv",
        ["card_id", "customer_id", "network", "card_type", "card1"],
        store.cards.values(),
    )
    dump(
        "devices.csv",
        ["device_id", "device_info", "os", "browser", "screen", "device_type"],
        store.devices.values(),
    )
    emails = set()
    regions: dict[str, str] = {}
    txn_rows = []
    next_rows = []
    for txn in store.transactions.values():
        if txn.get("p_email"):
            emails.add(txn["p_email"])
        if txn.get("r_email"):
            emails.add(txn["r_email"])
        if txn.get("addr1"):
            regions[str(txn["addr1"])] = stringify(txn.get("addr2"))
        ts = txn.get("ts")
        txn_rows.append(
            {
                "txn_id": txn["txn_id"],
                "card_id": txn.get("card_id") or "",
                "ts": ts.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ts, "strftime") else "",
                "amount": txn.get("amount") or 0,
                "product_cd": txn.get("product_cd") or "",
                "channel": txn.get("channel") or "",
                "risk_score": txn.get("risk_score") or 0,
                "addr1": txn.get("addr1") or "",
                "addr2": txn.get("addr2") or "",
                "p_email": txn.get("p_email") or "",
                "r_email": txn.get("r_email") or "",
                "dist1": txn.get("dist1") or 0,
                "dist2": txn.get("dist2") or 0,
                "device_status": txn.get("device_status") or "",
                "proxy": txn.get("proxy") or "",
                "device_type": txn.get("device_type") or "",
                "device_id": txn.get("device_id") or "",
            }
        )
    for card_id, ids in store.card_txns.items():
        for a, b in zip(ids, ids[1:]):
            ta = store.transactions[a].get("ts")
            tb = store.transactions[b].get("ts")
            gap = int((tb - ta).total_seconds()) if ta and tb else 0
            next_rows.append({"from_txn": a, "to_txn": b, "gap_seconds": max(gap, 0)})

    dump("emails.csv", ["domain"], ({"domain": e} for e in sorted(emails)))
    dump("regions.csv", ["region", "country"], ({"region": r, "country": c} for r, c in regions.items()))
    dump(
        "transactions.csv",
        [
            "txn_id",
            "card_id",
            "ts",
            "amount",
            "product_cd",
            "channel",
            "risk_score",
            "addr1",
            "addr2",
            "p_email",
            "r_email",
            "dist1",
            "dist2",
            "device_status",
            "proxy",
            "device_type",
            "device_id",
        ],
        txn_rows,
    )
    dump("next.csv", ["from_txn", "to_txn", "gap_seconds"], next_rows)

    closed_rows = []
    closed_txn = []
    closed_conn = []
    for rec in store.closed_cases.values():
        opened = rec.get("opened_at")
        closed = rec.get("closed_at")
        closed_rows.append(
            {
                "case_id": rec["case_id"],
                "customer_id": rec.get("customer_id") or "",
                "card_id": rec.get("card_id") or "",
                "opened_at": opened.strftime("%Y-%m-%d %H:%M:%S") if hasattr(opened, "strftime") else "",
                "closed_at": closed.strftime("%Y-%m-%d %H:%M:%S") if hasattr(closed, "strftime") else "",
                "outcome": rec.get("outcome") or "",
                "pattern": rec.get("pattern") or "",
                "first_fraud_txn_id": rec.get("first_fraud_txn_id") or "",
                "txn_ids": "|".join(rec.get("txn_id_list") or []),
                "n_txns": rec.get("n_txns") or len(rec.get("txn_id_list") or []),
                "exposure_usd": rec.get("exposure_usd") or 0,
                "connected_card_ids": "|".join(rec.get("connected_list") or []),
                "actions_taken": rec.get("actions_taken") or "",
                "report_filed": "true" if rec.get("report_filed") else "false",
                "analyst_notes": rec.get("analyst_notes") or "",
            }
        )
        for tid in rec.get("txn_id_list") or []:
            closed_txn.append({"case_id": rec["case_id"], "txn_id": tid})
        for cid in rec.get("connected_list") or []:
            closed_conn.append({"case_id": rec["case_id"], "card_id": cid})
    dump(
        "closed_cases.csv",
        [
            "case_id",
            "customer_id",
            "card_id",
            "opened_at",
            "closed_at",
            "outcome",
            "pattern",
            "first_fraud_txn_id",
            "txn_ids",
            "n_txns",
            "exposure_usd",
            "connected_card_ids",
            "actions_taken",
            "report_filed",
            "analyst_notes",
        ],
        closed_rows,
    )
    dump("closed_txn.csv", ["case_id", "txn_id"], closed_txn)
    dump("closed_conn.csv", ["case_id", "card_id"], closed_conn)

    from agent.graphrag.documents import all_chunks

    dump("policy.csv", ["chunk_id", "title", "body", "kind"], all_chunks())


def _csv_val(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
