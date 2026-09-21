# Project Memory — Agentic Fraud Investigation (TigerGraph HHGoa Task 4)

**How to use this file**: paste this whole file into an AI agent's context at the start of any new session on this project, instead of re-explaining the project from scratch. Update it at the end of every session or milestone (see rules.md Section 6). Keep entries short and factual — this is a log, not a report.

---

## Project snapshot

- Challenge: TigerGraph Agentic Fraud Investigation, HHGoa Task 4
- Team: originally 3 people (see phases.md); implementation completed as a unified effort (ownership boundaries not preserved for remaining work)
- Deadline: 7 days from kickoff; Day 6 is the real internal deadline, Day 7 is deliverables-only
- Repo: fraudgraph
- Shikhar's role: Person 3 — Actions, Memory & UI Lead (historical)

## Key decisions log

*(dated, one line each, newest last — do not delete old entries, this is a history)*

- 2026-09-19 — Dataset README reviewed. Answer format, fraud policy, and graph schema are now LOCKED per the README — not our own draft. `architecture.md` Section 4 (contracts) and 5.1/5.2 (schema/policy) updated to match exactly. Do not deviate from field names/enum values — they're scored against a hidden key.
- 2026-09-19 — `transactions.csv` (708MB, 590,742 rows) confirmed too large to hand to any LLM as raw text. It goes in `data/raw/` (gitignored) and is only accessed via TigerGraph after ingestion, or via targeted GSQL/pandas queries — never pasted into a prompt.
- 2026-09-19 — Confirmed case output is one JSON file per case (`cases/<case_id>.json`), 20 files total, matching `case_pack.csv`'s 20 rows exactly (HHG-001 through HHG-020).
- 2026-09-19 — Renamed `outputs/` to `cases/` to match the submission spec exactly; fixed `.gitignore` which had been incorrectly ignoring the JSON files it needed to keep.
- 2026-09-19 — Role assignment locked: Shikhar = Person 3 (Actions, Memory & UI Lead), based on direct architectural overlap with his prior Nexa project (deterministic rule layer + LLM proposal + confirmation gating on destructive actions).
- 2026-09-19 — `transactions.csv` downloaded and placed in `data/raw/`; all four dataset files now present locally.
- 2026-09-21 — Unified implementation: graph schema + GSQL, chunked ingestion, local/TigerGraph adapters, MCP tool layer, GraphRAG Evidence Bundle, LangGraph investigation loop, confidence/stopping, simulated evidence requests, R1–R10 + routing, mock actions, case memory, SAR, strict validator, Streamlit UI, pytest suite.
- 2026-09-21 — Dual mode: `FRAUDGRAPH_MODE=local` (default) vs `tigergraph`. LLM optional for prose only.
- 2026-09-21 — This sandbox has no `data/raw/*.csv` and no TigerGraph credentials. Case pack fallback from the dataset README is used. Benchmark JSONs are pipeline-generated, not hand-written; `mock_mode` is recorded in `cases/benchmark_report.json`. Do not claim hidden-key accuracy.

## Current state by module

### Data Layer / GSQL
- Schema: `graph/schema/schema.gsql` (+ `schema_change.gsql`, `load.gsql`) — deployable; not applied to a live cluster in this environment
- Ingestion: `graph/ingestion/pipeline.py` — chunked, header-validated, rerunnable; exports slim CSVs for loading jobs
- Local store: `graph/local_store.py` indexes whatever CSVs are present and seeds the public 20-row case pack
- GSQL investigation queries: `graph/gsql/investigation.gsql` (retrieval + card-testing path + write-back)
- Pattern detectors also run in Python on retrieved windows so local == live evidence shape
- MCP: in-process `GraphToolkit` + `python -m graph.mcp_server.server`

### GraphRAG / Agent Reasoning
- Evidence bundle: `agent/graphrag/bundle.py` (architecture 4.1)
- LangGraph: `agent/reasoning/graph.py` — multi-step loop with evidence requests
- Confidence: `agent/reasoning/confidence.py` (heuristic, not calibrated)
- Evidence-request simulation: `agent/reasoning/evidence_requests.py`

### Actions, Memory & UI
- Case Record / Action Request schemas retained
- Policy: R1–R10 + deterministic routing (`actions/policy/`)
- Mock executor: auto executes (logged); L1/L2 pending
- SAR: `actions/sar.py` — `FILE_REPORT` ↔ `sar.file`
- Case memory write/retrieve: `case_memory/writer.py`, `case_memory/retrieval.py`
- UI: `app/ui.py` Streamlit over `cases/*.json`
- Validator: `validation/validator.py`

## Contracts currently in effect

- Evidence Bundle: see architecture.md 4.1
- Case Record: see architecture.md 4.2 — implemented in `case_memory/schema.py`
- Action Request: see architecture.md 4.3 — implemented in `actions/schema.py`

## Known issues / blockers

- This checkout has no `transactions.csv` / `identity.csv` / `closed_cases_history.csv` in `data/raw/` — graph neighbourhoods beyond the 20 flagged txns are empty unless those files are added and `python -m app.ingest` is re-run.
- No live TigerGraph or LLM key in this environment — local store + template narration.
- Fraud probability is heuristic, not statistically calibrated.

## Resolved issues (history)

- `.gitignore` was ignoring `outputs/*.json`, which would have silently excluded the 20 graded submission files — caught before first real commit to that folder, fixed by renaming to `cases/` and removing the ignore rule.
- R4–R10 were stubs — implemented with tests.
- Agent / GraphRAG / GSQL / MCP / UI were empty packages — implemented.
- README “setup to be filled in” — replaced with working instructions.

## Benchmark run status

- 20 benchmark cases: generated 2026-09-21 via `python -m app.run_benchmark` (local/mock graph, fallback case pack)
- Outputs: `cases/HHG-001.json` … `cases/HHG-020.json`, `cases/benchmark_report.json`
- Validator: 20/20 pass the contract checker
- Known failure cases: none at the contract layer. Pattern detection on the 20 is limited without `transactions.csv`.
- Last full run date: 2026-09-21
- Hidden-key accuracy: unknown / not claimed

## Next actions

- Place the four dataset files in `data/raw/` and re-run ingest + benchmark for full graph evidence
- Point `FRAUDGRAPH_MODE=tigergraph` at a Savanna/CE instance and run `python -m app.setup_graph`
- Optional: set `LLM_API_KEY` for SAR/summary prose
