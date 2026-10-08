"""
Step 4: Figures for the README
==============================

Reads the aggregated results from 03_analyze.py (plus the raw data for one
length-matched comparison) and writes PNG charts to figures/.

  topics_by_game.png    How often players mention each topic, per game.
                        Only reviews with 8+ words, because longer reviews mention
                        more topics and review length differs a lot between games.
  stars_by_release.png  Average stars per release (±2 standard errors).
  ads_by_release.png    Share of reviews mentioning ads, per release.

Orange points = change vs the previous release that survives the
Benjamini-Hochberg correction (FDR 5%).

Run:  python 04_figures.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from importlib import import_module
analyze = import_module("03_analyze")   # reuse the same topic keyword lists

RESULTS, FIGS = Path("results"), Path("figures")
NAMES = {"royal_match": "Royal Match", "royal_kingdom": "Royal Kingdom",
         "toon_blast": "Toon Blast", "match_factory": "Match Factory",
         "pixel_flow": "Pixel Flow", "match_villains": "Match Villains"}
GAMES = [g for g in analyze.GAMES if (analyze.RAW_DIR / f"{g}.parquet").exists()]
MIN_WORDS = 8

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"
plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.titlecolor": INK,
    "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "figure.facecolor": "white", "axes.facecolor": "white",
})


def topics_by_game():
    topics = ["ads", "difficulty", "money", "bugs"]
    rows = []
    for g in GAMES:
        df = analyze.load(g)
        df = df[df["text"].str.split().str.len() >= MIN_WORDS]
        rows.append({"game": NAMES[g], "n": len(df),
                     **{t: 100 * df[f"t_{t}"].mean() for t in topics}})
    t = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, len(topics), figsize=(13, 3.6), sharey=True)
    for ax, topic in zip(axes, topics):
        d = t.sort_values("game", ascending=False)
        ax.barh(d["game"], d[topic], color=BLUE, height=0.6)
        for y, v in zip(d["game"], d[topic]):
            ax.text(v + 0.5, y, f"{v:.0f}%", va="center", color=INK, fontsize=9)
        ax.set_title(topic.capitalize(), loc="left")
        ax.set_xlim(0, max(t[topics].max()) * 1.25)
        ax.xaxis.set_major_formatter(lambda x, _: f"{x:.0f}%")
        ax.grid(axis="y", visible=False)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
    fig.suptitle(f"Share of reviews mentioning each topic (reviews with {MIN_WORDS}+ words, last 12 months)",
                 x=0.01, ha="left", color=INK, fontsize=12)
    fig.tight_layout()
    fig.savefig(FIGS / "topics_by_game.png", dpi=160)
    plt.close(fig)
    t.round(1).to_csv(RESULTS / "topics_by_game_8plus_words.csv", index=False)


def per_release(df, value, err=None, ylabel="", fname="", title="", sharey=True):
    games = [g for g in GAMES if g in set(df["game"])]
    ncols = 3
    nrows = -(-len(games) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(13, 3.3 * nrows), sharey=sharey, squeeze=False)
    for ax, g in zip(axes.flat, games):
        d = df[df["game"] == g].sort_values("first_seen")
        if err is not None:
            ax.errorbar(d["first_seen"], d[value], yerr=2 * d[err], fmt="none",
                        ecolor=GRID, elinewidth=2, capsize=0, zorder=1)
        ax.plot(d["first_seen"], d[value], color=BLUE, linewidth=2, zorder=2)
        ax.scatter(d["first_seen"], d[value], s=18, color=BLUE, zorder=3)
        sig = d[d["q"] < analyze.FDR]
        ax.scatter(sig["first_seen"], sig[value], s=60, color=ORANGE, zorder=4,
                   edgecolor="white", linewidth=1.5, label="Significant change vs previous release")
        ax.set_title(NAMES[g], loc="left")
        ax.tick_params(axis="x", labelrotation=0, labelsize=8)
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b\n%Y"))
        ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator(bymonth=[1, 4, 7, 10]))
        ax.set_ylabel(ylabel)
    for ax in list(axes.flat)[len(games):]:
        ax.set_visible(False)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles[:1] or [plt.Line2D([], [], marker="o", color=ORANGE, linestyle="")],
               ["Significant change vs previous release (FDR 5%)"],
               loc="upper right", frameon=False, fontsize=9)
    fig.suptitle(title, x=0.01, ha="left", color=INK, fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(FIGS / fname, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    FIGS.mkdir(exist_ok=True)
    releases = pd.read_csv(RESULTS / "releases.csv", parse_dates=["first_seen"])
    releases = releases[~releases["censored"]]
    topics = pd.read_csv(RESULTS / "topics_by_version.csv", parse_dates=["first_seen"])

    topics_by_game()
    per_release(releases, "avg_stars", err="se", ylabel="Average stars",
                fname="stars_by_release.png",
                title="Average rating per release (bars: ±2 standard errors)")
    ads = topics[topics["topic"] == "ads"]
    per_release(ads, "pct_mentioning", ylabel="% of reviews", fname="ads_by_release.png",
                title="Share of reviews mentioning ads, per release", sharey=False)
    print("Figures saved to figures/")
