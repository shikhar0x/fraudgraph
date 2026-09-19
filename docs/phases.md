# Phases & Ownership — 7-Day Plan, 3 People, Zero Overlap

Rule for this file: each person owns a fixed set of modules for the entire project (see architecture.md Section 2). Nobody edits another person's module files without asking. Integration happens at defined sync points, not by merging into each other's work silently.

Replace "Person 1/2/3" with actual names once assigned — keep the role definitions fixed regardless of who holds them.

## Role definitions (fixed for the whole project)

- **Person 1 — Graph & MCP Lead**: TigerGraph schema, data ingestion, GSQL fraud-pattern queries, TigerGraph MCP server setup and tool exposure.
- **Person 2 — Agent & Reasoning Lead**: GraphRAG evidence assembly, LangGraph agent state machine, confidence/uncertainty logic, explanation generation.
- **Person 3 — Actions, Memory & UI Lead**: mock action layer, policy/approval rules, case memory (write-back + retrieval), UI.

## Day 0 — Setup (all three, together, ~2 hours)

- All: create accounts per projectrequirements.md
- All: read the dataset README together, agree on the case/answer output format as a group — this format is shared by everyone and must not be reinterpreted later by one person alone
- All: agree on the contracts in architecture.md Section 4 (evidence bundle, case record, action request) before anyone writes code against them

## Day 1

- **Person 1**: Load dataset into TigerGraph. Define schema (accounts, transactions, devices, cases, policy docs as nodes/edges). Stand up TigerGraph MCP server, confirm one trivial GSQL query is callable as a tool.
- **Person 2**: Read the 5 documented fraud typologies and the policy doc. Draft the GraphRAG retrieval design (what gets embedded/indexed, what gets fetched at query time). Cannot start real retrieval until Person 1's schema exists — use mock/sample data in the meantime.
- **Person 3**: Design the case record schema in code (matches architecture.md 4.2), stub the action-request interface, sketch UI wireframe (no build yet).
- **Sync at end of day**: Person 1 confirms schema + MCP tool works. Person 2 and 3 adjust their stubs to match the real schema, not the assumed one.

## Day 2

- **Person 1**: Write GSQL pattern-detection queries for the fraud typologies (shared device across accounts, velocity, ring detection, etc.). Expose each as an MCP tool.
- **Person 2**: Wire GraphRAG for real — pull graph facts via Person 1's MCP tools, retrieve relevant policy/typology text, assemble into the Evidence Bundle contract.
- **Person 3**: Build the mock action layer (block/monitor/warn/escalate/request-more-evidence as functions, not real integrations) and the policy/approval rule set (which actions need human sign-off).
- **Sync**: Person 2 demonstrates a real Evidence Bundle for one sample transaction, generated only from Person 1's tools — no hand-written test data.

## Day 3

- **Person 1**: Support/debug GSQL queries as Person 2 surfaces gaps; otherwise start building the case-memory graph writes (schema for storing completed cases as graph nodes) — done in coordination with Person 3, who owns the write-back logic itself.
- **Person 2**: Build the LangGraph state machine: trigger → gather evidence → assess confidence → branch. Get one full case running start to finish (mocked action call at the end).
- **Person 3**: Build case memory retrieval (given a new case, find similar past cases) using Person 1's new case-memory schema. Build case memory write-back function (not yet wired to the live agent).
- **Sync**: Person 2's agent runs one case end-to-end, calling Person 3's mocked action layer and Person 1's real graph tools. This is the first true integration point — treat it as a milestone, not a formality.

## Day 4

- **Person 1**: Polish/optimize slow GSQL queries found during Day 3 integration. Otherwise available to unblock others.
- **Person 2**: Wire the "not confident enough" branch fully — evidence-request generation, re-entry into the loop after new evidence arrives. Wire explanation generation (evidence used / why more evidence was requested / why this action).
- **Person 3**: Wire case memory write-back into the live agent loop (every completed case gets written and becomes retrievable). Wire the approval-route recording (before and after evidence requests, per the submission format).
- **Sync**: Full pipeline runs on one sample case with a low-confidence branch triggered, producing a case record with both approval-route states filled in.

## Day 5

- **Person 1**: Run the full pipeline against all 20 benchmark cases from the graph side — confirm every case's data actually exists and is queryable; flag any missing data to the group immediately.
- **Person 2**: Run all 20 benchmark cases through the agent, capture output, fix reasoning failures on outliers.
- **Person 3**: Build the UI (case view: evidence, uncertainty, recommendation, approval status). Wire it to read real case records, not mocked ones.
- **Sync**: 20 case outputs exist in the required submission format; UI shows at least one real case.

## Day 6 — Hardening (all three, on their own modules only)

- **Person 1**: Final GSQL correctness pass against the 20 cases.
- **Person 2**: Final explainability pass — tighten reasoning text, check SAR-trigger logic against policy.
- **Person 3**: Final UI pass, confirm case memory retrieval actually surfaces relevant priors, not noise.
- **This is the real deadline.** No new features after today.

## Day 7 — Deliverables only (no code changes)

- **Person 1**: Write the "How TigerGraph is used" section of the blog post + technical architecture diagram.
- **Person 2**: Write the "agentic capabilities implemented" + "what we learned" sections of the blog post.
- **Person 3**: Record the demo video, post to X/LinkedIn tagging @TigerGraphDB, final repo README cleanup.
