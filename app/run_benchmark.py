"""Run the investigation pipeline on the 20 case-pack cases.

python -m app.run_benchmark
python -m app.run_benchmark --case HHG-001
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from agent.reasoning.graph import run_investigation
from graph.factory import get_provider, load_or_empty_local, reset_provider_cache
from graph.ingestion.pipeline import ingest, load_case_pack_rows
from graph.toolkit import GraphToolkit
from validation.validator import validate_case_record


def ensure_data(settings) -> None:
    store = load_or_empty_local(settings)
    if store.case_pack:
        return
    ingest(settings, persist=True)
    reset_provider_cache()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate cases/HHG-*.json from the investigation pipeline")
    parser.add_argument("--case", action="append", dest="cases", help="Case id (repeatable). Default: all 20")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    settings.cases_dir.mkdir(parents=True, exist_ok=True)
    ensure_data(settings)
    provider = get_provider(settings)
    rows, used_fallback = load_case_pack_rows(settings)
    if args.cases:
        wanted = set(args.cases)
        rows = [r for r in rows if r["case_id"] in wanted]
    if args.limit:
        rows = rows[: args.limit]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "graph_backend": getattr(provider, "name", "local"),
        "mock_mode": bool(getattr(provider, "mock_mode", True)),
        "dataset_status": provider.dataset_status() if hasattr(provider, "dataset_status") else {},
        "used_fallback_case_pack": used_fallback,
        "cases_processed": 0,
        "cases_successful": 0,
        "validation_failures": [],
        "runtime_statistics": {"total_s": 0.0, "per_case_s": {}},
        "tool_call_statistics": {"total": 0, "per_case": {}},
        "token_statistics": {"total": 0, "per_case": {}},
        "error_messages": [],
        "limitations": [],
    }
    if used_fallback or not provider.dataset_status().get("transactions_csv"):
        report["limitations"].append(
            "Full transactions.csv was not loaded; investigations used available graph data "
            "plus case_pack fields only. Do not treat these outputs as scored benchmark accuracy."
        )
    if getattr(provider, "mock_mode", True):
        report["limitations"].append("Graph backend is local/mock — written_to_graph is false.")

    t0 = time.perf_counter()
    for raw in rows:
        case_id = raw["case_id"]
        logging.info("Investigating %s", case_id)
        toolkit = GraphToolkit(provider)
        started = time.perf_counter()
        report["cases_processed"] += 1
        try:
            record = run_investigation(raw, toolkit)
            payload = record.model_dump(mode="json")
            problems = validate_case_record(payload, toolkit.known_ids())
            out = settings.cases_dir / f"{case_id}.json"
            out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            elapsed = time.perf_counter() - started
            report["runtime_statistics"]["per_case_s"][case_id] = round(elapsed, 3)
            report["tool_call_statistics"]["per_case"][case_id] = record.tool_calls
            report["token_statistics"]["per_case"][case_id] = record.tokens
            report["tool_call_statistics"]["total"] += record.tool_calls
            report["token_statistics"]["total"] += record.tokens
            if problems:
                report["validation_failures"].append({"case_id": case_id, "errors": problems})
                logging.error("%s validation failed: %s", case_id, problems)
            else:
                report["cases_successful"] += 1
                logging.info("%s ok p=%.2f verdict=%s pattern=%s", case_id, record.case.fraud_probability, record.case.verdict, record.case.pattern)
        except Exception as exc:  # noqa: BLE001
            logging.exception("Failed %s", case_id)
            report["error_messages"].append({"case_id": case_id, "error": str(exc)})

    report["runtime_statistics"]["total_s"] = round(time.perf_counter() - t0, 3)
    report_path = settings.cases_dir / "benchmark_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    logging.info("Wrote %s", report_path)
    return 0 if not report["error_messages"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
