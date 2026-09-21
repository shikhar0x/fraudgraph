"""Graph capabilities exposed as agent tools.

These wrap the GraphProvider. They can be served over MCP (server.py) or
called in-process by GraphToolkit — the agent never reads the raw 590k CSV.
"""
from __future__ import annotations

from typing import Any, Callable

TOOL_SPECS = [
    {
        "name": "get_transaction",
        "description": "Return attributes of a single transaction by ID.",
        "parameters": {"txn_id": "string"},
    },
    {
        "name": "card_history",
        "description": "Recent transactions for a card, newest first.",
        "parameters": {"card_id": "string", "limit": "int"},
    },
    {
        "name": "customer_history",
        "description": "Recent transactions across all cards a customer owns.",
        "parameters": {"customer_id": "string", "limit": "int"},
    },
    {
        "name": "transaction_window",
        "description": "Transactions on the same card within +/- hours of a flagged txn.",
        "parameters": {"txn_id": "string", "hours": "float"},
    },
    {
        "name": "device_neighbors",
        "description": "Cards, customers, and transactions sharing a device profile.",
        "parameters": {"device_id": "string"},
    },
    {
        "name": "region_neighbors",
        "description": "Cards that billed in a given addr1 region.",
        "parameters": {"region": "string"},
    },
    {
        "name": "connected_cards",
        "description": "Other cards linked via device, email, or rare region.",
        "parameters": {"card_id": "string"},
    },
    {
        "name": "detect_card_testing",
        "description": "3+ small online auths in ~1h followed by a larger purchase.",
        "parameters": {"card_id": "string", "around_txn_id": "string"},
    },
    {
        "name": "detect_cnp",
        "description": "Card-not-present burst / history divergence.",
        "parameters": {"card_id": "string", "around_txn_id": "string"},
    },
    {
        "name": "detect_new_device_cnp",
        "description": "CNP combined with New device / proxy.",
        "parameters": {"card_id": "string", "around_txn_id": "string"},
    },
    {
        "name": "detect_out_of_region",
        "description": "Unusual billing-region activity vs home region.",
        "parameters": {"card_id": "string", "around_txn_id": "string"},
    },
    {
        "name": "detect_account_takeover",
        "description": "Mixed-channel + device/identity anomalies.",
        "parameters": {"card_id": "string", "around_txn_id": "string"},
    },
    {
        "name": "detect_shared_origin",
        "description": "Shared device / email / region across cards.",
        "parameters": {"card_id": "string", "around_txn_id": "string"},
    },
    {
        "name": "related_closed_cases",
        "description": "Historical ClosedCase vertices related to this card/customer/device.",
        "parameters": {"card_id": "string", "customer_id": "string", "device_id": "string", "pattern": "string"},
    },
    {
        "name": "write_case",
        "description": "Write an investigation case vertex and edges back to the graph.",
        "parameters": {"payload": "object"},
    },
]


def dispatch_tool(provider: Any, name: str, arguments: dict[str, Any]) -> Any:
    if not hasattr(provider, name):
        raise ValueError(f"unknown tool {name}")
    fn: Callable = getattr(provider, name)
    return fn(**arguments)
