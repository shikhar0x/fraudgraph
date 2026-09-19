# Architecture — Agentic Fraud Investigation (TigerGraph HHGoa Task 4)

Purpose of this file: the single source of truth for how the system fits together. Any AI agent (or human) working on one module should read this first and not need to ask what another module does or produces.

## 1. One-line description

A LangGraph-orchestrated agent investigates fraud cases by pulling evidence from TigerGraph (via TigerGraph MCP), grounding its reasoning with GraphRAG (graph facts + policy/typology docs), deciding whether it has enough confidence to act, and — if not — requesting more evidence before recommending or executing a next-best-action, with every step written back to the graph as a case record.

## 2. Layers and ownership

| # | Layer | Responsibility | Owner (see phases.md) |
|---|---|---|---|
| 1 | Data Layer | TigerGraph schema, data load, GSQL fraud-pattern queries | Person 1 |
| 2 | MCP Layer | TigerGraph MCP server exposing graph ops as agent tools | Person 1 |
| 3 | GraphRAG / Evidence Layer | Retrieves connected graph evidence + relevant policy/typology text, assembles structured evidence bundle | Person 2 |
| 4 | Agent Reasoning Layer | LangGraph state machine: trigger → gather → assess confidence → branch → decide | Person 2 |
| 5 | Action & Policy Layer | Mock action execution, approval/permission rules, next-best-action logic | Person 3 |
| 6 | Case Memory Layer | Write completed cases back to graph, retrieve similar past cases | Person 3 |
| 7 | UI Layer | Analyst/case view showing evidence, uncertainty, recommendations | Person 3 |

Each layer talks to its neighbors only through the contracts in Section 4. This is what keeps three people from stepping on each other's code.

## 3. Data flow

```
Trigger (signal / report / analyst request)
        │
        ▼
Agent Reasoning Layer (LangGraph)
        │  calls tools
        ▼
MCP Layer ──► TigerGraph (GSQL queries, graph algorithms)
        │
        ▼
GraphRAG Layer (graph facts + policy/typology docs → evidence bundle)
        │
        ▼
Agent Reasoning Layer: assess risk + confidence
        │
   ┌────┴─────┐
   │           │
confident   not confident
   │           │
   ▼           ▼
Action &    Gather more evidence
Policy      (step-up auth / analyst ask)
Layer           │
   │           └──► back into Agent Reasoning Layer
   ▼
Case Memory Layer (write case to graph, index for future retrieval)
   │
   ▼
UI Layer (renders case, evidence, reasoning, action, approval status)
```

## 4. Interface contracts (do not change without telling the other two people)

**These are now locked to the dataset's own answer format (`README.md`, "Answer Format" section) — not our own invention.** This is the exact shape every case output must match, since it's what gets scored against a hidden answer key. Do not simplify or rename fields.

### 4.1 Evidence Bundle (GraphRAG → Agent, internal — not submitted, but feeds `case.evidence`)
```json
{
  "case_id": "string",
  "flagged_txn_id": "string",
  "graph_facts": [ {"claim": "string", "source": "graph|document|customer|external", "ref": "string", "entity_ids": ["..."]} ],
  "policy_context": ["string excerpt from Fraud Policy section"],
  "typology_matches": ["card_testing|card_not_present_fraud|card_not_present_new_device|out_of_region_use|account_takeover|undocumented|none"],
  "similar_prior_cases": ["CC-xxxx", "..."]
}
```
This is where `graph_facts` becomes `case.evidence`, `similar_prior_cases` becomes `case.similar_prior_cases`, and `typology_matches` feeds `case.pattern`.

### 4.2 Case Record — this IS the submitted output per case (one file: `cases/<case_id>.json`)

