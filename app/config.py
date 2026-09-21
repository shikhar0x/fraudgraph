"""Runtime configuration. Secrets come from the environment / .env — never hardcoded."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    env_path = ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
    else:
        load_dotenv(ROOT / ".env.example", override=False)


_load_env()


def _path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    p = Path(value)
    return p if p.is_absolute() else (ROOT / p)


@dataclass(frozen=True)
class Settings:
    mode: str
    data_dir: Path
    processed_dir: Path
    cases_dir: Path
    fallback_case_pack: Path
    tg_host: str
    tg_graphname: str
    tg_username: str
    tg_password: str
    tg_api_token: str
    tg_secret: str
    tg_restpp_port: str
    tg_gs_port: str
    mcp_command: str
    mcp_args: str
    mcp_url: str
    llm_provider: str
    llm_api_key: str
    llm_model: str
    llm_base_url: str
    llm_max_tokens: int
    log_level: str

    @property
    def live_tigergraph(self) -> bool:
        return self.mode == "tigergraph"

    @property
    def mock_mode(self) -> bool:
        return not self.live_tigergraph

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider not in {"", "none", "off"} and bool(self.llm_api_key)


def get_settings() -> Settings:
    return Settings(
        mode=os.getenv("FRAUDGRAPH_MODE", "local").strip().lower(),
        data_dir=_path(os.getenv("DATA_DIR"), ROOT / "data" / "raw"),
        processed_dir=_path(os.getenv("PROCESSED_DIR"), ROOT / "data" / "processed"),
        cases_dir=_path(os.getenv("CASES_DIR"), ROOT / "cases"),
        fallback_case_pack=ROOT / "data" / "case_pack.fallback.csv",
        tg_host=os.getenv("TG_HOST", ""),
        tg_graphname=os.getenv("TG_GRAPHNAME", "FraudGraph"),
        tg_username=os.getenv("TG_USERNAME", "tigergraph"),
        tg_password=os.getenv("TG_PASSWORD", ""),
        tg_api_token=os.getenv("TG_API_TOKEN", ""),
        tg_secret=os.getenv("TG_SECRET", ""),
        tg_restpp_port=os.getenv("TG_RESTPP_PORT", ""),
        tg_gs_port=os.getenv("TG_GS_PORT", ""),
        mcp_command=os.getenv("TIGERGRAPH_MCP_COMMAND", ""),
        mcp_args=os.getenv("TIGERGRAPH_MCP_ARGS", "-vv"),
        mcp_url=os.getenv("TIGERGRAPH_MCP_URL", ""),
        llm_provider=os.getenv("LLM_PROVIDER", "none").strip().lower(),
        llm_api_key=os.getenv("LLM_API_KEY", "") or os.getenv("OPENAI_API_KEY", "") or os.getenv("GROQ_API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", ""),
        llm_base_url=os.getenv("LLM_BASE_URL", ""),
        llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "800")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


RAW_FILES = {
    "transactions": "transactions.csv",
    "identity": "identity.csv",
    "closed_cases": "closed_cases_history.csv",
    "case_pack": "case_pack.csv",
}

TXN_REQUIRED_HEADERS = [
    "TransactionID",
    "TransactionAmt",
    "customer_id",
    "ts",
    "channel",
    "risk_score",
]
TXN_OPTIONAL_HEADERS = [
    "TransactionDT",
    "ProductCD",
    "card1",
    "card2",
    "card3",
    "card4",
    "card5",
    "card6",
    "addr1",
    "addr2",
    "dist1",
    "dist2",
    "P_emaildomain",
    "R_emaildomain",
    "card_id",
    "C1",
    "C13",
    "C14",
    "D1",
    "M4",
    "M5",
    "M6",
]
IDENTITY_REQUIRED_HEADERS = ["TransactionID"]
IDENTITY_OPTIONAL_HEADERS = [
    "id_15",
    "id_23",
    "id_30",
    "id_31",
    "id_33",
    "id_34",
    "DeviceType",
    "DeviceInfo",
    "id_01",
    "id_02",
    "id_03",
]
CLOSED_REQUIRED_HEADERS = [
    "case_id",
    "customer_id",
    "card_id",
    "outcome",
    "pattern",
]
CASE_PACK_REQUIRED_HEADERS = [
    "case_id",
    "opened_at",
    "trigger_type",
    "trigger_text",
    "flagged_txn_id",
    "card_id",
    "customer_id",
]
