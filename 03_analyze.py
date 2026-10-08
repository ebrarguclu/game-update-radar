"""
Step 3: First analysis (baseline)
=================================

Answers four questions for each game and saves aggregated results to results/:

  A. Data checks       Is the collected data sound? (duplicates, gaps, empty text)
  B. Release table     For each major version: how many reviews, average stars,
                       and is the change vs the previous version real or noise?
  C. Topic baseline    Which topics (ads, difficulty, bugs...) do players mention,
                       and did that change between versions? Keyword lists, no model.
  D. Churn check       Are reviews WITHOUT a version really from players who quit?
                       Tested against the alternative explanation ("they're just angrier"),
                       plus a random sample of reviews saved for reading by hand.

Only aggregated numbers are written to results/ (safe to publish).
Raw reviews stay in data/raw/ (never published).

Run:  python 03_analyze.py
"""

import math
from pathlib import Path

import numpy as np
import pandas as pd

GAMES = ["royal_match", "royal_kingdom", "toon_blast", "match_factory", "pixel_flow", "match_villains"]
DETAIL_GAMES = ["match_villains", "royal_match"]   # games whose full release table is printed
RAW_DIR = Path("data/raw")
OUT_DIR = Path("results")
SAMPLE_DIR = Path("data/samples")   # raw text samples for manual reading (never published)

MIN_REVIEWS = 100    # a version needs this many reviews to be analysed on its own
FDR = 0.05           # Benjamini-Hochberg: at most 5% of flagged findings may be false (multiple comparisons)
SAMPLE_SIZE = 20     # reviews per group saved for manual reading

# Topic keyword lists (the baseline). \b = word boundary, so "ad" doesn't match "add".
TOPICS = {
    "ads":        r"\bads?\b|\badvert|\bcommercials?\b",
    "difficulty": r"\btoo hard\b|\bdifficult|\bimpossible\b|\bcan'?t (?:beat|pass|win)\b|\bcannot (?:beat|pass)\b|\bstuck\b|\brigged\b|\bunfair\b|\bpay to win\b|\bpay-to-win\b",
    "lives":      r"\blives\b|\bhearts?\b|\benergy\b|\brefill",
    "money":      r"\bexpensive\b|\bprices?\b|\bmoney\b|\bspend|\bpurchas|\bpay\b|\bpaid\b|\bcoins?\b",
    "bugs":       r"\bcrash|\bbugs?\b|\bbuggy\b|\bglitch|\bfreez|\bfroze|\blag|\bwon'?t (?:load|open)\b|\bnot loading\b|\bblack screen\b",
    "progress":   r"\blost (?:my |all )?progress\b|\bprogress (?:is )?(?:gone|lost|reset)\b|\bstart(?:ed)? over\b",
    "content":    r"\bnew levels?\b|\bmore levels\b|\bran out of levels\b|\bwaiting for (?:new )?levels\b|\bfinished all\b",
    "events":     r"\bevents?\b|\bteams?\b|\btournament|\bcompetitions?\b|\brace\b",
}
QUIT_WORDS = r"\buninstall|\bdelet(?:e|ed|ing)\b|\bquit(?:ting)?\b|\bgiv(?:e|ing) up\b|\bgave up\b|\bdone with (?:this|the) game\b|\bstopped playing\b|\bno longer play"


# ------------------------------------------------------------------ helpers --
def se_mean(x: pd.Series) -> float:
    """Standard error of a mean: std / sqrt(n)."""
    return x.std() / np.sqrt(len(x)) if len(x) > 1 else np.nan


def z_diff_means(a: pd.Series, b: pd.Series) -> float:
    """How many standard errors apart are two means? (|z| > 2 ~ unlikely to be chance)"""
    se = np.sqrt(se_mean(a) ** 2 + se_mean(b) ** 2)
    return (b.mean() - a.mean()) / se if se > 0 else np.nan


def z_diff_props(p1, n1, p2, n2) -> float:
    """Same idea for two percentages (proportions)."""
    se = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return (p2 - p1) / se if se > 0 else np.nan


