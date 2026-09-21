# UI Wireframe — Case View (sketch, Day 1)

Layout: single case page.
- Header: case_id, status, verdict, fraud_probability
- Evidence panel: list of EvidenceItem (claim, source, entity_ids)
- Pattern + exposure_usd
- Next-best-actions: initial (left) vs final (right), what_changed between
- SAR panel: shown only if sar.file is true
- similar_prior_cases: linked list of closed case IDs

Implemented: `app/ui.py` (Streamlit). Reads `cases/*.json`. Mock-mode banner from `cases/benchmark_report.json`. L1/L2 shown as pending human approval. SAR panel only when `sar.file` is true.

```bash
streamlit run app/ui.py --server.address 0.0.0.0 --server.port 8501
```
