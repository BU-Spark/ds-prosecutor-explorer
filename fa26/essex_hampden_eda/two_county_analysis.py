"""Step 2: compare Essex and Hampden on five questions (motor vehicle charges excluded).

  Q1  How do charges end, by charge type and county?
  Q2  How often is cash bail set, and how much, by charge type and county?
  Q3  Do bail and outcomes differ by race or gender for the same charge type?
  Q4  How long do charges take to resolve, and did COVID (2020) change that?
  Q5  Do outcomes and bail differ between courts within each county?

Method notes
  - One row per charge (duplicates removed); cases filed 2017-2025; motor vehicle chapters excluded.
  - Outcome rates use only charges with a final criminal outcome (civil infractions, charges moved
    to Superior Court, pending and unclassified charges are left out).
  - Bail = highest cash bail set on the case (> $0). Essex: bail set at District Court arraignment.
    Hampden: any "Bail Set" value for the case.
  - Race/gender comparisons are "charge-type adjusted": each group's rate per charge type is
    reweighted to the county's overall charge-type mix (direct standardization).
  - Hampden outcome codes are not defined in the data; the grouping below is inferred from
    related fields and must be confirmed with the client.

Usage:  python two_county_analysis.py --data data      (tables are saved to ./output)
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from fa26.essex_hampden_eda.load_data import load, charge_type, MV_CHAPTERS, HAMPDEN_COURTS

CRIMINAL = ["Dismissed/nolle", "Guilty/plea", "CWF/diversion", "Acquitted"]
TYPES = ["Person", "Property", "Drugs", "Weapons", "Vs. justice", "Restraining order", "Public order"]

ESSEX_OUTCOMES = {
    **dict.fromkeys(["Guilty", "Pled Guilty to Charge", "Guilty Probation", "Guilty Filed", "Guilty Fine", "Plea Lesser Offense",
                     "DYS CMTD", "Youthful Offender", "Delinquent", "Delinquent Probation", "Delinquent Filed",
                     "Guilty Verdict Lesser Offense"], "Guilty/plea"),
    **dict.fromkeys(["Continued Without Finding", "Admission to Sufficient Facts", "Pre-Trial Probation", "Pre-Trial Probation Â§87",
                     "Generally Continuance", "Filed Without Change of Plea"], "CWF/diversion"),
    **dict.fromkeys(["Dismissed", "Dismissed Court Costs", "Dismissed Lack of Prosecution W/O Pred.", "Nolle Prosequi",
                     "Dismissed Victim No Show", "Dismissed Marital Privilege", "Dismissed Lack of Evidence", "No True Bill",
                     "Dismissed Lackof Prosecution with Pred.", "Dismissed by Fines", "Dismissed Duplicate Chrg"], "Dismissed/nolle"),
    **dict.fromkeys(["Not Guilty", "Not Guilty by Jury", "Not Guilty Insanity", "Required Finding of Not Guilty",
                     "Directed Verdict"], "Acquitted"),
    **dict.fromkeys(["Not Responsible", "Responsible", "Responsible Filed", "Responsible Fine"], "Civil"),
    **dict.fromkeys(["Dismissed due to Indictment", "Superceding Indictment", "Transferred Jurisdiction", "Federal Prosecution",
                     "Dismissed New Complaint Issued", "Remanded Clerks Hearing"], "Moved"),
}

# Inferred from Dispo Description, Sentence Type and trial fields -- CONFIRM WITH CLIENT
HAMPDEN_OUTCOMES = {
    **dict.fromkeys(["NOP", "2003"], "Dismissed/nolle"),          # 2003 + description INDI -> Moved (handled below)
    **dict.fromkeys(["NOT-RESP", "RESF", "RES", "RESE"], "Civil"),
    **dict.fromkeys(["CWOF", "2004", "276"], "CWF/diversion"),
    **dict.fromkeys(["GLT-CMTD", "GLT-PROB", "2000", "GLT-FILE", "TS", "GLTSS", "GLT-CON", "GLT-FINE", "GCS", "GCC",
                     "GLT-LIFE", "GLESS", "DYSC", "DYSS", "DYS"], "Guilty/plea"),
    **dict.fromkeys(["2001", "NTGLT", "NGI", "DIRV"], "Acquitted"),
}


def finish_outcomes(raw, groups):
    og = raw.map(groups)
    og[og.isna() & raw.notna()] = "Other"
    return og.fillna("Pending/none")


def essex_charges(data):
    f = load("essex", "filed", data)
    f["dispo_date"] = pd.to_datetime(f["Date Dspstn"], errors="coerce")
    start = f.groupby("Id Cs")["Date Evnt"].min()
    f = f.sort_values("dispo_date").drop_duplicates("Id Dfndnt Chrg", keep="last")
    out = pd.DataFrame({
        "county": "Essex", "case": f["Id Cs"].astype(str), "charge_id": f["Id Dfndnt Chrg"].astype(str),
        "order": f["Id Dfndnt Chrg"].astype(float), "code": f["Code Chrg"], "start": f["Id Cs"].map(start).values,
        "dispo_date": f["dispo_date"], "outcome": finish_outcomes(f["Desc Dspstn"], ESSEX_OUTCOMES),
        "race": f["Code Rc"].astype(str), "sex": f["Code Sex"].astype(str), "court": f["Desc Crt Lctn (ACTION EVENT)"].astype(str)})
    b = load("essex", "bail", data)
    bail = b[b["Desc Dfndnt Sts"] == "Bail Set at D/C Arraignment"].groupby("Id Cs")["Amnt Bl Set"].max()
    bail.index = bail.index.astype(str)
    return out, bail


def hampden_charges(data):
    f = load("hampden", "filed", data).drop_duplicates()
    f["dispo_date"] = pd.to_datetime(f["Dispo Date"], errors="coerce")
    f["filing_date"] = pd.to_datetime(f["Filing Date"], errors="coerce")
    f["did"] = f["Defendant ID Number"].astype(str).str.strip()
    f["key"] = f["did"] + "|" + f["Count"].astype(str) + "|" + f["Charge Code"].astype(str)
    start = f.groupby("did")["filing_date"].min()
    f = f.sort_values("dispo_date").drop_duplicates("key", keep="last")
    code = f["Dispo Code"].astype(str).str.strip().where(f["Dispo Code"].notna())
    og = finish_outcomes(code, HAMPDEN_OUTCOMES)
    og[(code == "2003") & (f["Dispo Description"].astype(str) == "INDI")] = "Moved"   # dismissed due to indictment
    out = pd.DataFrame({
        "county": "Hampden", "case": f["did"], "charge_id": f["key"], "order": pd.to_numeric(f["Count"], errors="coerce"),
        "code": f["Charge Code"], "start": f["did"].map(start).values, "dispo_date": f["dispo_date"], "outcome": og,
        "race": f["Race"].astype(str).replace({"HW": "H", "HB": "H"}), "sex": f["Gender"].astype(str),
        "court": f["Court"].map(HAMPDEN_COURTS).fillna(f["Court"].astype(str))})
    b = load("hampden", "bail", data).drop_duplicates()
    bail = b.assign(case=b["Case #"].astype(str).str.strip()).groupby("case")["Bail Set"].max()
    return out, bail


def adjusted_rates(df, group_col, value_col):
    """Rate per group, standardized to the overall charge-type mix of df."""
    weights = df["ctype"].value_counts(normalize=True)
    rates = df.pivot_table(index="ctype", columns=group_col, values=value_col, aggfunc="mean")
    return (rates.mul(weights, axis=0).sum() / weights[rates.index].sum() * 100).round(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="output")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(exist_ok=True)
    save = lambda df, name: (df.to_csv(out / f"{name}.csv"), print(f"\n--- {name}\n{df}"))

    e, ebail = essex_charges(a.data)
    h, hbail = hampden_charges(a.data)
    ch = pd.concat([e, h], ignore_index=True)
    ch[["chapter", "ctype"]] = ch["code"].apply(lambda x: pd.Series(charge_type(x)))
    ch["year"] = ch["start"].dt.year
    ch = ch[ch["year"].between(2017, 2025)]
    print("Motor vehicle share of charges:", ch["chapter"].isin(MV_CHAPTERS).groupby(ch["county"]).mean().round(3).to_dict())
    ch = ch[~ch["chapter"].isin(MV_CHAPTERS)]
    save(ch.groupby("county").agg(charges=("charge_id", "size"), cases=("case", "nunique")), "coverage_non_mv")

    # ---- Q1 outcomes
    cr = ch[ch["outcome"].isin(CRIMINAL)]
    save(pd.crosstab(cr["county"], cr["outcome"], normalize="index").mul(100).round(1)[CRIMINAL]
         .assign(n=cr["county"].value_counts()), "q1_outcomes_by_county")
    t = cr[cr["ctype"].isin(TYPES)]
    for name, lab in [("guilty", "Guilty/plea"), ("dismissed", "Dismissed/nolle")]:
        save(pd.crosstab(t["ctype"], t["county"], values=t["outcome"] == lab, aggfunc="mean").mul(100).round(1),
             f"q1_{name}_pct_by_type")

    # ---- case-level table (lead charge = first non-MV charge on the case)
    cases = (ch.sort_values("order").groupby(["county", "case"])
             .agg(ctype=("ctype", "first"), race=("race", "first"), sex=("sex", "first"), court=("court", "first"),
                  year=("year", "first")).reset_index())
    cases["bail"] = np.where(cases["county"] == "Essex", cases["case"].map(ebail), cases["case"].map(hbail))
    cases["cash_bail"] = cases["bail"].fillna(0) > 0
    paid = cases[cases["cash_bail"]]

    # ---- Q2 bail
    q2 = cases.groupby("county").agg(cases=("case", "size"), pct_cash_bail=("cash_bail", "mean"))
    q2["pct_cash_bail"] = (q2["pct_cash_bail"] * 100).round(1)
    q2["median_bail"] = paid.groupby("county")["bail"].median(); q2["p90_bail"] = paid.groupby("county")["bail"].quantile(.9)
    save(q2, "q2_bail_by_county")
    ct = cases[cases["ctype"].isin(TYPES)]
    save(pd.crosstab(ct["ctype"], ct["county"], values=ct["cash_bail"], aggfunc="mean").mul(100).round(1), "q2_bail_pct_by_type")
    save(paid[paid["ctype"].isin(TYPES)].pivot_table(index="ctype", columns="county", values="bail", aggfunc="median"),
         "q2_median_bail_by_type")

    # ---- Q3 race and gender (charge-type adjusted)
    rows = []
    for cty in ["Essex", "Hampden"]:
        c_ = cases[cases["county"] == cty]; r_ = cr[cr["county"] == cty]
        for col, keep in [("race", ["W", "B", "H"]), ("sex", ["M", "F"])]:
            cc = c_[c_[col].isin(keep)]; rr = r_[r_[col].isin(keep)].assign(g=lambda d: d["outcome"] == "Guilty/plea",
                                                                             d=lambda d: d["outcome"] == "Dismissed/nolle")
            for grp in keep:
                rows.append({"county": cty, "variable": col, "group": grp,
                             "cash_bail_raw": round(cc.loc[cc[col] == grp, "cash_bail"].mean() * 100, 1),
                             "cash_bail_adjusted": adjusted_rates(cc, col, "cash_bail").get(grp),
                             "guilty_adjusted": adjusted_rates(rr, col, "g").get(grp),
                             "dismissed_adjusted": adjusted_rates(rr, col, "d").get(grp)})
    save(pd.DataFrame(rows).set_index(["county", "variable", "group"]), "q3_race_gender_adjusted")
    rc = cases[cases["race"].isin(["W", "B", "H"]) & cases["ctype"].isin(TYPES)]
    save(rc.pivot_table(index=["county", "ctype"], columns="race", values="cash_bail", aggfunc="mean").mul(100).round(1),
         "q3_bail_pct_by_race_and_type")
    save(cases.groupby("county")["race"].apply(lambda s: round((~s.isin(["W", "B", "H", "A", "I"])).mean() * 100, 1)),
         "q3_race_missing_or_unknown_pct")

    # ---- Q4 time to resolution, by filing year
    ch["days"] = (ch["dispo_date"] - ch["start"]).dt.days
    ok = ch[ch["dispo_date"].notna() & ch["days"].between(0, 365 * 15)]
    save(ok.pivot_table(index="year", columns="county", values="days", aggfunc="median"), "q4_median_days_by_filing_year")
    ch["within_1yr"] = ch["dispo_date"].notna() & ch["days"].between(0, 365)
    save(ch.pivot_table(index="year", columns="county", values="within_1yr", aggfunc="mean").mul(100).round(1),
         "q4_pct_resolved_within_1yr")
    save(ch.assign(open=ch["dispo_date"].isna()).pivot_table(index="year", columns="county", values="open", aggfunc="mean")
         .mul(100).round(1), "q4_pct_no_disposition_yet")

    # ---- Q5 courts
    q5 = cr.groupby(["county", "court"]).agg(charges=("charge_id", "size"),
                                             guilty_pct=("outcome", lambda s: round((s == "Guilty/plea").mean() * 100, 1)),
                                             dismissed_pct=("outcome", lambda s: round((s == "Dismissed/nolle").mean() * 100, 1)))
    q5 = q5.join(cases.groupby(["county", "court"]).agg(cases=("case", "size"),
                                                        cash_bail_pct=("cash_bail", lambda s: round(s.mean() * 100, 1))))
    q5 = q5.join(paid.groupby(["county", "court"])["bail"].median().rename("median_bail"))
    save(q5[q5["cases"] >= 500].sort_values(["county", "cases"], ascending=[True, False]), "q5_courts")


if __name__ == "__main__":
    main()