def p_value(z: float) -> float:
    """Two-sided p-value: how likely is a difference this large if nothing really changed?"""
    return math.erfc(abs(z) / math.sqrt(2)) if pd.notna(z) else np.nan


def benjamini_hochberg(p: pd.Series) -> pd.Series:
    """Adjust p-values for running many tests at once.
    Flag findings with q < FDR; then at most FDR of the flagged ones are expected to be false."""
    p = p.astype(float)
    valid = p.dropna().sort_values()
    m = len(valid)
    if m == 0:
        return pd.Series(np.nan, index=p.index)
    ranked = valid * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1].clip(upper=1)
    return pd.Series(q, index=valid.index).reindex(p.index)


def load(game: str) -> pd.DataFrame:
    df = pd.read_parquet(RAW_DIR / f"{game}.parquet")
    df["version"] = df["reviewCreatedVersion"].astype("string")   # versions are labels, not numbers
    df["text"] = df["content"].fillna("").str.lower()
    for topic, pattern in TOPICS.items():
        df[f"t_{topic}"] = df["text"].str.contains(pattern, regex=True)
    df["mentions_quit"] = df["text"].str.contains(QUIT_WORDS, regex=True)
    df["has_version"] = df["version"].notna()
    return df


# ------------------------------------------------------------ A. checks --
def data_checks(game: str, df: pd.DataFrame) -> dict:
    days = pd.date_range(df["at"].min().normalize(), df["at"].max().normalize(), freq="D")
    per_day = df.groupby(df["at"].dt.normalize()).size().reindex(days, fill_value=0)
    return {
        "game": game,
        "reviews": len(df),
        "duplicate_ids": int(df["reviewId"].duplicated().sum()),
        "empty_text_pct": round(100 * (df["text"].str.strip() == "").mean(), 1),
        "first_day": df["at"].min().date(),
        "last_day": df["at"].max().date(),
        "days_with_zero_reviews": int((per_day == 0).sum()),
        "median_words": int(df["text"].str.split().str.len().median()),
        "pct_with_version": round(100 * df["has_version"].mean(), 1),
        "pct_mentioning_any_topic": round(100 * df[[f"t_{t}" for t in TOPICS]].any(axis=1).mean(), 1),
    }


# ------------------------------------------------------ B. release table --
def release_table(game: str, df: pd.DataFrame) -> pd.DataFrame:
    counts = df["version"].value_counts()
    majors = counts[counts >= MIN_REVIEWS].index
    data_start = df["at"].min()

    rows = []
    for v in majors:
        d = df[df["version"] == v]
        rows.append({
            "game": game,
            "version": v,
            "first_seen": d["at"].min(),
            "reviews": len(d),
            "avg_stars": d["score"].mean(),
            "se": se_mean(d["score"]),
            "pct_1_star": 100 * (d["score"] == 1).mean(),
            # First seen within 3 days of the data start -> probably released earlier (censored).
            "censored": d["at"].min() <= data_start + pd.Timedelta(days=3),
        })
    # Order by release date, not by version string ("1.10" vs "1.9" sorts wrongly as text).
    t = pd.DataFrame(rows).sort_values("first_seen").reset_index(drop=True)

    # Compare each version with the previous major version.
    t["stars_change"] = t["avg_stars"].diff()
    t["z"] = np.nan
    for i in range(1, len(t)):
        prev = df.loc[df["version"] == t.loc[i - 1, "version"], "score"]
        cur = df.loc[df["version"] == t.loc[i, "version"], "score"]
        t.loc[i, "z"] = z_diff_means(prev, cur)
    t["p"] = t["z"].apply(p_value)

    # Churn signal around each release: share of version-less reviews
    # in the 14 days after first_seen vs the 14 days before.
    for i, r in t.iterrows():
        before = df[(df["at"] >= r.first_seen - pd.Timedelta(days=14)) & (df["at"] < r.first_seen)]
        after = df[(df["at"] >= r.first_seen) & (df["at"] < r.first_seen + pd.Timedelta(days=14))]
        t.loc[i, "noversion_before_pct"] = 100 * (~before["has_version"]).mean() if len(before) else np.nan
        t.loc[i, "noversion_after_pct"] = 100 * (~after["has_version"]).mean() if len(after) else np.nan
    return t