Top level:
```json
{
  "case_id": "string (from case_pack.csv)",
  "case": { "...": "see below" },
  "evidence_requests": [ {"type": "customer_validation|step_up_auth|analyst_info", "asked_after_step": 0, "assumed_response": "string"} ],
  "next_best_actions": { "initial": [], "final": [], "what_changed": "string" },
  "sar": { "...": "see below" },
  "stop_reason": "string",
  "tool_calls": 0,
  "tokens": 0,
  "latency_s": 0.0
}
```

`case` object:
```json
{
  "status": "open|closed_fraud|closed_legitimate|escalated",
  "verdict": "fraud|legitimate|uncertain",
  "fraud_probability": 0.0,
  "pattern": "card_testing|card_not_present_fraud|card_not_present_new_device|out_of_region_use|account_takeover|undocumented|none",
  "pattern_description": "string — required only when pattern is 'undocumented', else ''",
  "affected_txn_ids": ["..."],
  "first_suspicious_txn_id": "string or ''",
  "connected_card_ids": ["..."],
  "connected_device_profiles": ["..."],
  "exposure_usd": 0.0,
  "evidence": [ {"claim": "string", "source": "graph|document|customer|external", "ref": "string", "entity_ids": ["..."]} ],
  "similar_prior_cases": ["CC-xxxx"],
  "summary": "string, 2-6 sentences",
  "written_to_graph": true,
  "graph_case_id": "string or ''"
}
```

`next_best_actions.initial` / `.final` — each entry:
```json
{ "action": "ALLOW_TRANSACTION|DECLINE_TRANSACTION|MONITOR_CARD|MONITOR_CONNECTED_CARDS|WARN_CUSTOMER|VERIFY_WITH_CUSTOMER|STEP_UP_AUTH|BLOCK_CARD|BLOCK_ALL_CARDS|GENERATE_REPORT|CREATE_CASE|FILE_REPORT|ESCALATE_TO_ANALYST|CLOSE_NO_FRAUD", "route": "auto|L1|L2", "reason": "string citing policy rule (e.g. 'R5')" }
```

`sar` object (when `file` is false: `narrative` "", `subjects` [], `total_amount_usd` 0, `activity_dates` []):
```json
{
  "file": true,
  "reason": "string, cite policy rule",
  "narrative": "string, 6-12 sentences, who/what/when/where/how/why",
  "subjects": ["..."],
  "total_amount_usd": 0.0,
  "activity_dates": ["YYYY-MM-DD", "YYYY-MM-DD"]
}
```

**Hard rules on this contract:**
- Every ID used must actually exist in the dataset — invented IDs score zero.
- `action`, `route`, and `pattern` values must match the exact strings above — no synonyms, no lowercase drift.
- Legitimate verdicts: `affected_txn_ids` empty, `exposure_usd` 0, `sar.file` false.

### 4.3 Action Request (Agent Reasoning → Action & Policy Layer, internal)
```json
{
  "action": "one of the 13 action names in 4.2",
  "requires_approval": true,
  "route": "auto|L1|L2",
  "justification": "string citing policy rule"
}
```
Route is resolved by the Action & Policy Layer per the Fraud Policy's approval table (Section 2) — the agent recommends, the policy layer assigns/validates the route.

Anyone changing a contract shape must update this file and tell the other two before merging. **This particular contract is now sourced from an external, immutable spec (the dataset README) — if it looks wrong, the fix is in our implementation, not in this file.**

## 5. Confirmed dataset (locked, from `README.md`)

| File | Rows | Notes |
|---|---|---|
| `transactions.csv` | 590,742 | ~708 MB. **Too large to hand to an AI agent as text — never paste this into a prompt.** Joins to `identity.csv` on `TransactionID` |
| `identity.csv` | 144,432 | Online transactions only; joins to transactions |
| `closed_cases_history.csv` | 5,565 | 4,665 confirmed fraud / 900 cleared. This is the case memory seed — load into the graph AND into vector retrieval (narratives) |
| `case_pack.csv` | 20 | The exam. One `.json` output per case required, in `cases/` |

`transactions.csv` lives only in `data/raw/` locally (gitignored) and gets streamed into TigerGraph via an ingestion script — it never gets read into an LLM context directly.

