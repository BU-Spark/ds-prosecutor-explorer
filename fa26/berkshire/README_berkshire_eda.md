# Berkshire EDA, 2017–2024

Open `berkshire_eda_2017_2024.ipynb` in Jupyter or VS Code. The notebook includes the analysis code, embedded results, policy interpretation, and limitations.

Use Python 3.10+ and install the packages in `requirements_eda.txt` into your selected notebook environment. Restart Kernel and Run All from this folder or its parent. Rerunning writes derived figures/tables under `eda_outputs/`; it never writes the three original Excel files. Source SHA-256 checks are included.

The three main populations are filings initiated in 2017–2024, charges disposed in 2017–2024, and bail events dated in 2017–2024. Linked-cohort follow-up is assessed separately. Read the scope and limitations before using any rate. `eda_outputs/key_findings.md` provides a concise numerical readout, `tables/` includes the full unique-description frequency table and cross-tabs, and `figures/` contains reusable PNG charts.

No payment ledger is present: bail amounts set/requested are not county receipts. Judge and demographic comparisons are descriptive and cannot establish causal effects or discrimination.
