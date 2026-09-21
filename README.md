# FraudGraph

Agentic fraud investigation system for **TigerGraph × Hacker House Goa Task 4**.

A LangGraph investigation loop gathers **graph evidence** (TigerGraph or a local pandas-backed store), grounds it with **GraphRAG** (graph facts + fraud-policy / typology text), computes an explicit **fraud probability**, requests more evidence when the stopping policy says so, then runs a **deterministic policy engine (R1–R10)** for next-best actions, SAR filing, mock execution, and case-memory write-back.

The LLM is used only for summary / SAR prose when an API key is configured. Verdicts, probabilities, routes, and actions are **not** LLM decisions.

## Architecture

See `docs/architecture.md` for locked interface contracts. Layers:

1. **Data / graph** — schema, chunked ingestion, GSQL pattern queries, local + TigerGraph providers
2. **MCP** — the same investigation tools exposed in-process and as an optional MCP server
3. **GraphRAG** — Evidence Bundle (`graph_facts`, `policy_context`, `typology_matches`, `similar_prior_cases`)
4. **Agent** — LangGraph: trigger → gather → assess → confidence check ⇄ evidence request → final decision → policy → mock actions → case memory
5. **Policy** — R1–R10 + auto/L1/L2 routing (deterministic)
6. **Case memory** — write InvestigationCase vertices/edges; retrieve `CC-*` closed cases
7. **UI** — Streamlit case viewer over real `cases/*.json`

```
Trigger → LangGraph agent
            │ tools
            ▼
     GraphToolkit ──► Local store  or  TigerGraph (GSQL / MCP)
            │
            ▼
     GraphRAG evidence bundle
            │
            ▼
     Confidence / evidence-request loop
            │
            ▼
     Policy engine R1–R10 → mock actions → case memory → cases/HHG-xxx.json
```

### Graph model

**Vertices:** `Customer`, `Card`, `Transaction`, `DeviceProfile`, `EmailDomain`, `BillingRegion`, `ClosedCase`  
plus `InvestigationCase` (agent write-back) and `PolicyChunk` (GraphRAG docs).

**Edges:** `OWNS`, `MADE`, `FROM_DEVICE`, `PURCHASER_EMAIL`, `BILLED_IN`, `NEXT`, `INVOLVES`, `ON_CARD`, `CONNECTED_TO` (and named reverse edges).

GSQL: `graph/schema/schema.gsql`, `graph/schema/load.gsql`, `graph/gsql/investigation.gsql`.

## Modes

| Mode | When | Graph | LLM |
|---|---|---|---|
| **Live** | `FRAUDGRAPH_MODE=tigergraph` and `TG_HOST` set | pyTigerGraph + installed GSQL | optional |
| **Local / mock** (default) | no TigerGraph | pandas/dict store, same tool contract | optional (templates if unset) |

The UI shows a banner when `benchmark_report.json` has `mock_mode: true`. Local results are **not** claimed as hidden-answer-key accuracy.

