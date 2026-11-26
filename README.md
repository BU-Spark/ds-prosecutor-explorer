# Prosecutor Explorer

Shared county-analysis files are available on this branch’s front page:

- [Analysis template](county_analysis_template.ipynb)
- [Shared chart functions](county_charts.py)
- [Visualization style](viz_style.py)
- [Figures](figures/)

County notebooks and supporting work are organized inside [fa26](fa26/).

| County analysis | Notebook | Figures |
| --- | --- | --- |
| Berkshire — eight shared questions | [Open notebook](fa26/berkshire/berkshire_analysis.ipynb) | [View figures](figures/berkshire/) |
| Cape & Islands — eight shared questions | [Open notebook](fa26/cape_and_islands/cape_and_islands_analysis.ipynb) | [View figures](figures/cape_and_islands/) |
| Norfolk — six county-specific questions | [Open notebook](fa26/norfolk/norfolk_six_shared_questions_2017_2025.ipynb) | [View figures](fa26/norfolk/figures/norfolk_six_shared_questions_2017_2025/) |

The reviewed Berkshire and Cape & Islands notebooks include saved outputs and clearly identify partial or unavailable answers. Each has 12 figures supporting eight questions, including explanatory notices where source data are insufficient.

## Run Berkshire and Cape & Islands

Install [the analysis requirements](fa26/requirements_shared_counties.txt), select that Python environment, and run the notebooks in order. Set `PROSECUTOR_DATA_ROOT` to the local directory containing the original `berkshire` and `cape and island` source folders. Raw spreadsheets are not included in this repository.

```text
python -m pip install -r fa26/requirements_shared_counties.txt
python fa26/execute_notebooks.py
python fa26/verify_release.py
```

See the [methods, limitations and reproduction guide](fa26/README_shared_counties.md) and [review manifest](fa26/review_manifest.json). Other county work remains under `fa26`.
