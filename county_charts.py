"""Standard charts and metrics shared by every county notebook.

Every county builds one standardized case table (`std`) and calls the same
functions, so all counties produce the same figures, measured the same way,
saved under the same file names.

std columns (one row per case = docket x defendant):
    case_key      unique case id
    year          filing year (int, 2017-2024)
    outcome       shared bucket: Trial Conviction, Plea, CWOF, Diversion,
                  Acquittal, Dismissal, Other  (pending cases excluded)
    offense       offense category of the most serious / lead charge
    court         court name
    race, sex     defendant race and sex ("Unknown" kept as a group)
    days          days from filing to disposition (NaN if negative / missing)
    prior_record  "0", "1-2", "3+" cases in the prior 3 years, or "Unknown"

vol: Series indexed by filing year with the number of filed criminal cases
     (open cases included).

bail_std columns (Q5; one row per case with a bail record, first arraignment):
    case_key        unique case id (must match std / filed cases)
    year            filing year of the case (int)
    status          "PR", "Cash Bail", "Held Without Bail"; anything else -> "Unknown"
    unable_to_post  True if cash bail was set and not posted, False if posted,
                    NaN if the county can't tell
    amount          cash bail amount set ($), NaN if none
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from viz_style import (stacked_pct_bar, save_fig, OUTCOME_COLORS, TEXT_SECONDARY,
                       BAIL_COLORS, BAIL_ORDER)

BLUE = OUTCOME_COLORS["Trial Conviction"]
MIN_CELL = 30
LOOKBACK_YEARS = 3
EVENTS = {"MA CJ reform act": "2018-04-13", "COVID court closures": "2020-03-16"}
STD_COLS = ["case_key", "year", "outcome", "offense", "court", "race", "sex", "days", "prior_record"]
CONVICTED = ["Trial Conviction", "Plea"]


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------
def check_std(std):
    missing = [c for c in STD_COLS if c not in std.columns]
    assert not missing, f"std is missing columns: {missing}"
    out = std.copy()
    out["dismissed"] = out["outcome"].eq("Dismissal")
    out["convicted"] = out["outcome"].isin(CONVICTED)
    return out


def prior_record_3yr(hist, years=LOOKBACK_YEARS):
    """hist: DataFrame indexed by case_key with columns person, filing_date.
    Use ALL filed cases (any year) so cases early in the window see history.
    Returns a Series of "0" / "1-2" / "3+" per case_key."""
    h = hist.dropna(subset=["person", "filing_date"]).copy()
    code = pd.factorize(h["person"])[0].astype(np.int64)
    day = (pd.to_datetime(h["filing_date"]) - pd.Timestamp("1900-01-01")).dt.days.astype(np.int64)
    big = 10_000_000
    key = code * big + day
    order = np.argsort(key.values, kind="stable")
    keys = key.values[order]
    start = keys - 365 * years
    n_prior = np.searchsorted(keys, keys, "left") - np.searchsorted(keys, start, "left")
    counts = pd.Series(n_prior, index=h.index[order])
    return pd.cut(counts, [-1, 0, 2, np.inf], labels=["0", "1-2", "3+"]).astype(str)


def _events(ax):
    ymax = ax.get_ylim()[1]
    for lbl, d in EVENTS.items():
        t = pd.Timestamp(d)
        x = t.year + (t.dayofyear - 1) / 365
        ax.axvline(x, color="grey", ls="--", lw=1)
        ax.text(x, ymax, f" {lbl}", fontsize=10, va="top", color="grey")


def _title(county, text, scope=""):
    return f"{county.title()}{' (' + scope + ')' if scope else ''}: {text}"


# ---------------------------------------------------------------------------
# Q1 / Q2  Volume and per capita
# ---------------------------------------------------------------------------
def volume_table(vol):
    t = vol.rename("cases").to_frame()
    t["pct_change_yoy"] = (t["cases"].pct_change() * 100).round(1)
    t["pct_change_vs_2017"] = ((t["cases"] / t["cases"].iloc[0] - 1) * 100).round(1)
    return t


def plot_volume(vol, county, path, scope=""):
    t = volume_table(vol)
    fig, ax = plt.subplots()
    ax.bar(t.index, t["cases"], color=BLUE, width=0.7)
    for x, n, p in zip(t.index, t["cases"], t["pct_change_yoy"]):
        lbl = f"{n:,}" + (f"\n({p:+.0f}%)" if pd.notna(p) else "")
        ax.text(x, n, lbl, ha="center", va="bottom", fontsize=11)
    ax.set_xticks(list(t.index))
    ax.set_ylim(0, t["cases"].max() * 1.2)
    ax.set(xlabel="Filing year", ylabel="Cases filed",
           title=_title(county, "criminal cases filed per year", scope))
    _events(ax)
    save_fig(fig, path)
    plt.show()
    return t


def plot_per_capita(vol, population, county, path, scope=""):
    pop = pd.Series(population, dtype="float")
    if pop.reindex(vol.index).isna().any():
        print("Q2: fill in annual population for every year to compute per-capita rates.")
        return None
    rate = (vol / pop.reindex(vol.index) * 10_000).round(1)
    fig, ax = plt.subplots()
    ax.plot(rate.index, rate.values, marker="o", markersize=8, linewidth=2, color=BLUE)
    for x, v in zip(rate.index, rate.values):
        ax.annotate(f"{v:.0f}", (x, v), xytext=(0, 8), textcoords="offset points",
                    ha="center", fontsize=11)
    ax.set_xticks(list(rate.index))
    ax.set_ylim(0, rate.max() * 1.25)
    ax.set(xlabel="Filing year", ylabel="Cases per 10,000 residents",
           title=_title(county, "cases filed per 10,000 residents", scope))
    _events(ax)
    save_fig(fig, path)
    plt.show()
    return rate.rename("cases_per_10k").to_frame()


# ---------------------------------------------------------------------------
# Q3  Case outcomes
# ---------------------------------------------------------------------------
def outcome_table(std):
    s = check_std(std)
    overall = s["outcome"].value_counts().rename("cases").to_frame()
    overall["pct"] = (overall["cases"] / overall["cases"].sum() * 100).round(1)
    by_year = s.groupby("year")["outcome"].value_counts().unstack(fill_value=0)
    return overall, by_year


def plot_outcomes(std, county, path, scope=""):
    overall, by_year = outcome_table(std)
    ax = stacked_pct_bar(by_year, unit="cases", xlabel="Filing year",
                         title=_title(county, "case outcomes by filing year", scope))
    save_fig(ax.figure, path)
    plt.show()
    return overall, (by_year.div(by_year.sum(axis=1), axis=0) * 100).round(1)


# ---------------------------------------------------------------------------
# Q5  Pretrial detention and bail
# ---------------------------------------------------------------------------
BAIL_STD_COLS = ["case_key", "year", "status", "unable_to_post", "amount"]


def check_bail(bail_std):
    missing = [c for c in BAIL_STD_COLS if c not in bail_std.columns]
    assert not missing, f"bail_std is missing columns: {missing}"
    out = bail_std.copy()
    out["status"] = out["status"].where(out["status"].isin(BAIL_ORDER), "Unknown")
    out["year"] = out["year"].astype(int)
    return out


def bail_table(bail_std, n_filed=None):
    """Headline Q5 metrics plus status counts by filing year.
    n_filed: number of filed cases, to report bail-record coverage."""
    b = check_bail(bail_std)
    s = b["status"].value_counts(normalize=True).reindex(BAIL_ORDER, fill_value=0) * 100
    cash = b[b["status"] == "Cash Bail"]
    known = cash["unable_to_post"].dropna().astype(float)
    rows = {}
    if n_filed:
        rows["bail record coverage (% of filed cases)"] = len(b) / n_filed * 100
    rows.update({
        "% PR": s["PR"],
        "% cash bail set": s["Cash Bail"],
        "% held without bail": s["Held Without Bail"],
        "% no status (Unknown)": s["Unknown"],
        "% of cash-bail cases unable to post": known.mean() * 100 if len(known) else np.nan,
        "median cash bail ($)": pd.to_numeric(cash["amount"], errors="coerce").median(),
    })
    by_year = (b.groupby("year")["status"].value_counts().unstack(fill_value=0)
                .reindex(columns=BAIL_ORDER, fill_value=0))
    return pd.Series(rows).round(1).to_frame("value"), by_year


def plot_bail(bail_std, county, path, post_path=None, n_filed=None, scope=""):
    """Q5 chart: status at first arraignment by filing year (100% stacked).
    If post_path is given and the county records posting, also draws the
    share of cash-bail cases unable to post, by year."""
    table, by_year = bail_table(bail_std, n_filed)
    ax = stacked_pct_bar(by_year, unit="cases with a bail record", xlabel="Filing year",
                         colors=BAIL_COLORS,
                         title=_title(county, "status at first arraignment", scope))
    save_fig(ax.figure, path)
    plt.show()

    if post_path:
        b = check_bail(bail_std)
        cash = b[(b["status"] == "Cash Bail") & b["unable_to_post"].notna()]
        g = cash.groupby("year")["unable_to_post"].agg(n="size", rate=lambda v: v.astype(float).mean() * 100)
        g = g[g["n"] >= MIN_CELL]
        if g.empty:
            print("Q5: posting not recorded, so no unable-to-post chart.")
        else:
            fig, ax = plt.subplots()
            ax.plot(g.index, g["rate"], marker="o", markersize=8, linewidth=2,
                    color=BAIL_COLORS["Cash Bail"])
            for x, v, n in zip(g.index, g["rate"], g["n"]):
                ax.annotate(f"{v:.0f}%\n(n={int(n):,})", (x, v), xytext=(0, 8),
                            textcoords="offset points", ha="center", fontsize=10)
            ax.set_xticks(list(g.index))
            ax.set_ylim(0, 110)
            ax.set(xlabel="Filing year", ylabel="% of cash-bail cases",
                   title=_title(county, "cash bail set but not posted", scope))
            _events(ax)
            save_fig(fig, post_path)
            plt.show()

    pct = (by_year.div(by_year.sum(axis=1), axis=0) * 100).round(1)
    return table, pct


# ---------------------------------------------------------------------------
# Q6  Time to disposition
# ---------------------------------------------------------------------------
def time_table(std, by):
    t = check_std(std).dropna(subset=["days"])
    g = t.groupby(by)["days"]
    out = pd.DataFrame({"n": g.size(), "median": g.median(),
                        "q1": g.quantile(0.25), "q3": g.quantile(0.75)})
    return out[out["n"] >= MIN_CELL].round(0)


def plot_time(std, by, label, county, path, top=15, scope=""):
    tbl = time_table(std, by)
    d = tbl.sort_values("median", ascending=False).head(top).iloc[::-1]
    y = list(range(len(d)))
    fig, ax = plt.subplots(figsize=(11, 0.45 * len(d) + 2))
    ax.hlines(y, d["q1"], d["q3"], color=BLUE, alpha=0.35, lw=7)
    ax.plot(d["median"], y, "o", color=BLUE, ms=8)
    for yi, (m, q3, n) in enumerate(zip(d["median"], d["q3"], d["n"])):
        ax.text(q3 + 8, yi, f"{m:.0f} days (n={int(n):,})", va="center", fontsize=11)
    ax.set_yticks(y, d.index)
    ax.set_xlim(0, d["q3"].max() * 1.4)
    ax.set_xlabel("Days from filing to disposition (dot = median, bar = IQR)")
    ax.grid(axis="x"); ax.grid(axis="y", visible=False)
    ax.set_title(_title(county, f"time to disposition by {label}", scope))
    save_fig(fig, path)
    plt.show()
    return tbl


def plot_time_by_year(std, county, path, scope=""):
    tbl = time_table(std, "year")
    fig, ax = plt.subplots()
    ax.fill_between(tbl.index, tbl["q1"], tbl["q3"], color=BLUE, alpha=0.2, label="IQR")
    ax.plot(tbl.index, tbl["median"], marker="o", markersize=8, linewidth=2, color=BLUE, label="Median")
    for x, m, n in zip(tbl.index, tbl["median"], tbl["n"]):
        ax.annotate(f"{m:.0f}", (x, m), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=11)
    ax.set_xticks(list(tbl.index))
    ax.set_ylim(0, tbl["q3"].max() * 1.2)
    ax.set(xlabel="Filing year", ylabel="Days from filing to disposition",
           title=_title(county, "time to disposition by filing year", scope))
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    _events(ax)
    save_fig(fig, path)
    plt.show()
    return tbl


# ---------------------------------------------------------------------------
# Q7  Disparities by race and sex
# ---------------------------------------------------------------------------
def rate_table(std, group, ref):
    s = check_std(std)
    g = s.groupby(group).agg(n=("case_key", "size"),
                             dismissal=("dismissed", "mean"),
                             conviction=("convicted", "mean"))
    g = g[g["n"] >= MIN_CELL]
    for m in ["dismissal", "conviction"]:
        g[f"{m}_pct"] = (g[m] * 100).round(1)
        g[f"{m}_ratio_vs_{ref}"] = (g[m] / g.loc[ref, m]).round(2) if ref in g.index else np.nan
    return g.drop(columns=["dismissal", "conviction"]).sort_values("n", ascending=False)


def plot_rates(std, group, ref, label, county, path, scope=""):
    tbl = rate_table(std, group, ref)
    x = np.arange(len(tbl)); w = 0.38
    fig, ax = plt.subplots(figsize=(max(8, 1.6 * len(tbl) + 3), 6))
    b1 = ax.bar(x - w / 2, tbl["dismissal_pct"], w, color=OUTCOME_COLORS["Dismissal"], label="Dismissed")
    b2 = ax.bar(x + w / 2, tbl["conviction_pct"], w, color=OUTCOME_COLORS["Plea"], label="Convicted (plea or trial)")
    for bars in (b1, b2):
        for r in bars:
            ax.text(r.get_x() + r.get_width() / 2, r.get_height(), f"{r.get_height():.0f}%",
                    ha="center", va="bottom", fontsize=10)
    ax.set_xticks(x, [f"{i}\n(n={int(n):,})" for i, n in zip(tbl.index, tbl["n"])], fontsize=11)
    ax.set_ylim(0, max(tbl["dismissal_pct"].max(), tbl["conviction_pct"].max()) * 1.2)
    ax.set(ylabel="% of disposed cases", xlabel="",
           title=_title(county, f"dismissal and conviction rates by {label}", scope))
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    save_fig(fig, path)
    plt.show()
    return tbl


# ---------------------------------------------------------------------------
# Q8  Disparities within offense x prior record
# ---------------------------------------------------------------------------
def q8_table(std, ref="White"):
    s = check_std(std)
    s = s[s["prior_record"].isin(["0", "1-2", "3+"])]
    cell = (s.groupby(["offense", "prior_record", "race"])["dismissed"]
              .agg(n="size", rate="mean").reset_index())
    cell = cell[cell["n"] >= MIN_CELL]
    wide = cell.pivot_table(index=["offense", "prior_record"], columns="race", values="rate")
    n = cell.pivot_table(index=["offense", "prior_record"], columns="race", values="n")
    return (wide * 100).round(1), n, len(s)


def plot_q8_heatmap(std, county, path, groups=("Black", "Hispanic"), ref="White",
                    supplementary=False, scope=""):
    rates, n, n_used = q8_table(std, ref)
    groups = [g for g in groups if g in rates.columns]
    if ref not in rates.columns or not groups:
        print("Q8: not enough cases for a within-cell comparison.")
        return rates
    cmap = LinearSegmentedColormap.from_list("div", ["#2a78d6", "#f0efec", "#e34948"])
    grids = {g: (rates[g] / rates[ref]).unstack("prior_record").reindex(columns=["0", "1-2", "3+"])
             for g in groups}
    rows = sorted(set().union(*[gr.dropna(how="all").index for gr in grids.values()]))
    fig, axes = plt.subplots(1, len(groups), figsize=(6 * len(groups), 0.45 * len(rows) + 2.5), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, g in zip(axes, groups):
        rr = grids[g].reindex(rows)
        im = ax.imshow(rr.values, cmap=cmap, norm=TwoSlopeNorm(1, 0.5, 2), aspect="auto")
        ax.set_xticks(range(3), ["0 priors", "1-2", "3+"])
        ax.set_yticks(range(len(rows)), rows)
        ax.grid(False)
        for (i, j), v in np.ndenumerate(rr.values):
            if pd.notna(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=10)
        ax.set_title(f"{g} / {ref}")
    fig.colorbar(im, ax=axes, label=f"Dismissal rate ratio (1 = same as {ref})", shrink=0.8)
    tag = " [supplementary]" if supplementary else ""
    fig.suptitle(_title(county, f"dismissal rate ratio within same offense and prior record{tag}", scope),
                 fontweight="bold", x=0.01, ha="left")
    save_fig(fig, path)
    plt.show()
    print(f"Q8 cases with known prior record: {n_used:,}")
    return rates


# ---------------------------------------------------------------------------
# Run everything with standard file names
# ---------------------------------------------------------------------------
def standard_figures(std, vol, county, fig_dir, population=None, bail_std=None, prefix=None,
                     scope="", q8_supplementary=False):
    """Draws the full standard figure set. Returns the tables behind each chart.
    population and bail_std are optional: Q2 / Q5 are skipped without them.
    Files are named {county}_qX_... unless a different prefix is given."""
    if prefix is None:
        prefix = f"{county.lower()}_"
    p = lambda name: f"{fig_dir}/{prefix}{name}.png"
    out = {}
    out["q1_volume"] = plot_volume(vol, county, p("q1_volume"), scope)
    if population is not None:
        out["q2_per_capita"] = plot_per_capita(vol, population, county, p("q2_per_capita"), scope)
    out["q3_outcomes"] = plot_outcomes(std, county, p("q3_outcomes_by_year"), scope)
    if bail_std is not None:
        out["q5_bail"] = plot_bail(bail_std, county, p("q5_bail_status"),
                                   post_path=p("q5_unable_to_post"), n_filed=int(vol.sum()), scope=scope)
    out["q6_offense"] = plot_time(std, "offense", "offense category", county, p("q6_time_by_offense"), scope=scope)
    out["q6_court"] = plot_time(std, "court", "court", county, p("q6_time_by_court"), scope=scope)
    out["q6_year"] = plot_time_by_year(std, county, p("q6_time_by_year"), scope)
    out["q7_race"] = plot_rates(std, "race", "White", "race/ethnicity", county, p("q7_rates_by_race"), scope)
    out["q7_sex"] = plot_rates(std, "sex", "Male", "sex", county, p("q7_rates_by_sex"), scope)
    out["q8"] = plot_q8_heatmap(std, county, p("q8_dismissal_ratio_heatmap"),
                                supplementary=q8_supplementary, scope=scope)
    return out
