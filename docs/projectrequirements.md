# Project Requirements — Software & Accounts

Everything below must be set up before Day 1 work starts. Assign someone to own account creation for each so it isn't duplicated.

## 1. Accounts (create Day 0, before kickoff)

| Item | Purpose | Who creates it |
|---|---|---|
| TigerGraph Savanna account (savanna.tgcloud.io) | Hosted graph DB | Person 1 |
| GitHub repo (private, 3 collaborators) | Code + submission | Whoever creates it, add other two immediately |
| LLM API key (Groq / Anthropic / OpenAI — pick one, reuse existing key if the team already has one) | Agent reasoning | Person 2 |
| TigerGraph Discord (discord.gg/7JMkCAy9D3) | Mentor/judge support | All three join |
| TigerGraph WhatsApp group | Announcements | At least one person joins |

## 2. Core software / libraries

- Python 3.11+
- `pyTigerGraph` (or the TigerGraph MCP server's own client) — graph connectivity
- TigerGraph MCP server (clone from github.com/tigergraph/tigergraph-mcp)
- LangGraph (agent orchestration) + LangChain core if needed for tool wrapping
- An MCP-compatible agent client/runtime (Claude Code, or a custom Python MCP client)
- FastAPI or Streamlit (UI layer)
- `pandas` (dataset wrangling — the IEEE-CIS data is tabular before it becomes graph)
- `pytest` (basic test coverage on the evidence bundle / case record contracts)
- Git

## 3. Dataset

- HHGOA_IEEE dataset (provided by organizers — IEEE-CIS fraud data reshaped for this hackathon)
- **Read the dataset's own README before writing any schema or ingestion code** — it defines the answer format for the 20 benchmark cases, which is a hard requirement, not a suggestion.
- Includes: ~590K transactions, ~13.5K customers, device/connection records, bank fraud policy doc, 5 documented fraud typologies, regulatory references, closed cases (months 1–4), 20 benchmark cases (months 5–6, held out).

## 4. Infrastructure notes

- If using TigerGraph Savanna: confirm auto-stop/auto-start is enabled by whoever sets it up, so the instance doesn't idle-bill or die mid-demo.
- Decide early whether GraphRAG vector storage lives inside TigerGraph or needs a separate vector store — default to TigerGraph-native to avoid a second moving part, only add a separate vector DB if retrieval quality demands it.

## 5. Deliverable-production tools (needed by Day 6–7, not Day 1)

- Screen recording tool for the 3–5 min demo video
- Blog platform (Medium / dev.to / personal site — whatever the team already has)
- X or LinkedIn account to post from, tagging @TigerGraphDB

## 6. Explicitly NOT required

- No real payment processor, no real customer messaging integration, no real account-freezing capability — all actions are mocked/stubbed per the challenge brief. Do not spend time integrating real third-party APIs for this.
