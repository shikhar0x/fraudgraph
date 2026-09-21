"""Optional MCP server exposing investigation graph tools.

Run: python -m graph.mcp_server.server
If the `mcp` package is not installed, this module still documents the tool
list and can be imported. The agent uses GraphToolkit in-process by default.
"""
from __future__ import annotations

import json
import sys

from graph.factory import get_provider
from graph.mcp_server.tools import TOOL_SPECS, dispatch_tool


def main() -> None:
    provider = get_provider()
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        _stdio_loop(provider)
        return
    mcp = FastMCP("fraudgraph-graph")
    for spec in TOOL_SPECS:
        name = spec["name"]

        def _make(n: str):
            def _tool(**kwargs):
                return dispatch_tool(provider, n, kwargs)

            _tool.__name__ = n
            _tool.__doc__ = spec["description"]
            return _tool

        mcp.tool()(_make(name))
    mcp.run()


def _stdio_loop(provider) -> None:
    """Minimal JSON-lines fallback so the process is still callable without mcp."""
    sys.stderr.write("mcp package not installed; serving JSON-lines tools on stdin/stdout\n")
    sys.stderr.flush()
    print(json.dumps({"tools": TOOL_SPECS}), flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        try:
            result = dispatch_tool(provider, req["name"], req.get("arguments") or {})
            print(json.dumps({"ok": True, "result": result}, default=str), flush=True)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": str(exc)}), flush=True)


if __name__ == "__main__":
    main()
