"""python -m app.ingest"""
from __future__ import annotations

import argparse
import logging

from app.config import get_settings
from graph.factory import reset_provider_cache
from graph.ingestion.pipeline import configure_logging, ingest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest HHGOA dataset into the local graph / export CSVs")
    parser.add_argument("--export", action="store_true", help="Also write slim CSVs for TigerGraph loading jobs")
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    store = ingest(settings, export=args.export, persist=not args.no_persist)
    reset_provider_cache()
    logging.getLogger("fraudgraph.ingest").info(
        "Done. txns=%s cards=%s customers=%s closed=%s pack=%s mock=%s",
        len(store.transactions),
        len(store.cards),
        len(store.customers),
        len(store.closed_cases),
        len(store.case_pack),
        store.mock_mode,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
