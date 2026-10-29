"""Step 1: profile every column of the six files (Essex + Hampden: filed, disposed, bail).

Writes one CSV per file to ./output/profile_<county>_<file>.csv with, for each column:
dtype, missing count and %, unique values, top 5 values, and (for date-like columns)
min/max and the number of impossible dates (before 1990 or after 2026).
Also prints file-level stats: rows, exact duplicate rows, and the share of the file they make up.

Usage:  python profile_files.py --data data
"""
import argparse
from pathlib import Path
import pandas as pd
from load_data import FILES, load

DATE_HINTS = ("date", "dt", "dspstn", "crm", "evnt", "sts")


def profile(df):
    rows = []
    for col in df.columns:
        s = df[col]
        top = s.astype(str)[s.notna()].value_counts().head(5)
        rec = {
            "column": col,
            "dtype": str(s.dtype),
            "missing": int(s.isna().sum()),
            "missing_pct": round(s.isna().mean() * 100, 2),
            "unique": int(s.nunique()),
            "top_values": "; ".join(f"{k} ({v:,})" for k, v in top.items()),
        }
        if any(h in col.lower() for h in DATE_HINTS) and not col.lower().startswith(("desc", "code")):
            d = pd.to_datetime(s, errors="coerce")
            if d.notna().mean() > 0.5:
                rec.update(date_min=d.min(), date_max=d.max(),
                           impossible_dates=int(((d.dt.year < 1990) | (d.dt.year > 2026)).sum()),
                           unparsable=int(d.isna().sum() - s.isna().sum()))
        rows.append(rec)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="output")
    a = ap.parse_args()
    Path(a.out).mkdir(exist_ok=True)
    summary = []
    for county, kind in FILES:
        df = load(county, kind, a.data)
        dups = int(df.duplicated().sum())
        summary.append({"county": county, "file": kind, "rows": len(df), "columns": df.shape[1],
                        "exact_duplicate_rows": dups, "duplicate_pct": round(dups / len(df) * 100, 1)})
        p = profile(df)
        p.to_csv(Path(a.out) / f"profile_{county}_{kind}.csv", index=False)
        print(f"\n===== {county.upper()} {kind} : {len(df):,} rows x {df.shape[1]} cols, {dups:,} exact duplicate rows")
        print(p[["column", "missing", "missing_pct", "unique"]].to_string(index=False))
    s = pd.DataFrame(summary)
    s.to_csv(Path(a.out) / "file_summary.csv", index=False)
    print("\n===== FILE SUMMARY"); print(s.to_string(index=False))


if __name__ == "__main__":
    main()
