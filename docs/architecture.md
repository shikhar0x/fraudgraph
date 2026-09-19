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

### 4.1 Evidence Bundle (GraphRAG → Agent)
```json
{
  "case_id": "string",
  "transaction_id": "string",
  "graph_facts": [ {"type": "string", "description": "string", "confidence": 0.0} ],
  "policy_context": ["string excerpt", "..."],
  "typology_matches": ["string typology name", "..."],
  "prior_similar_cases": [ {"case_id": "string", "outcome": "confirmed_fraud|cleared", "summary": "string"} ]
}
```

### 4.2 Case Record (Agent → Case Memory / Graph / Output file)
```json
{
  "case_id": "string",
  "trigger": "string",
  "evidence_used": [ "..." ],
  "fraud_pattern": "string or null",
  "risk_level": "low|medium|high",
  "confidence": 0.0,
  "evidence_requests": [ {"stage": "before|after", "request": "string", "approval_route": "string"} ],
  "recommended_actions": [ "string" ],
  "actions_taken": [ "string" ],
  "sar_filed": true,
  "explanation": "string",
  "status": "open|escalated|closed"
}
```

### 4.3 Action Request (Agent → Action & Policy Layer)
```json
{
  "action": "block_transaction|block_account|monitor_account|warn_customer|request_step_up|escalate|file_sar",
  "requires_approval": true,
  "justification": "string"
}
```

Anyone changing a contract shape must update this file and tell the other two before merging.

## 5. Tech stack

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

## 6. Non-negotiable design constraints

- The LLM reasons and explains; it does not replace graph pattern detection.
- Every action is either logged as "recommended" or, if executed, is mocked/stubbed — never a real customer-facing action.
- Confidence must be an explicit, inspectable value at every decision point, not implicit in prose.