## 5.1 Graph schema (per README "Suggested graph schema" — start here, adjust as needed)

**Vertices:** `Customer`, `Card`, `Transaction`, `DeviceProfile` (DeviceInfo + OS + browser + screen, composite key), `EmailDomain`, `BillingRegion`, `ClosedCase`

**Edges:**
- `Customer -OWNS-> Card`
- `Card -MADE-> Transaction`
- `Transaction -FROM_DEVICE-> DeviceProfile` (online only, from `identity.csv`)
- `Transaction -PURCHASER_EMAIL-> EmailDomain`
- `Transaction -BILLED_IN-> BillingRegion` (from `addr1`)
- `Transaction -NEXT-> Transaction` (ordered by `ts` within a card — needed for card-testing pattern detection)
- `ClosedCase -INVOLVES-> Transaction`, `ClosedCase -ON_CARD-> Card`, `ClosedCase -CONNECTED_TO-> Card`

Vector store (TigerGraph-native): closed-case narratives (`analyst_notes`), the Fraud Policy text below, the 5 pattern descriptions, and any regulatory PDFs the team decides to load.

## 5.2 Fraud policy — condensed reference (full text is the source of truth, in `docs/fraud_policy.md` — copy it there verbatim from the README)

**13 actions:** `ALLOW_TRANSACTION`, `DECLINE_TRANSACTION`, `MONITOR_CARD`, `MONITOR_CONNECTED_CARDS`, `WARN_CUSTOMER`, `VERIFY_WITH_CUSTOMER`, `STEP_UP_AUTH`, `BLOCK_CARD`, `BLOCK_ALL_CARDS`, `GENERATE_REPORT`, `CREATE_CASE`, `FILE_REPORT`, `ESCALATE_TO_ANALYST`, `CLOSE_NO_FRAUD`

**Approval routing:** `auto` (agent may execute) → everything except blocks/decline/reports. `L1` → `DECLINE_TRANSACTION`, `BLOCK_CARD` if exposure ≤ $2,500. `L2` → `BLOCK_CARD` if exposure > $2,500, `BLOCK_ALL_CARDS` always, `FILE_REPORT` always.

**Rules R1–R10** govern which actions apply when (verify-before-block on weak signal, customer-denies vs confirms, card testing, shared-origin fraud rings, disputed-but-legitimate, escalate-when-uncertain-and-exposed, undocumented patterns, never `BLOCK_ALL_CARDS` without two confirmed cards). **Person 3 (Actions & Policy Layer) encodes these as literal, testable rule logic — not as an LLM prompt hoping it remembers the policy.** The LLM proposes, the rule engine validates the route.

**Stopping condition:** fraud probability ≥ 0.85 or ≤ 0.15 with 2+ independent evidence pieces, OR a verification response settles it, OR further evidence won't change the decision (state why in `stop_reason`).

## 6. Tech stack

| Component | Choice | Notes |
|---|---|---|
| Graph DB | TigerGraph Savanna (free tier) | enable auto-stop/auto-start |
| Graph query language | GSQL | pattern detection, traversal |
| Agent-to-graph bridge | TigerGraph MCP | github.com/tigergraph/tigergraph-mcp |
| Agent orchestration | LangGraph | state machine fits the loop-until-confident pattern |
| LLM | reuse existing project's LLM choice (confirm with team) | reasoning + explanation only, not fraud detection itself |
| Retrieval / GraphRAG | TigerGraph vector storage + graph traversal | avoid standing up a second vector DB unless needed |
| UI | Streamlit or lightweight FastAPI + HTML | functional over polished |
| Language | Python 3.11+ | |

## 7. Non-negotiable design constraints

- The LLM reasons and explains; it does not replace graph pattern detection.
- Every action is either logged as "recommended" or, if executed, is mocked/stubbed — never a real customer-facing action.
- Confidence must be an explicit, inspectable value at every decision point, not implicit in prose.
