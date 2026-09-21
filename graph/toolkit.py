"""Agent-facing graph tools with per-investigation caching and call counts."""
from __future__ import annotations

from typing import Any


class GraphToolkit:
    def __init__(self, provider: Any) -> None:
        self.provider = provider
        self.calls = 0
        self.log: list[str] = []
        self._cache: dict[tuple, Any] = {}

    @property
    def mock_mode(self) -> bool:
        return bool(getattr(self.provider, "mock_mode", True))

    def _call(self, name: str, **kwargs: Any) -> Any:
        key = (name, tuple(sorted((k, _freeze(v)) for k, v in kwargs.items())))
        if key in self._cache:
            return self._cache[key]
        fn = getattr(self.provider, name)
        self.calls += 1
        self.log.append(name)
        result = fn(**kwargs)
        self._cache[key] = result
        return result

    def get_transaction(self, txn_id: str) -> dict[str, Any] | None:
        return self._call("get_transaction", txn_id=str(txn_id))

    def get_card(self, card_id: str) -> dict[str, Any] | None:
        return self._call("get_card", card_id=str(card_id))

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        return self._call("get_customer", customer_id=str(customer_id))

    def card_history(self, card_id: str, limit: int = 200) -> list[dict[str, Any]]:
        return self._call("card_history", card_id=str(card_id), limit=limit)

    def customer_history(self, customer_id: str, limit: int = 400) -> list[dict[str, Any]]:
        return self._call("customer_history", customer_id=str(customer_id), limit=limit)

    def transaction_window(self, txn_id: str, hours: float = 24.0) -> list[dict[str, Any]]:
        return self._call("transaction_window", txn_id=str(txn_id), hours=hours)

    def device_neighbors(self, device_id: str) -> dict[str, Any]:
        return self._call("device_neighbors", device_id=str(device_id))

    def region_neighbors(self, region: str) -> dict[str, Any]:
        return self._call("region_neighbors", region=str(region))

    def connected_cards(self, card_id: str) -> dict[str, Any]:
        return self._call("connected_cards", card_id=str(card_id))

    def detect_card_testing(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return self._call("detect_card_testing", card_id=str(card_id), around_txn_id=around_txn_id)

    def detect_cnp(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return self._call("detect_cnp", card_id=str(card_id), around_txn_id=around_txn_id)

    def detect_new_device_cnp(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return self._call("detect_new_device_cnp", card_id=str(card_id), around_txn_id=around_txn_id)

    def detect_out_of_region(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return self._call("detect_out_of_region", card_id=str(card_id), around_txn_id=around_txn_id)

    def detect_account_takeover(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return self._call("detect_account_takeover", card_id=str(card_id), around_txn_id=around_txn_id)

    def detect_shared_origin(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        return self._call("detect_shared_origin", card_id=str(card_id), around_txn_id=around_txn_id)

    def detect_recurring(self, card_id: str, around_txn_id: str | None = None) -> dict[str, Any]:
        if hasattr(self.provider, "detect_recurring"):
            return self._call("detect_recurring", card_id=str(card_id), around_txn_id=around_txn_id)
        from graph.local_store import parse_ts
        from graph.patterns import detect_recurring_legitimate

        hist = self.card_history(card_id)
        rows = []
        for r in hist:
            item = dict(r)
            item["ts"] = parse_ts(item.get("ts"))
            rows.append(item)
        self.calls += 1
        self.log.append("detect_recurring")
        return detect_recurring_legitimate(rows, around_txn_id)

    def related_closed_cases(
        self,
        card_id: str,
        customer_id: str,
        device_id: str | None = None,
        pattern: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            "related_closed_cases",
            card_id=str(card_id),
            customer_id=str(customer_id),
            device_id=device_id,
            pattern=pattern,
        )

    def search_closed_cases(self, query: str, pattern: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        return self._call("search_closed_cases", query=query, pattern=pattern, limit=limit)

    def write_case(self, payload: dict[str, Any]) -> str:
        return self._call("write_case", payload=payload)

    def known_ids(self) -> dict[str, set[str]]:
        return self.provider.known_ids()

    def dataset_status(self) -> dict[str, Any]:
        return self.provider.dataset_status()


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value