# ---------------------------------------------------- C. topics by version --
def topics_by_version(game: str, df: pd.DataFrame, releases: pd.DataFrame) -> pd.DataFrame:
    rows = []
    versions = releases["version"].tolist()
    for i, v in enumerate(versions):
        d = df[df["version"] == v]
        for topic in TOPICS:
            col = f"t_{topic}"
            p = d[col].mean()
            row = {"game": game, "version": v, "first_seen": releases.loc[i, "first_seen"],
                   "topic": topic, "reviews": len(d), "pct_mentioning": 100 * p,
                   "avg_stars_when_mentioned": d.loc[d[col], "score"].mean()}
            if i > 0:
                prev = df[df["version"] == versions[i - 1]]
                p0 = prev[col].mean()
                row["change_pct_points"] = 100 * (p - p0)
                row["z"] = z_diff_props(p0, len(prev), p, len(d))
                row["p"] = p_value(row["z"])
            rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------- D. churn check --
def churn_check(game: str, df: pd.DataFrame) -> dict:
    """Hypothesis: version-less reviews come from players who uninstalled.
    Evidence we look for: they mention quitting more often.
    Alternative explanation: they're just angrier, and angry players say 'quit' more.

    1. Test the alternative directly: among reviews WITH a version, does the quit
       rate depend on the star rating?
    2. Compare with- and without-version reviews WITHIN each star level, then
       combine (standardization): "if both groups had the same star ratings,
       how big would the gap be?"
    """
    by_star = []
    for stars in range(1, 6):
        d = df[df["score"] == stars]
        a, b = d[d["has_version"]], d[~d["has_version"]]
        by_star.append({
            "game": game, "stars": stars,
            "quit_pct_with_version": 100 * a["mentions_quit"].mean() if len(a) else np.nan,
            "n_with": len(a),
            "quit_pct_no_version": 100 * b["mentions_quit"].mean() if len(b) else np.nan,
            "n_without": len(b),
        })
    by_star = pd.DataFrame(by_star)

    # Standardized gap: weight each star level by how common it is among version-less reviews.
    ok = (by_star["n_with"] > 0) & (by_star["n_without"] > 0)
    s_ = by_star[ok]
    w = s_["n_without"] / s_["n_without"].sum()
    p1, p2 = s_["quit_pct_with_version"] / 100, s_["quit_pct_no_version"] / 100
    gap = (w * (p2 - p1)).sum()
    se = np.sqrt((w ** 2 * (p1 * (1 - p1) / s_["n_with"] + p2 * (1 - p2) / s_["n_without"])).sum())

    raw_a, raw_b = df[df["has_version"]], df[~df["has_version"]]
    summary = {
        "game": game,
        "quit_pct_with_version": round(100 * raw_a["mentions_quit"].mean(), 1),
        "quit_pct_no_version": round(100 * raw_b["mentions_quit"].mean(), 1),
        "raw_gap_pct_points": round(100 * (raw_b["mentions_quit"].mean() - raw_a["mentions_quit"].mean()), 1),
        "gap_same_stars_pct_points": round(100 * gap, 1),
        "z": round(gap / se, 1) if se > 0 else np.nan,
    }

    # Save random samples for reading by hand (does the keyword list catch real quitting?).
    rng = np.random.default_rng(42)  # fixed seed so the sample is reproducible
    samples = []
    for label, d in [("no_version_mentions_quit", raw_b[raw_b["mentions_quit"]]),
                     ("no_version_no_quit_word", raw_b[~raw_b["mentions_quit"]]),
                     ("with_version_mentions_quit", raw_a[raw_a["mentions_quit"]])]:
        if len(d):
            pick = d.iloc[rng.choice(len(d), size=min(SAMPLE_SIZE, len(d)), replace=False)]
            samples.append(pick[["score", "version", "at", "content"]].assign(group=label))
    if samples:
        pd.concat(samples).to_csv(SAMPLE_DIR / f"{game}_quit_samples.csv", index=False)

    return {"summary": summary, "by_star": by_star}