## Installation

Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit; never commit .env
```

## Dataset

Do **not** commit raw data. Place files in `data/raw/`:

| File | Role |
|---|---|
| `transactions.csv` | ~590k rows / ~708 MB — **streamed**, never sent to an LLM |
| `identity.csv` | online device / proxy fields |
| `closed_cases_history.csv` | case memory seed (`CC-*`) |
| `case_pack.csv` | the 20 exam cases |

`data/case_pack.fallback.csv` is the public 20-row pack from the dataset README so the pipeline can run without the dump.

```bash
python -m app.ingest              # local graph pickle in data/processed/
python -m app.ingest --export     # also slim CSVs for TigerGraph loading jobs
```

Ingestion validates presence/headers, chunks large CSVs, builds vertices/edges (including `NEXT` on card timelines), loads closed cases and the case pack, and is rerunnable.

## TigerGraph setup

1. Create a workspace (Savanna or Community Edition).
2. Fill `.env`: `TG_HOST`, `TG_GRAPHNAME=FraudGraph`, token or username/password.
3. `FRAUDGRAPH_MODE=tigergraph`
4. Deploy schema and queries:

```bash
python -m app.setup_graph
# or paste graph/schema/schema.gsql then graph/gsql/investigation.gsql
# then INSTALL QUERY ALL
```

5. Export and load (avoids millions of REST upserts):

```bash
python -m app.ingest --export
# RUN LOADING JOB load_fraud USING f_customers=..., ...  (see graph/schema/load.gsql)
```

Optional: run the official [tigergraph-mcp](https://github.com/tigergraph/tigergraph-mcp) server. This repo also exposes investigation tools via `python -m graph.mcp_server.server`.

## Run the agent / all 20 cases

```bash
python -m app.run_benchmark           # all 20 → cases/HHG-001.json … HHG-020.json
python -m app.run_benchmark --case HHG-001
python -m app                         # CLI: ingest | setup-graph | run-benchmark | ui
```

Each file matches the dataset **Answer Format** (see `docs/architecture.md` §4.2 and `docs/dataset_readme.md`). A machine-readable run log is written to `cases/benchmark_report.json` (counts, timings, tool/token stats, limitations). We do **not** score against the hidden key.

## UI

```bash
streamlit run app/ui.py --server.address 0.0.0.0 --server.port 8501
# or: python -m app ui
```

Reads real `cases/*.json`: header (id, status, verdict, probability), evidence, pattern/exposure/priors, initial vs final actions with pending L1/L2 approval, SAR only when `sar.file` is true.

## Policy engine (deterministic)

Actions and routes are assigned in Python (`actions/policy/`), not by prompt:

- **R1** verify before block on a weak single signal  
- **R2** customer denies → `BLOCK_CARD` + `CREATE_CASE` (+ `FILE_REPORT` if exposed / shared)  
- **R3** customer confirms → `CLOSE_NO_FRAUD`  
- **R4** no reply → monitor / decline / escalate  
- **R5** card testing  
- **R6** shared origin  
- **R7** disputed but legitimate — never block  
- **R8** uncertain + exposure / conflicts → escalate  
- **R9** undocumented coordinated abuse  
- **R10** never `BLOCK_ALL_CARDS` without two confirmed cards or compromised credentials  

`auto` actions are mock-executed. `L1`/`L2` stay pending human approval. There is no payment processor, messenger, or account-freeze integration.

## Tests

```bash
pytest
```

Coverage includes schema/enums, R1–R10, route validation, safety (`BLOCK_ALL_CARDS`, L1/L2 not auto-executed, no real integrations), case-output/SAR consistency, pattern detectors, and `case → evidence → agent → policy → CaseRecord` with a fixture graph.

## Expected output

`cases/HHG-001.json` … `cases/HHG-020.json` plus `cases/benchmark_report.json`.

Without `transactions.csv`, investigations use the case-pack fields only (risk-score alerts often close as legitimate after simulated customer confirmation; customer-report alerts follow R2 after simulated denial). That is explicit in the report `limitations` list.

## Limitations

- Fraud probability is a documented heuristic, **not** a calibrated probability.
- Risk score is an input, never a verdict.
- Live GSQL is used when TigerGraph is configured; local mode runs the same detectors on retrieved windows.
- Regulatory GraphRAG chunks are internal summaries of policy/SAR structure, not loaded FinCEN PDFs.
- Do not recover labels from the public IEEE-CIS / Kaggle files.

## Demo

1. `pip install -r requirements.txt`
2. `python -m app.ingest`
3. `python -m app.run_benchmark --case HHG-001 --case HHG-003`
4. `streamlit run app/ui.py --server.address 0.0.0.0 --server.port 8501`
5. Select a case; expand evidence; compare initial vs final actions.

## Project docs

- `docs/architecture.md` — contracts  
- `docs/fraud_policy.md` — policy text  
- `docs/dataset_readme.md` — data + answer format  
- `docs/memory.md` — session log  
- `docs/ui_wireframe.md` — UI sketch  
- `.env.example` — configuration  
