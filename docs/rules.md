# Rules of Engagement — For AI Agents Working On This Project

Read this before writing any code. Purpose: keep the agent from doing expensive, scope-creeping, or contract-breaking work. If a rule and a person's instruction conflict, flag the conflict instead of silently picking one.

## 1. Scope boundaries

- Only work on the module owned by the person who is prompting you (see phases.md for ownership). Do not edit another owner's files unless explicitly told to, even if you think you see a bug — flag it instead.
- Do not add features beyond what's in architecture.md and projectrequirements.md. If something looks missing, ask before building it.
- Do not integrate real third-party APIs for actions (payments, messaging, account freezing). Everything is mocked/stubbed per the challenge brief — building a real integration is wasted effort and a scope violation.

## 2. Contracts are law

- The Evidence Bundle, Case Record, and Action Request shapes in architecture.md Section 4 are fixed. Do not change a field name, type, or structure without the change being written back into architecture.md first and flagged to the user for the other two teammates.
- The 20-benchmark-case output format is defined by the dataset's own README, not by us. Do not improvise a "cleaner" format — match theirs exactly.

## 3. No hallucinated graph/agent behavior

- Never invent GSQL syntax you're not sure of. If uncertain, say so and propose checking TigerGraph docs rather than producing plausible-looking-but-wrong GSQL.
- Never claim a query or pattern-detection result works without it actually having been run against real data in this project. Do not fabricate benchmark numbers, confidence scores, or accuracy claims in documentation or the blog post.
- Confidence values reported by the agent must come from an actual computed signal (risk score, pattern match strength, evidence completeness) — never a placeholder number dressed up as a real assessment.

## 4. Cost discipline (the reason this file exists)

- Don't make redundant LLM calls in a loop. Cache retrieved evidence within a single case investigation instead of re-fetching.
- Prefer graph queries and deterministic logic over LLM calls wherever the task doesn't require reasoning (e.g., don't ask an LLM to compute a threshold comparison it could do in Python).
- Batch similar operations (e.g., running all 20 benchmark cases) rather than triggering one-off ad hoc runs repeatedly during debugging — use a small fixed sample (1–2 cases) while iterating, then run the full 20 only when confident.
- Before generating large blocks of new code, check architecture.md and this project's existing modules first — don't regenerate something that already exists.

## 5. Testing discipline

- Every change to the agent loop or GSQL queries must be verified against at least one real sample case before being considered done — not just "should work."
- When a bug is found, report the diagnostic finding first, then propose the fix, then implement — don't silently patch and move on (matches the team's preferred working pattern from prior hackathon work).

## 6. Process discipline

- Update memory.md after every meaningful milestone (schema finalized, first end-to-end run, integration point reached, bug found and fixed). This is what keeps future sessions cheap — a well-maintained memory.md means an agent doesn't need the whole codebase re-explained.
- Commit small and often, with descriptive messages tied to the phase/module (e.g., "Person1: GSQL ring-detection query for typology 3").
- If a task would take significantly longer than the day it's scheduled for in phases.md, say so immediately rather than quietly falling behind — the 7-day timeline has no slack built in past Day 6.

## 7. Explanation and honesty

- The agent's own "explain its reasoning" output must reflect what evidence was actually retrieved and actually used — not a generic justification. Same standard applies to us: don't write documentation or blog content that overstates what the system does.
