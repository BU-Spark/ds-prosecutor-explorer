# Cape and Islands analysis

Open `cape_and_islands_eda_2017_2024.ipynb` for extensive EDA and `cape_and_islands_team_objectives_23_2017_2024.ipynb` for all 23 shared Objectives. Both include embedded charts/tables, readable code, limits, assumptions, discrepancy flags, and source-hash checks.

Use Python 3.10+ and packages in `requirements_cape.txt`. Restart Kernel and Run All from this folder or its parent. Rerunning writes only derived outputs under `cape_eda_outputs/` and `cape_objectives_23_outputs/`. The three original Excel workbooks are never written. No network or external numerical data is needed.

Important: no filing date exists. Any case-ID-year chart is an explicitly unverified proxy, not a common filing-year metric. Missing, explicit Unknown, unmapped values, invalid dates, and actual zero amounts remain distinct. Identical charge rows are retained because no count sequence proves they are redundant. Severe shifted rows are quarantined with Excel coordinates, not exposed names/comments. Cash-only/surety, actual funds collected, and custody duration cannot be reconstructed.

The Objectives output folder contains `answers_to_23_objectives.md`, `tables/all_23_objectives_answer_matrix.csv`, and `tables/uniform_visualization_contracts.csv` for team discussion. The EDA folder contains complete literal charge-description frequencies, code cross-tabs, source audits, and reusable PNG figures. Source-only known-criminal and observed-closed-case populations are qualified proxies and require team agreement before pooling counties.
