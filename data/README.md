# Data

Place the HHGOA IEEE files in `data/raw/` (gitignored):

- `transactions.csv` (~708 MB, streamed — never pasted into an LLM)
- `identity.csv`
- `closed_cases_history.csv`
- `case_pack.csv`

`data/case_pack.fallback.csv` is the public 20-row case pack copied from the dataset README so the pipeline can run without the full dump. It is not a substitute for `transactions.csv`.

Processed indexes live in `data/processed/` (gitignored).
