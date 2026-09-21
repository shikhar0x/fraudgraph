from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent
SCHEMA_GSQL = SCHEMA_DIR / "schema.gsql"
LOAD_GSQL = SCHEMA_DIR / "load.gsql"
