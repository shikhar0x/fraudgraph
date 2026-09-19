# Project Memory — Agentic Fraud Investigation (TigerGraph HHGoa Task 4)

**How to use this file**: paste this whole file into an AI agent's context at the start of any new session on this project, instead of re-explaining the project from scratch. Update it at the end of every session or milestone (see rules.md Section 6). Keep entries short and factual — this is a log, not a report.

---

## Project snapshot

- Challenge: TigerGraph Agentic Fraud Investigation, HHGoa Task 4
- Team: 3 people (see phases.md for role assignments)
- Deadline: 7 days from kickoff; Day 6 is the real internal deadline, Day 7 is deliverables-only
- Repo: [add GitHub link once created]

## Key decisions log

*(dated, one line each, newest last — do not delete old entries, this is a history)*

- 2026-09-19 — Dataset README reviewed. Answer format, fraud policy, and graph schema are now LOCKED per the README — not our own draft. `architecture.md` Section 4 (contracts) and 5.1/5.2 (schema/policy) updated to match exactly. Do not deviate from field names/enum values — they're scored against a hidden key.
- 2026-09-19 — `transactions.csv` (708MB, 590,742 rows) confirmed too large to hand to any LLM as raw text. It goes in `data/raw/` (gitignored) and is only accessed via TigerGraph after ingestion, or via targeted GSQL/pandas queries — never pasted into a prompt.
- 2026-09-19 — Confirmed case output is one JSON file per case (`cases/<case_id>.json`), 20 files total, matching `case_pack.csv`'s 20 rows exactly (HHG-001 through HHG-020).

## Current state by module

### Data Layer / GSQL (Person 1)
- Schema status: design locked (see architecture.md 5.1), not yet implemented in TigerGraph
- Data on hand: `identity.csv` (144,432 rows), `closed_cases_history.csv` (5,565 rows), `case_pack.csv` (20 rows) — all confirmed and inspected. `transactions.csv` (708MB) not yet downloaded into `data/raw/`
- GSQL queries written: none yet
- MCP server status: not started

### GraphRAG / Agent Reasoning (Person 2)
- Evidence bundle assembly: not started
- LangGraph state machine: not started
- Confidence/branch logic: not started

### Actions, Memory & UI (Person 3)
- Mock action layer: not started
- Case memory write/retrieve: not started
- UI: not started

## Contracts currently in effect

*(copy the exact current versions from architecture.md Section 4 here whenever they change, so this file is self-contained)*

- Evidence Bundle: see architecture.md 4.1
- Case Record: see architecture.md 4.2
- Action Request: see architecture.md 4.3

## Known issues / blockers

*(one line each; move to "resolved" once fixed, don't delete)*

- none logged yet

## Resolved issues (history)

- none yet

## Benchmark run status

- 20 benchmark cases: not yet run
- Last full run date: —
- Known failure cases: —

## Next actions

*(short list, updated at end of each session — this is the first thing the next session should read)*

- Complete Day 0 setup per projectrequirements.md
- Confirm dataset README read by all three, format agreed
