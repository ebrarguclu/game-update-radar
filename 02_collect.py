"""
Step 2: Collect 12 months of Google Play reviews (and keep them up to date)
==========================================================================

The same script does two jobs:

  * First run   -> "backfill": walks back DAYS_BACK days for each game.
  * Later runs  -> "incremental": only fetches reviews newer than what we
                   already have, then stops. A daily run needs only a few
                   requests per game.

Design principles (see NOTES.md):
  - Checkpointing: progress is saved every SAVE_EVERY pages, so an interrupted
    run loses at most a few pages of work.
  - Idempotency: reviews are de-duplicated by reviewId, so running the script
    twice never creates duplicates.
  - Data minimization: usernames and profile images are never stored.
  - Reproducibility: every row records when it was collected (scraped_at).

Run:
    python 02_collect.py                    # all games
    python 02_collect.py pixel_flow         # one game
"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from google_play_scraper import Sort, reviews

GAMES = {
    "royal_match":   "com.dreamgames.royalmatch",
    "royal_kingdom": "com.dreamgames.royalkingdom",
    "toon_blast":    "net.peakgames.toonblast",
    "match_factory": "net.peakgames.match",
    "pixel_flow":    "com.loomgames.pixelflow",
    "match_villains": "com.goodjobgames.matchvillains",  # Good Job Games
}

DAYS_BACK = 365        # history depth for the first run (decision in NOTES.md)
PAGE_SIZE = 200        # Google Play's maximum per request
PAUSE_SECONDS = 1.5    # polite delay between requests
SAVE_EVERY = 10        # checkpoint: save to disk every 10 pages
MAX_RETRIES = 3        # retry a failed request this many times

KEEP_COLUMNS = ["reviewId", "content", "score", "thumbsUpCount",
                "reviewCreatedVersion", "at", "replyContent", "repliedAt"]

DATA_DIR = Path("data/raw")
STATE_FILE = DATA_DIR / "_state.json"


# ---------------------------------------------------------------- storage --
def load_reviews(game: str) -> pd.DataFrame:
    path = DATA_DIR / f"{game}.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def save_reviews(game: str, existing: pd.DataFrame, new_rows: list) -> pd.DataFrame:
    """Merge new rows into existing data, de-duplicate, and write to disk."""
    if new_rows:
        new = pd.DataFrame(new_rows)[KEEP_COLUMNS]
        new["scraped_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
        new["reviewCreatedVersion"] = new["reviewCreatedVersion"].astype("string")
        combined = pd.concat([existing, new], ignore_index=True)
    else:
        combined = existing
    if combined.empty:
        return combined
    # keep="last": if a review was fetched again, keep the newest copy
    # (its thumbs-up count or developer reply may have changed).
    combined = (combined.drop_duplicates("reviewId", keep="last")
                        .sort_values("at", ascending=False)
                        .reset_index(drop=True))
    combined.to_parquet(DATA_DIR / f"{game}.parquet", index=False)
    return combined


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


# ---------------------------------------------------------------- network --
def fetch_page(package: str, token):
    """One request to Google Play, retried with increasing waits on failure."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return reviews(package, lang="en", country="us", sort=Sort.NEWEST,
                           count=PAGE_SIZE, continuation_token=token)
        except Exception as e:
            wait = PAUSE_SECONDS * 4 ** attempt   # 6 s, 24 s, 96 s
            print(f"    request failed ({e}); retry {attempt}/{MAX_RETRIES} in {wait:.0f}s")
            time.sleep(wait)
    raise RuntimeError("Google Play did not respond after several retries")


# ---------------------------------------------------------------- collect --
def collect_game(game: str, package: str, state: dict) -> None:
    existing = load_reviews(game)
    game_state = state.setdefault(game, {"backfill_done": False})
    cutoff = datetime.now() - timedelta(days=DAYS_BACK)

    if game_state["backfill_done"] and not existing.empty:
        # Incremental mode: stop once we reach reviews we already have.
        stop_at = existing["at"].max()
        mode = f"incremental (newer than {stop_at:%Y-%m-%d %H:%M})"
    else:
        # Backfill mode: walk back to the cutoff date.
        # If a previous backfill was interrupted, already-saved reviews are
        # simply de-duplicated on the way down.
        stop_at = cutoff
        mode = f"backfill (back to {cutoff:%Y-%m-%d})"
    print(f"\n{game}: {mode}; {len(existing)} reviews on disk")

    token, buffer, pages = None, [], 0
    while True:
        batch, token = fetch_page(package, token)
        if not batch:
            reached_end = True
            break
        buffer.extend(batch)
        pages += 1
        if batch[-1]["at"] <= stop_at:      # oldest review on this page is old enough
            reached_end = True
            break
        if pages % SAVE_EVERY == 0:         # checkpoint
            existing = save_reviews(game, existing, buffer)
            buffer = []
            print(f"  {pages} pages | oldest so far: {batch[-1]['at']:%Y-%m-%d} "
                  f"| {len(existing)} reviews saved")
        time.sleep(PAUSE_SECONDS)

    # Drop reviews older than the 12-month window, then save.
    buffer = [r for r in buffer if r["at"] >= cutoff]
    existing = save_reviews(game, existing, buffer)
    existing = existing[existing["at"] >= cutoff]
    existing.to_parquet(DATA_DIR / f"{game}.parquet", index=False)

    game_state["backfill_done"] = game_state["backfill_done"] or reached_end
    game_state["last_run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    game_state["reviews"] = len(existing)
    if not existing.empty:
        game_state["oldest"] = existing["at"].min().isoformat()
        game_state["newest"] = existing["at"].max().isoformat()
    save_state(state)
    print(f"  done: {len(existing)} reviews, {pages} pages requested")


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    selected = sys.argv[1:] or list(GAMES)
    state = load_state()
    for game in selected:
        try:
            collect_game(game, GAMES[game], state)
        except Exception as e:  # one game failing must not stop the others
            print(f"  {game} FAILED: {e}")
    print("\nState:", json.dumps(load_state(), indent=2))
