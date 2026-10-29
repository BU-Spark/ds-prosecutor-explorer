# Essex & Hampden EDA (2017–2025)

Exploratory analysis of prosecutor data for two Massachusetts counties: charges filed,
charges disposed, and bail, January 2017 – December 2025.

## Setup

```bash
pip install pandas openpyxl
```

Put the six raw files in a `data/` folder next to these scripts (do **not** commit them):

| County  | File |
|---------|------|
| Essex   | `01_Criminal_Charges_Filed_2017-01-01_2025-12-31.xlsx` |
| Essex   | `02_Criminal_Charges_Disposed_2017-01-01_2025-12-31.xlsx` |
| Essex   | `03_Bail_and_Pretrial_Detention_2017-01-01_2025-12-31.xlsx` |
| Hampden | `Data_-_Filed_17-25_2.xlsx` |
| Hampden | `Data_-_Dispo_17-25.xlsx` |
| Hampden | `Bail_17-25.xlsx` |

The first run reads the Excel files (a few minutes) and caches them in `cache/`.

## Scripts (run in order)

| Script | What it does | Output |
|--------|--------------|--------|
| `profile_files.py` | Profiles every column of all six files: missing values, unique values, top values, date ranges, impossible dates, duplicate rows | `output/profile_*.csv`, `output/file_summary.csv` |
| `two_county_analysis.py` | Answers the five research questions (outcomes, bail, race/gender, time to resolution, courts), excluding motor vehicle charges | `output/q1_*.csv` … `output/q5_*.csv` |
| `check_duplicates.py` | Evidence for duplicate rows in the Hampden files, with Excel row numbers | printed to screen |
| `load_data.py` | Shared file paths, loaders, and charge-type / court mappings | — |

```bash
python profile_files.py
python two_county_analysis.py
python check_duplicates.py
```

## Method summary

- One row per charge after removing exact duplicates; cases filed 2017–2025.
- Motor vehicle charges (chapters 89, 90, 90B–90F) are excluded (about 44% of charges).
- Charge type comes from the statute chapter in the charge code (e.g. `265/13A/B` → Person).
- Outcomes are grouped into Dismissed/nolle, Guilty/plea, CWF/diversion, Acquitted. Civil infractions,
  charges moved to Superior Court ("dismissed due to indictment") and pending charges are left out of rates.
- Cash bail = highest bail set above $0 on the case (Essex: District Court arraignment; Hampden: any "Bail Set").
- Race and gender comparisons are adjusted for charge type (direct standardization to each county's charge mix).
- Hampden "HW"/"HB" race codes are counted as Hispanic.

## Known limitations

- Hampden outcome codes (e.g. 2000, 2001, 2003, 2004, NOP) and court codes are not defined in the data;
  the mappings in the code are inferred and need client confirmation.
- Hampden files contain duplicate rows (about 6% of Filed, 17% of Dispo, about 30% of Bail); the Bail file has no count column.
- Race is missing or unknown in about 25% of Essex and 11% of Hampden cases.
- Sentencing fields are mostly empty in both counties.
- Results are descriptive and do not account for prior record or case details.
