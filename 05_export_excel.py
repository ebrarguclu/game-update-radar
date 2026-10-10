"""
Step 5: Export results to a formatted Excel workbook
====================================================

Opening the CSV files directly in Excel can silently corrupt numbers when the
computer uses a locale with a comma decimal separator (e.g. Turkish):
"4.15" may become the date "15 April" and "12.145" may become 12145.
Writing a real .xlsx file from Python avoids that entirely.

Sheets:
  Match Villains   release table for Match Villains
  Releases         release table for all games
  Topic changes    topic share per release and change vs previous release
  Topics by game   topic share per game (reviews with 8+ words)
  Churn check      quit-word test (overall and by star rating)
  Data checks      data health per game

Rows where the change vs the previous release is significant (q < 0.05)
are highlighted. Header row is frozen and every sheet has filters.

Run:  python 05_export_excel.py   ->  results/game_update_radar.xlsx
"""

from pathlib import Path

import pandas as pd
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

RESULTS = Path("results")
OUT = RESULTS / "game_update_radar.xlsx"

HEADER_FILL = PatternFill("solid", start_color="1F3A5F")
HIGHLIGHT = PatternFill("solid", start_color="FDE3D6")
FDR = 0.05


def load(name, **kw):
    path = RESULTS / name
    return pd.read_csv(path, **kw) if path.exists() else None


def format_sheet(ws, df, q_col=None):
    # header
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    # column widths and number formats
    for i, col in enumerate(df.columns, start=1):
        letter = get_column_letter(i)
        width = max(len(str(col)), *(len(str(v)) for v in df[col].head(200))) if len(df) else len(str(col))
        ws.column_dimensions[letter].width = min(max(width + 2, 9), 40)
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            fmt = "yyyy-mm-dd"
        elif pd.api.types.is_float_dtype(df[col]):
            fmt = "0.000" if col in ("p", "q", "se") else "0.00"
        elif pd.api.types.is_integer_dtype(df[col]):
            fmt = "#,##0"
        else:
            fmt = None
        if fmt:
            for row in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                row[0].number_format = fmt

    # highlight significant rows (q < 0.05)
    if q_col and q_col in df.columns and len(df):
        q_letter = get_column_letter(list(df.columns).index(q_col) + 1)
        last_col = get_column_letter(len(df.columns))
        rng = f"A2:{last_col}{len(df) + 1}"
        ws.conditional_formatting.add(
            rng, FormulaRule(formula=[f'AND(ISNUMBER(${q_letter}2), ${q_letter}2<{FDR})'], fill=HIGHLIGHT))


def tidy_releases(df):
    cols = ["game", "version", "first_seen", "reviews", "avg_stars", "stars_change", "z", "q",
            "pct_1_star", "noversion_before_pct", "noversion_after_pct", "censored"]
    df = df[[c for c in cols if c in df.columns]].copy()
    df["first_seen"] = pd.to_datetime(df["first_seen"]).dt.normalize()
    return df


if __name__ == "__main__":
    releases = load("releases.csv", dtype={"version": str})
    topics = load("topics_by_version.csv", dtype={"version": str})
    sheets = []

    if releases is not None:
        rel = tidy_releases(releases)
        sheets.append(("Match Villains", rel[rel["game"] == "match_villains"], "q"))
        sheets.append(("Releases", rel, "q"))
    if topics is not None:
        t = topics[["game", "version", "first_seen", "topic", "reviews", "pct_mentioning",
                    "change_pct_points", "z", "q", "avg_stars_when_mentioned"]].copy()
        t["first_seen"] = pd.to_datetime(t["first_seen"]).dt.normalize()
        sheets.append(("Topic changes", t, "q"))
    for title, name in [("Topics by game", "topics_by_game_8plus_words.csv"),
                        ("Churn check", "churn_check.csv"),
                        ("Churn by star", "churn_check_by_star.csv"),
                        ("Data checks", "data_checks.csv")]:
        df = load(name)
        if df is not None:
            sheets.append((title, df, None))

    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
        for title, df, q_col in sheets:
            df.to_excel(writer, sheet_name=title, index=False)
            format_sheet(writer.sheets[title], df, q_col)
    print(f"Saved {OUT} ({len(sheets)} sheets)")
