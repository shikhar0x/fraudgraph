"""Select local vs TigerGraph provider from settings."""
from __future__ import annotations

import logging
from pathlib import Path

from app.config import Settings, get_settings
from graph.local_store import LocalGraphStore

logger = logging.getLogger("fraudgraph.factory")

_CACHE: dict[str, object] = {}


def default_pickle_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.processed_dir / "local_graph.pkl"


def load_or_empty_local(settings: Settings | None = None) -> LocalGraphStore:
    settings = settings or get_settings()
    path = default_pickle_path(settings)
    if path.exists():
        try:
            return LocalGraphStore.load(path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not load %s: %s", path, exc)
    store = LocalGraphStore()
    return store


def get_provider(settings: Settings | None = None, *, force_local: bool = False):
    settings = settings or get_settings()
    key = f"{settings.mode}:{force_local}"
    if key in _CACHE:
        return _CACHE[key]
    local = load_or_empty_local(settings)
    if force_local or settings.mode != "tigergraph" or not settings.tg_host:
        local.mock_mode = True
        _CACHE[key] = local
        return local
    try:
        from graph.tigergraph_store import TigerGraphStore, connect_tigergraph

        conn = connect_tigergraph(settings)
        store = TigerGraphStore(conn, fallback=local)
        _CACHE[key] = store
        return store
    except Exception as exc:  # noqa: BLE001
        logger.warning("TigerGraph unavailable (%s); using local store", exc)
        local.mock_mode = True
        _CACHE[key] = local
        return local


def reset_provider_cache() -> None:
    _CACHE.clear()
