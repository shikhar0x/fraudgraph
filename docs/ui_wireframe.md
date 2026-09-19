# UI Wireframe — Case View (sketch, Day 1)

Layout: single case page.
- Header: case_id, status, verdict, fraud_probability
- Evidence panel: list of EvidenceItem (claim, source, entity_ids)
- Pattern + exposure_usd
- Next-best-actions: initial (left) vs final (right), what_changed between
- SAR panel: shown only if sar.file is true
- similar_prior_cases: linked list of closed case IDs

Build target: Day 5, per phases.md. Streamlit is the fast path given the team's Python stack.
