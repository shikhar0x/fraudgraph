from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from graph.factory import reset_provider_cache
from graph.ingestion.pipeline import ingest
from graph.local_store import LocalGraphStore


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_store(tmp_path, monkeypatch) -> LocalGraphStore:
    reset_provider_cache()
    monkeypatch.setenv("DATA_DIR", str(FIXTURES))
    monkeypatch.setenv("PROCESSED_DIR", str(tmp_path))
    monkeypatch.setenv("FRAUDGRAPH_MODE", "local")
    from app.config import Settings as SettingsCls

    s = SettingsCls(
        mode="local",
        data_dir=FIXTURES,
        processed_dir=tmp_path,
        cases_dir=tmp_path / "cases",
        fallback_case_pack=ROOT / "data" / "case_pack.fallback.csv",
        tg_host="",
        tg_graphname="FraudGraph",
        tg_username="",
        tg_password="",
        tg_api_token="",
        tg_secret="",
        tg_restpp_port="",
        tg_gs_port="",
        mcp_command="",
        mcp_args="",
        mcp_url="",
        llm_provider="none",
        llm_api_key="",
        llm_model="",
        llm_base_url="",
        llm_max_tokens=800,
        log_level="INFO",
    )
    store = ingest(s, persist=False)
    yield store
    reset_provider_cache()
