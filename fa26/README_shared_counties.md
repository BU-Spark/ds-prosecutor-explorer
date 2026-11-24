# Berkshire and Cape & Islands — shared-template review

Open `berkshire/berkshire_analysis.ipynb` and `cape_and_islands/cape_and_islands_analysis.ipynb`.
Both notebooks retain executed tables and embedded graphs. PNGs and aggregate CSVs are adjacent to each notebook.
The original ZIP, original notebooks, and raw spreadsheets are unchanged. Norfolk is outside this revision.

## What changed

- Adopted the supplied `parin-dev` template's coverage-first presentation, case unit, outcome hierarchy, missing-data threshold, small-cell rule and question order.
- Copied `viz_style.py` and `county_charts.py` unchanged from the linked branch. `county_review_charts.py` uses their palette and plotting primitives while correcting county-specific labels and the Q7 metric: incarceration is not conviction.
- Case counts now use observed docket × defendant units rather than distinct internal case IDs. Berkshire resolves the docket using the recorded court or the sole available docket. Ambiguous identities are excluded and audited.
- The primary cohort requires at least one source-classified felony or misdemeanor charge (F, M+, M−). Civil-only cases are excluded from criminal volume. Missing/unmapped classes cannot establish criminal eligibility; the source coverage table is conditional on the retained known-criminal charge cohort.
- Outcomes now follow case cohorts rather than the older notebooks' disposition-year groups. Berkshire uses initiation year; Cape has no filing date and therefore uses explicitly unverified case-ID-prefix cohorts only as supplementary proxies.
- Retained all charge outcomes when applying the shared severity hierarchy; any recorded open charge excludes the case from disposed-case metrics. Missing closed-charge outcomes remain Unknown.
- Fields over 20% missing in the target source cohort are insufficient, matching the supplied template. Missing/conflicting evidence is checked again on each metric's case denominator. Dependent metrics are withheld rather than treating blanks as zero. This stricter rule can withhold results previously shown descriptively.
- Sentence evidence is kept separate from plea route, CWOF, and actual time served. Suspended and filed sentences are not silently merged with probation or incarceration.
- Bail is the first recorded in-range event, not a verified arraignment. Ambiguous cash/surety or unspecified-mode bail is not labeled confirmed cash-only bail. No payment, revenue, inability-to-post, or detention-duration claim is made.
- Q8's requested prior-record adjustment remains unavailable. A clearly marked supplementary offense-only comparison is shown where coverage and cell sizes permit; zero priors are never inferred from absent history.

Exact repeated rows are treated as redundant for case-level aggregation. Cape does not provide a charge ordinal, so identical rows cannot by themselves prove duplicate legal charges. These notebooks do not use the resulting row total as a verified count of distinct legal charges.

The supplied template includes legal-policy event markers. These revised charts omit event overlays because the extracts alone do not establish a causal effect; this does not change the shared colors or quantitative metrics.

## Reproduce

Use Python 3.13 and install `requirements_shared_counties.txt` in an isolated environment. Select that environment as the notebook kernel and Run All.

By default, this package sits immediately inside the project folder alongside these source folders:

```
project/
  berkshire/
    charges filed info.xlsx
    disposed info.xlsx
    bail info.xlsx
  cape and island/
    charges filed.xlsx
    charges disposed.xlsx
    bail_data.xlsx
  fa26/
```

For another source location, set `PROSECUTOR_DATA_ROOT` to the parent of the two source folders before launching Jupyter or VS Code. The setup cell discovers the package without requiring a Git checkout. Raw data are not included in this review package.

To execute and validate both notebooks from the package root:

```
python execute_notebooks.py
```

The runner creates a temporary project-local kernel configuration under `.execution/`, uses the current Python environment, stops on the first error, and requires embedded PNG outputs. That configuration is excluded from the review ZIP and Git.

Run `python verify_release.py` afterward to validate the saved outputs and rebuild the ZIP. It checks raw-source hashes when the original workbooks are available and explicitly lists any source-preservation checks it cannot perform on another computer.

## Provenance and review

- Template: https://github.com/BU-Spark/ds-prosecutor-explorer/blob/parin-dev/county_analysis_template.ipynb
- Charts: https://github.com/BU-Spark/ds-prosecutor-explorer/blob/parin-dev/county_charts.py
- Style: https://github.com/BU-Spark/ds-prosecutor-explorer/blob/parin-dev/viz_style.py
- Source snapshots retrieved November 23, 2026; hashes are recorded in `review_manifest.json`.
- Annual Census PEP population values are reused from the supplied Berkshire notebook. `annual_population.csv` retains the year, estimate vintage, and original source URL. No new population values were fetched.
- Raw workbook hashes, row exclusions, coverage, case identity, disposition crosswalks, question answerability, and date exclusions are exported as aggregate tables for review.

The remaining client questions appear at the end of both notebooks. Executing without errors confirms reproducibility and the included checks; it does not resolve missing source information or validate ambiguous source semantics.

## GitHub placement

These reviewed notebooks replace the previous Berkshire and Cape folders directly under `fa26` on `pavan`. Norfolk and the other counties are unchanged. Raw workbooks remain outside Git. Set `PROSECUTOR_DATA_ROOT` to the local folder containing `berkshire` and `cape and island` before rerunning.

Text checksums normalize Windows/Unix line endings; raw workbook checksums preserve the original bytes.
