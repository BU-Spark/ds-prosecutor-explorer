"""Shared loaders for the Essex and Hampden prosecutor data (2017-2025).

Put the six raw Excel files in one folder (default: ./data) with their original names,
or edit FILES below. The first load reads the Excel files (a few minutes each) and caches
them as pickles in ./cache so later runs are fast.
"""
from pathlib import Path
import pandas as pd

FILES = {
    ("essex", "filed"): "01_Criminal_Charges_Filed_2017-01-01_2025-12-31.xlsx",
    ("essex", "disposed"): "02_Criminal_Charges_Disposed_2017-01-01_2025-12-31.xlsx",
    ("essex", "bail"): "03_Bail_and_Pretrial_Detention_2017-01-01_2025-12-31.xlsx",
    ("hampden", "filed"): "Data_-_Filed_17-25_2.xlsx",
    ("hampden", "disposed"): "Data_-_Dispo_17-25.xlsx",
    ("hampden", "bail"): "Bail_17-25.xlsx",
}

# Motor vehicle statute chapters, excluded from the main analysis
MV_CHAPTERS = {"89", "90", "90B", "90C", "90D", "90E", "90F"}

# Charge type by Massachusetts General Laws chapter (first part of the charge code, e.g. 265/13A/B)
CHAPTER_TYPES = {
    "265": "Person", "266": "Property", "94C": "Drugs", "269": "Weapons", "268": "Vs. justice",
    "209A": "Restraining order", "272": "Public order", "140": "Firearms licensing", "274": "Attempt/conspiracy",
}

# Hampden court codes (inferred from agency/court names; confirm with client)
HAMPDEN_COURTS = {
    "SD": "Springfield District", "HD": "Holyoke District", "PD": "Palmer District", "CD": "Chicopee District",
    "WD": "Westfield District", "HS": "Hampden Superior", "SJ": "Springfield Juvenile", "HJ": "Holyoke Juvenile",
}


def load(county, kind, data_dir="data", cache_dir="cache"):
    """Load one file as a DataFrame with stripped column names (cached after first read)."""
    data_dir, cache_dir = Path(data_dir), Path(cache_dir)
    cache_dir.mkdir(exist_ok=True)
    cache = cache_dir / f"{county}_{kind}.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    df = pd.read_excel(data_dir / FILES[(county, kind)])
    df.columns = [str(c).strip() for c in df.columns]
    df.to_pickle(cache)
    return df


def charge_type(code):
    """Return (chapter, charge type) from a charge code like '265/13A/B'."""
    chapter = str(code).split("/")[0].strip().upper()
    return chapter, CHAPTER_TYPES.get(chapter, "Other")
