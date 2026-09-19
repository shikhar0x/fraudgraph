# Fraud Policy (v1.0) — Verbatim from Dataset README

This is the exact policy text the agent operates under and that must be loaded into TigerGraph's vector store for GraphRAG retrieval. Person 3 (Actions & Policy Layer) implements the rules below as literal, testable logic. Action names and approval routes in output files must match these identifiers exactly.

## 0. What the agent starts with

Every transaction carries a `risk_score` between 0 and 1 from the bank's detection model. The model is useful and imperfect: many high scores are legitimate, and some fraud scores low. A score is a reason to look, never a verdict. The only confirmed outcomes are in the closed cases.

## 1. Actions

| Action | What it does | Customer impact |
|---|---|---|
| `ALLOW_TRANSACTION` | Let the flagged transaction stand | None |
| `DECLINE_TRANSACTION` | Decline the flagged authorization only. Card stays active | Low |
| `MONITOR_CARD` | Card stays active; raise monitoring sensitivity for 72 hours | None |
| `MONITOR_CONNECTED_CARDS` | Put other cards linked to the same device profile, region cluster, or ring under monitoring | None |
| `WARN_CUSTOMER` | Send an informational message | None |
| `VERIFY_WITH_CUSTOMER` | Ask the cardholder whether they made the transaction. Card stays active pending reply | Low |
| `STEP_UP_AUTH` | Require a one-time passcode or app confirmation before further activity | Low |
| `BLOCK_CARD` | Block this card and reissue | High |
| `BLOCK_ALL_CARDS` | Block every card the customer holds | Very high |
| `GENERATE_REPORT` | Write up the investigation for the internal record, without opening a case | None |
| `CREATE_CASE` | Open an internal fraud case with evidence attached, write it to the graph | None |
| `FILE_REPORT` | File a suspicious activity report with the regulator | None |
| `ESCALATE_TO_ANALYST` | Hand the case to a human analyst with the evidence | None |
| `CLOSE_NO_FRAUD` | Close the alert as legitimate | None |

An agent may recommend several actions for one case, ordered by what happens first.

## 2. Approval routing

| Route | Applies to |
|---|---|
| `auto` | `ALLOW_TRANSACTION`, `MONITOR_CARD`, `MONITOR_CONNECTED_CARDS`, `WARN_CUSTOMER`, `VERIFY_WITH_CUSTOMER`, `STEP_UP_AUTH`, `GENERATE_REPORT`, `CREATE_CASE`, `ESCALATE_TO_ANALYST`, `CLOSE_NO_FRAUD` |
| `L1` (team lead) | `DECLINE_TRANSACTION`; `BLOCK_CARD` when exposure ≤ $2,500 |
| `L2` (fraud manager) | `BLOCK_CARD` when exposure > $2,500; `BLOCK_ALL_CARDS` always; `FILE_REPORT` always |

The agent recommends. Only `auto` actions may be executed by the agent. `L1`/`L2` actions wait for a human.

## 3. Rules

**R1. Verify before you block on a weak signal.** Single-signal case (including risk score alone) with fraud probability below 0.70 → recommend `VERIFY_WITH_CUSTOMER` or `STEP_UP_AUTH` before any block.

**R2. Customer denies the transaction.** Recommend `BLOCK_CARD` and `CREATE_CASE`. Add `FILE_REPORT` if exposure exceeds $1,000 or the case connects to a shared device profile or another card's fraud.

**R3. Customer confirms the transaction.** Recommend `CLOSE_NO_FRAUD`. Note the confirmation in the case file.

**R4. No reply within 24 hours.** Recommend `MONITOR_CARD` and `DECLINE_TRANSACTION` for pending authorizations. Escalate if exposure exceeds $500.

**R5. Card testing.** Three+ small online authorizations on one card within an hour, followed by a larger purchase: recommend `DECLINE_TRANSACTION` and `STEP_UP_AUTH`. If a purchase over $100 already cleared, recommend `BLOCK_CARD`.

**R6. Shared origin.** Several cards show fraud from the same device profile, billing region, or recipient email in one window: name the shared element, recommend `CREATE_CASE` and `FILE_REPORT`, and `MONITOR_CONNECTED_CARDS` for every card that shares it.

**R7. Disputed but legitimate.** Customer disputes a charge matching their own recurring pattern (same merchant, amount, monthly): recommend `CREATE_CASE`, `VERIFY_WITH_CUSTOMER`, `WARN_CUSTOMER`. Do not block.

**R8. Escalate when uncertain and exposed.** Verdict `uncertain` and exposure > $500, or evidence conflicts: recommend `ESCALATE_TO_ANALYST`.

**R9. Undocumented patterns.** Activity fits none of the known patterns but shows coordinated/repeated abuse across customers: recommend `CREATE_CASE`, `FILE_REPORT`, `ESCALATE_TO_ANALYST`, and describe the pattern in your own words. Do not force it into a known category.

**R10. Never `BLOCK_ALL_CARDS`** unless at least two of the customer's cards show confirmed fraud, or credentials are confirmed compromised.

## 3a. Case vs. report

**Case** (`CREATE_CASE`): internal record. Open whenever fraud probability reaches 0.30, whenever evidence is requested, or whenever a customer disputes a charge. Written to the graph so later investigations can retrieve it.

**Report** (`FILE_REPORT`): regulatory filing. File when fraud is confirmed or strongly suspected AND at least one holds: exposure > $1,000; connects to a shared device/region cluster/another customer's fraud; pattern is coordinated or undocumented (R9). A report always has a case behind it. The narrative must stand on its own: who, what, when, where, how, why.

## 3b. Recommendations can change

Recommend what evidence supports now, request more evidence if policy calls for it, then recommend again. Record both `initial` and `final`, and `what_changed`.

## 4. Exposure

Sum of absolute amounts of every transaction identified as part of the fraud episode, including the flagged one. USD.

## 5. Gathering more evidence

Agent may, without approval: ask customer to validate a transaction, request step-up auth, request analyst info. Responses are not provided this round — simulate and record the assumption in `evidence_requests`.

## 6. Stopping

Stop when: fraud probability ≥ 0.85 or ≤ 0.15 with 2+ independent evidence pieces; OR a verification response settles it; OR further steps won't change the decision (state why in `stop_reason`). Stopping too early or too late are both marked down.

## 7. Explaining

Every recommendation states: what evidence was used, why more evidence was requested (if it was), why the chosen actions follow from policy — citing the rule number.

## The five known fraud patterns

1. **Card testing** — 3+ tiny online authorizations (often <$5), then a larger purchase. Confirmed by sequence itself. Policy R5.
2. **Card-not-present fraud** — online use without the card; amounts/products inconsistent with history, often bursts of 2-4 within 48h. One unusual purchase alone is ambiguous. R1-R4.
3. **Card-not-present fraud, new device** — same as #2, plus identity record marks device `New`, sometimes behind a proxy. Stronger signal, still not proof.
4. **Out-of-region use** — card-present purchases in a billing region with no history, while normal activity continues at home. Several days = trip, not clone. R2, R3.
5. **Account takeover** — mixed-channel activity inconsistent with cardholder, device/match-flag anomalies, pointing to stolen credentials.

`undocumented` — a few closed cases are confirmed fraud but match none of the five. Read `analyst_notes` carefully; noticing and describing an undocumented pattern is scored (R9).
