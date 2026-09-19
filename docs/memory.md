# Project Memory — Agentic Fraud Investigation (TigerGraph HHGoa Task 4)

**How to use this file**: paste this whole file into an AI agent's context at the start of any new session on this project, instead of re-explaining the project from scratch. Update it at the end of every session or milestone (see rules.md Section 6). Keep entries short and factual — this is a log, not a report.

---

## Project snapshot

- Challenge: TigerGraph Agentic Fraud Investigation, HHGoa Task 4
- Team: 3 people (see phases.md for role assignments)
- Deadline: 7 days from kickoff; Day 6 is the real internal deadline, Day 7 is deliverables-only
- Repo: fraudgraph (local: ~/Desktop/fraudgraph) — [add GitHub link here]
- Shikhar's role: Person 3 — Actions, Memory & UI Lead

## Key decisions log

*(dated, one line each, newest last — do not delete old entries, this is a history)*

- 2026-09-19 — Dataset README reviewed. Answer format, fraud policy, and graph schema are now LOCKED per the README — not our own draft. `architecture.md` Section 4 (contracts) and 5.1/5.2 (schema/policy) updated to match exactly. Do not deviate from field names/enum values — they're scored against a hidden key.
- 2026-09-19 — `transactions.csv` (708MB, 590,742 rows) confirmed too large to hand to any LLM as raw text. It goes in `data/raw/` (gitignored) and is only accessed via TigerGraph after ingestion, or via targeted GSQL/pandas queries — never pasted into a prompt.
- 2026-09-19 — Confirmed case output is one JSON file per case (`cases/<case_id>.json`), 20 files total, matching `case_pack.csv`'s 20 rows exactly (HHG-001 through HHG-020).
- 2026-09-19 — Renamed `outputs/` to `cases/` to match the submission spec exactly; fixed `.gitignore` which had been incorrectly ignoring the JSON files it needed to keep.
- 2026-09-19 — Role assignment locked: Shikhar = Person 3 (Actions, Memory & UI Lead), based on direct architectural overlap with his prior Nexa project (deterministic rule layer + LLM proposal + confirmation gating on destructive actions).
- 2026-09-19 — `transactions.csv` downloaded and placed in `data/raw/`; all four dataset files now present locally.

## Current state by module

### Data Layer / GSQL (Person 1)
- Schema status: design locked (see architecture.md 5.1), not yet implemented in TigerGraph
- Data on hand: all four files present in `data/raw/` — `identity.csv` (144,432 rows), `closed_cases_history.csv` (5,565 rows), `case_pack.csv` (20 rows), `transactions.csv` (708MB, 590,742 rows)
- GSQL queries written: none yet
- MCP server status: not started

### GraphRAG / Agent Reasoning (Person 2)
- Evidence bundle assembly: not started
- LangGraph state machine: not started
- Confidence/branch logic: not started

### Actions, Memory & UI (Person 3)
- Day 1 complete: Case Record schema (`case_memory/schema.py`), Action Request schema (`actions/schema.py`), both matching architecture.md 4.2/4.3 exactly
- Policy rule engine: R1, R2, R3 implemented in `actions/policy/rules.py`; R4-R10 still TODO (Day 2)
- Mock action executor: `actions/mock_actions/executor.py` — logs/simulates only, no real integrations, per challenge brief
- UI: wireframe sketched in `docs/ui_wireframe.md`, no build yet (build target Day 5)
- Validated by `tests/test_day1_person3.py` — schema + Action Request + R2 all pass together

## Contracts currently in effect

*(copy the exact current versions from architecture.md Section 4 here whenever they change, so this file is self-contained)*

- Evidence Bundle: see architecture.md 4.1
- Case Record: see architecture.md 4.2 — implemented in `case_memory/schema.py`
- Action Request: see architecture.md 4.3 — implemented in `actions/schema.py`

## Known issues / blockers

*(one line each; move to "resolved" once fixed, don't delete)*

- none logged yet

## Resolved issues (history)

- `.gitignore` was ignoring `outputs/*.json`, which would have silently excluded the 20 graded submission files — caught before first real commit to that folder, fixed by renaming to `cases/` and removing the ignore rule.

## Benchmark run status

- 20 benchmark cases: not yet run
- Last full run date: —
- Known failure cases: —

## Next actions

*(short list, updated at end of each session — this is the first thing the next session should read)*

- Confirm Person 1 and Person 2's actual Day 1 progress — TigerGraph schema live? Evidence bundle design started?
- Day 2: Person 3 finishes rules R4-R10 in `actions/policy/rules.py`, each with its own test case
- Day 2 integration point (per phases.md): Person 2 demonstrates a real Evidence Bundle for one sample transaction generated only from Person 1's tools, not hand-written test data
