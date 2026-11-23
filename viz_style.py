"""Shared plotting style and outcome buckets for the prosecutor explorer analyses.

Outcome buckets follow the team's agreed criteria (Final Questions, Q3):
Trial Conviction, Plea, CWOF (reported separately), Diversion, Acquittal,
Dismissal, Other, Unknown. Each county maps its own disposition codes onto
these in its notebook (see OUTCOME_ALIASES for common ones).

counts passed to stacked_pct_bar must be RAW COUNTS (not percents):
one row per bar (year, court, ...), one column per outcome.
"""

import matplotlib.pyplot as plt
import pandas as pd

# One fixed color per outcome, used in every county and chart.
# Don't reorder: the order keeps neighboring segments colorblind-safe.
OUTCOME_COLORS = {
    "Trial Conviction": "#2a78d6",  # blue
    "Plea":             "#eb6834",  # orange
    "CWOF":             "#1baf7a",  # aqua
    "Diversion":        "#eda100",  # yellow
    "Acquittal":        "#e87ba4",  # magenta
    "Dismissal":        "#008300",  # green
    "Other":            "#8a8984",  # gray
    "Unknown":          "#c9c8c2",  # light gray
}
OUTCOME_ORDER = list(OUTCOME_COLORS)

# Q5: status at first arraignment. Same palette, fixed order.
BAIL_COLORS = {
    "PR":                "#1baf7a",  # aqua
    "Cash Bail":         "#eb6834",  # orange
    "Held Without Bail": "#2a78d6",  # blue
    "Unknown":           "#c9c8c2",  # light gray
}
BAIL_ORDER = list(BAIL_COLORS)

# Case-level rule: a case gets its most severe outcome across all charges.
SEVERITY = ["Trial Conviction", "Plea", "CWOF", "Diversion",
            "Acquittal", "Dismissal", "Other", "Unknown"]

# Common raw labels -> shared buckets. Counties add their own mappings in
# their notebook. Nolle prosequi counts as Dismissal for shared questions.
OUTCOME_ALIASES = {
    "Dismissed": "Dismissal",
    "DISM": "Dismissal",
    "Nolle Prosequi": "Dismissal",
    "NOPR": "Dismissal",
    "Not Guilty": "Acquittal",
    "Continuance without a finding": "CWOF",
}

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"


def normalize_outcome(label):
    """Map a raw label to a shared bucket. Missing -> Unknown, unmapped -> Other.
    'Pending' passes through so open cases can be excluded."""
    if pd.isna(label):
        return "Unknown"
    label = OUTCOME_ALIASES.get(label, label)
    if label == "Pending":
        return "Pending"
    return label if label in OUTCOME_COLORS else "Other"


def case_outcome(outcomes):
    """Most severe outcome across a case's charges.
    Returns 'Pending' if any charge is still open (exclude these from outcome charts)."""
    s = set(outcomes)
    if "Pending" in s:
        return "Pending"
    for o in SEVERITY:
        if o in s:
            return o
    return "Other"


def color_for(outcome):
    return OUTCOME_COLORS.get(outcome, OUTCOME_COLORS["Other"])


def set_style(font_size=14):
    """Call once at the top of a notebook. Sizes are set for slides."""
    plt.rcParams.update({
        "figure.figsize": (11, 6),
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.size": font_size,
        "axes.titlesize": font_size + 4,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.labelsize": font_size + 1,
        "xtick.labelsize": font_size,
        "ytick.labelsize": font_size,
        "legend.fontsize": font_size - 1,
        "legend.frameon": False,
        "text.color": TEXT_PRIMARY,
        "axes.labelcolor": TEXT_SECONDARY,
        "xtick.color": TEXT_SECONDARY,
        "ytick.color": TEXT_SECONDARY,
        "axes.edgecolor": GRID,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "grid.color": GRID,
    })


def stacked_pct_bar(counts, unit="cases", title=None, xlabel=None, ax=None,
                    min_label_pct=6, show_pct_labels=True, legend_title=None, colors=None):
    """100% stacked bar with n above each bar.

    counts: DataFrame of raw counts, index = bars, columns = outcomes.
    unit:   "cases" or "charges", shown in the y label.
    colors: optional {category: color} for non-outcome categories (e.g. BAIL_COLORS).
            Its order sets the stack order. Default: the shared outcome buckets.
    """
    counts = counts.copy()
    if colors is None:
        counts.columns = [normalize_outcome(c) for c in counts.columns]
        counts = counts.T.groupby(level=0).sum().T
        colors = OUTCOME_COLORS
    cols = [c for c in colors if c in counts.columns]
    counts = counts[cols]

    totals = counts.sum(axis=1)
    pct = counts.div(totals.where(totals > 0), axis=0).fillna(0) * 100

    if ax is None:
        _, ax = plt.subplots()

    x = list(range(len(pct)))
    bottom = pd.Series(0.0, index=pct.index)
    for outcome in cols:
        vals = pct[outcome]
        ax.bar(x, vals, bottom=bottom, width=0.7, color=colors[outcome],
               label=outcome, edgecolor=SURFACE, linewidth=2)
        if show_pct_labels:
            for xi, v, b in zip(x, vals, bottom):
                if v >= min_label_pct:
                    ax.text(xi, b + v / 2, f"{v:.0f}%", ha="center", va="center",
                            fontsize=plt.rcParams["font.size"] - 2, color=TEXT_PRIMARY)
        bottom += vals

    for xi, n in zip(x, totals):
        ax.text(xi, 101.5, f"n={int(n):,}", ha="center", va="bottom",
                fontsize=plt.rcParams["font.size"] - 2, color=TEXT_SECONDARY)

    ax.set_xticks(x)
    ax.set_xticklabels([str(i) for i in pct.index])
    ax.set_ylim(0, 108)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.set_ylabel(f"% of {unit}")
    if xlabel:
        ax.set_xlabel(xlabel)
    if title:
        ax.set_title(title, pad=24)

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], title=legend_title,
              loc="upper left", bbox_to_anchor=(1.01, 1))
    return ax


def save_fig(fig, path, dpi=300):
    """Save at slide quality. Use this instead of screenshots."""
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
