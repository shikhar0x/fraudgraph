"""Deploy schema + queries to a live TigerGraph instance. python -m app.setup_graph"""
from __future__ import annotations

import argparse

from app.config import ROOT, get_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create FraudGraph schema and install GSQL queries")
    parser.add_argument("--schema-only", action="store_true")
    parser.add_argument("--install-queries", action="store_true")
    parser.add_argument("--drop", action="store_true", help="DROP ALL first (destructive)")
    args = parser.parse_args(argv)
    settings = get_settings()
    if not settings.tg_host:
        print("TG_HOST is not set. Copy .env.example to .env and configure TigerGraph.")
        print("Schema files (no live connection required):")
        print(f"  {ROOT / 'graph' / 'schema' / 'schema.gsql'}")
        print(f"  {ROOT / 'graph' / 'schema' / 'schema_change.gsql'}")
        print(f"  {ROOT / 'graph' / 'schema' / 'load.gsql'}")
        print(f"  {ROOT / 'graph' / 'gsql' / 'investigation.gsql'}")
        return 0
    from graph.tigergraph_store import connect_tigergraph

    conn = connect_tigergraph(settings)
    if args.drop:
        print(conn.gsql("USE GLOBAL\nDROP ALL"))
    schema = (ROOT / "graph" / "schema" / "schema.gsql").read_text(encoding="utf-8")
    print(conn.gsql(schema))
    if args.schema_only:
        return 0
    load = (ROOT / "graph" / "schema" / "load.gsql").read_text(encoding="utf-8")
    print(conn.gsql(load))
    if args.install_queries or not args.schema_only:
        queries = (ROOT / "graph" / "gsql" / "investigation.gsql").read_text(encoding="utf-8")
        print(conn.gsql(queries))
        print(conn.gsql("USE GRAPH FraudGraph\nINSTALL QUERY ALL"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
