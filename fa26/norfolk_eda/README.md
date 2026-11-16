# Norfolk County EDA

Answers the team's final questions (Q1–Q8) and the Norfolk-specific questions (N1–N6) for Norfolk County.

## Files
- `norfolk_analysis.py`: builds every number and table behind the charts from the Norfolk master parquet files.
- `norfolk_dashboard_page.html`: chart code (d3) used in the Claude dashboard.
- `charts/`: one PNG per question (card_q1.png … card_n6.png).

## Run
```
pip install pandas pyarrow numpy
python norfolk_analysis.py data/master/norfolk/charges.parquet data/master/norfolk/norfolk-supplementary.parquet
```
Outputs `norfolk_viz_data.json` and `norfolk_tables.json` (aggregated tables only).

## Method
- One row per case, classified by its most serious charge; motor-vehicle/OUI-only cases excluded.
- Team window 2017–2024; Norfolk "last decade" questions use 2015–2024.
- Case outcome = most severe outcome across charges. Norfolk's PLEA code is split by reason code (CWOF, pretrial probation, guilty plea).
- Nolle prosequi with reason SIND (indictment routing) excluded from N6.
- Unknown race kept as its own group (about 30% of cases).

## Not answerable
- Q5 bail: Norfolk denied the bail data request.
- N4 victim race: no victim fields.

Data files are not committed (client data).
