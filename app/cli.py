"""python -m app --help"""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app", description="FraudGraph CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest", help="Load CSVs into the local graph")
    sub.add_parser("setup-graph", help="Deploy GSQL schema to TigerGraph")
    p_bench = sub.add_parser("run-benchmark", help="Investigate case-pack cases")
    p_bench.add_argument("--case", action="append", dest="cases")
    p_bench.add_argument("--limit", type=int, default=0)
    sub.add_parser("ui", help="Launch Streamlit UI")
    args, rest = parser.parse_known_args(argv)

    if args.cmd == "ingest":
        from app.ingest import main as ingest_main

        return ingest_main(rest)
    if args.cmd == "setup-graph":
        from app.setup_graph import main as setup_main

        return setup_main(rest)
    if args.cmd == "run-benchmark":
        from app.run_benchmark import main as bench_main

        extra: list[str] = []
        if args.cases:
            for c in args.cases:
                extra.extend(["--case", c])
        if args.limit:
            extra.extend(["--limit", str(args.limit)])
        extra.extend(rest)
        return bench_main(extra)
    if args.cmd == "ui":
        import os
        from pathlib import Path

        os.execvp(
            sys.executable,
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(Path(__file__).with_name("ui.py")),
                "--server.address",
                os.getenv("STREAMLIT_SERVER_ADDRESS", "0.0.0.0"),
                "--server.port",
                os.getenv("STREAMLIT_SERVER_PORT", "8501"),
                "--server.headless",
                "true",
            ],
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
