"""Step 3: evidence for duplicate rows in the Hampden files.

- Counts exact duplicate rows in each Hampden file and lists the most-repeated rows
  with their Excel row numbers (header = row 1).
- For the Bail file (no count column), compares rows per defendant+charge with the
  number of counts of that charge in the Filed file, to separate legitimate repeated
  counts from likely true duplicates.

Usage:  python check_duplicates.py --data data
"""
import argparse
from pathlib import Path
import pandas as pd
from load_data import load


def top_repeats(df, n=3):
    key = pd.util.hash_pandas_object(df, index=False)
    groups = pd.Series(df.index + 2, index=df.index).groupby(key.values)
    sizes = groups.size().sort_values(ascending=False).head(n)
    out = []
    for k, cnt in sizes.items():
        rows = groups.get_group(k).head(5).tolist()
        text = " | ".join(str(v) for v in df.loc[rows[0] - 2].tolist())[:150]
        out.append((int(cnt), rows, text))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    a = ap.parse_args()
    for kind in ["filed", "disposed", "bail"]:
        df = load("hampden", kind, a.data)
        d = int(df.duplicated().sum())
        print(f"\n===== Hampden {kind}: {len(df):,} rows, {len(df) - d:,} unique, {d:,} extra copies ({d / len(df) * 100:.1f}%)")
        for cnt, rows, text in top_repeats(df):
            print(f"  {cnt} copies, first Excel rows {rows}: {text}")

    f = load("hampden", "filed", a.data).drop_duplicates()
    b = load("hampden", "bail", a.data)
    f["did"] = f["Defendant ID Number"].astype(str).str.strip()
    b["did"] = b["Case #"].astype(str).str.strip()
    counts = f.groupby(["did", "Charge Description"]).size().rename("counts_filed")
    rows = b.groupby(["did", "Charges"]).size().rename("rows_bail")
    j = pd.concat([rows, counts], axis=1, join="inner")
    explained = j[["rows_bail", "counts_filed"]].min(axis=1).sum()
    excess = (j["rows_bail"] - j["counts_filed"]).clip(lower=0).sum()
    print(f"\nBail rows matched to a filed charge: {j['rows_bail'].sum():,}")
    print(f"  explained by number of counts: {explained:,}")
    print(f"  beyond number of counts (likely true duplicates): {excess:,} ({excess / len(b) * 100:.1f}% of bail file)")
    print(f"  pairs where bail rows == counts: {(j.rows_bail == j.counts_filed).mean():.1%}; bail rows > counts: {(j.rows_bail > j.counts_filed).mean():.1%}")


if __name__ == "__main__":
    main()