# ------------------------------------------------------------------ main --
if __name__ == "__main__":
    OUT_DIR.mkdir(exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)

    checks, releases, topics, churn, churn_by_star = [], [], [], [], []
    for game in GAMES:
        df = load(game)
        checks.append(data_checks(game, df))
        r = release_table(game, df)
        releases.append(r)
        topics.append(topics_by_version(game, df, r))
        c = churn_check(game, df)
        churn.append(c["summary"])
        churn_by_star.append(c["by_star"])

    checks = pd.DataFrame(checks)
    releases = pd.concat(releases, ignore_index=True)
    topics = pd.concat(topics, ignore_index=True)
    churn = pd.DataFrame(churn)
    churn_by_star = pd.concat(churn_by_star, ignore_index=True)

    # Multiple comparisons: adjust all p-values together (per family of tests).
    releases["q"] = benjamini_hochberg(releases["p"].where(~releases["censored"]))
    topics["q"] = benjamini_hochberg(topics["p"])

    checks.to_csv(OUT_DIR / "data_checks.csv", index=False)
    releases.to_csv(OUT_DIR / "releases.csv", index=False)
    topics.to_csv(OUT_DIR / "topics_by_version.csv", index=False)
    churn.to_csv(OUT_DIR / "churn_check.csv", index=False)
    churn_by_star.to_csv(OUT_DIR / "churn_check_by_star.csv", index=False)

    print("\n=== A. Data checks ===")
    print(checks.to_string(index=False))

    print("\n=== B. Releases per game (major versions, not censored) ===")
    summary = (releases[~releases["censored"]]
               .groupby("game")
               .agg(releases=("version", "count"),
                    flagged_star_changes=("q", lambda q: int((q < FDR).sum()))))
    print(summary.to_string())

    cols = ["version", "first_seen", "reviews", "avg_stars", "stars_change", "z", "q",
            "pct_1_star", "noversion_before_pct", "noversion_after_pct", "censored"]
    for g in DETAIL_GAMES:
        print(f"\n=== B. {g} release table ===")
        t = releases[releases["game"] == g][cols].copy()
        t["first_seen"] = t["first_seen"].dt.date
        print(t.round(2).to_string(index=False))

    print("\n=== C. Topic mentions, all versions pooled (% of reviews) ===")
    pooled = topics.groupby(["game", "topic"])["pct_mentioning"].mean().unstack().round(1)
    print(pooled.to_string())

    flagged = topics[topics["q"] < FDR]
    print(f"\n=== C. Topic changes that survive multiple-comparison correction "
          f"({len(flagged)} of {topics['p'].notna().sum()} tests, FDR {FDR:.0%}) ===")
    big = flagged.sort_values("z", key=abs, ascending=False).copy()
    big["first_seen"] = big["first_seen"].dt.date
    print(big[["game", "version", "first_seen", "topic", "pct_mentioning",
               "change_pct_points", "z", "q"]].head(12).round(3).to_string(index=False))

    print("\n=== D1. Testing the alternative explanation: quit-word rate by stars (reviews WITH a version) ===")
    alt = churn_by_star.pivot(index="game", columns="stars", values="quit_pct_with_version").round(1)
    alt.columns = [f"{c} star" for c in alt.columns]
    print(alt.to_string())

    print("\n=== D2. Do version-less reviews mention quitting more, at the same star rating? ===")
    print(churn.to_string(index=False))
    print(f"\nRandom samples for reading by hand saved to {SAMPLE_DIR}/")
    print("\nAll results saved to results/")
