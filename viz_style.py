"""Shared plotting style for the prosecutor explorer analyses.

counts passed to stacked_pct_bar must be RAW COUNTS (not percents):
one row per bar (year, court, ...), one column per outcome.
"""

import matplotlib.pyplot as plt
import pandas as pd

# One fixed color per outcome, used in every county and chart.
# Don't reorder: the order keeps neighboring segments colorblind-safe.
OUTCOME_COLORS = {
    "Dismissed":      "#2a78d6",  # blue
    "Nolle Prosequi": "#eb6834",  # orange
    "CWOF":           "#1baf7a",  # aqua
    "Guilty":         "#eda100",  # yellow (plea or finding)
    "Not Guilty":     "#e87ba4",  # magenta
    "Other Plea":     "#008300",  # green
    "Other":          "#8a8984",  # gray
    "Missing":        "#c9c8c2",  # light gray
}
OUTCOME_ORDER = list(OUTCOME_COLORS)

# Map raw codes/spellings onto the shared labels. Add variants as you find them.
OUTCOME_ALIASES = {
    "NOPR": "Nolle Prosequi",
    "Nolle prosequi": "Nolle Prosequi",
    "DISM": "Dismissed",
    "Dismissal": "Dismissed",
    "Continuance without a finding": "CWOF",
    "Plea": "Guilty",
    "Guilty plea": "Guilty",
    "Not guilty": "Not Guilty",
    "Unknown": "Missing",
}

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"


def normalize_outcome(label):
    if pd.isna(label):
        return "Missing"
    label = OUTCOME_ALIASES.get(label, label)
    return label if label in OUTCOME_COLORS else "Other"


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
                    min_label_pct=6, show_pct_labels=True, legend_title=None):
    """100% stacked bar with n above each bar.

    counts: DataFrame of raw counts, index = bars, columns = outcomes.
    unit:   "cases" or "charges", shown in the y label so every chart
            says what it counts.
    """
    counts = counts.copy()
    counts.columns = [normalize_outcome(c) for c in counts.columns]
    counts = counts.T.groupby(level=0).sum().T
    cols = [c for c in OUTCOME_ORDER if c in counts.columns]
    counts = counts[cols]

    totals = counts.sum(axis=1)
    pct = counts.div(totals.where(totals > 0), axis=0).fillna(0) * 100

    if ax is None:
        _, ax = plt.subplots()

    x = list(range(len(pct)))
    bottom = pd.Series(0.0, index=pct.index)
    for outcome in cols:
        vals = pct[outcome]
        ax.bar(x, vals, bottom=bottom, width=0.7, color=color_for(outcome),
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
