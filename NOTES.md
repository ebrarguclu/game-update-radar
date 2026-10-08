# Project notes

Working notes: decisions, the reasoning behind them, and concepts learned.
Update this file whenever a decision is made.

## Research question

**Main question:** Which types of updates push players to quit, and can we detect it in the first days after release?

**Layers** (each one is a complete result on its own):
1. **Core:** How does player sentiment change after updates, and on which topics (difficulty, ads, prices, bugs...)?
2. **Churn signal:** ~~Are reviews without an app version from players who uninstalled?~~ Not supported (see below). Now: after which updates does the share of reviews *stating* they quit rise?
3. **Early warning:** Can the first 3 days after a release predict how it looks after 30 days?

**Product vision:** A pipeline that produces a report for every new release.
- Before a release: how did competitors' similar updates land? (competitive intelligence)
- After a release: how is our update being received? (post-release monitoring)

## Why the project turned toward churn

In the feasibility check (`01_check_data.py`), Royal Match reviews **without** an app version averaged
**2.94 stars** (n=376, SE 0.10) vs **4.13** for reviews **with** one (n=2,624, SE 0.03).
The 95% intervals do not overlap, so the gap is real.
Hypothesis: Google Play records the installed version when a review is written, so players who
uninstalled before reviewing have no version. If true, this group is the voice of players who quit.
**Must be validated before use** (e.g., do these reviews mention "uninstalled", "deleted", "quit" more often?).

### Result of the test (2026-10-07, 12 months, 5 games): not supported
- Alternative explanation tested first: among reviews WITH a version, quit words appear in 8–17% of 1–2 star reviews but only 0.2–0.6% of 5-star reviews. So angrier reviews say "quit" more, regardless of version.
- Version-less reviews mention quitting 1–4 points more often (raw), but **at the same star rating the gap is −0.1 to +1.6 points (|z| ≤ 2)**.
- Conclusion: version-less reviews are more negative, but there is no evidence they come from players who quit. Layer 2 now tracks *stated* quitting intent directly.
- Caveat: the keyword list is a crude measure; a real but small effect could be hidden. Pixel Flow and Match Factory are borderline (z ≈ 2).
- Lesson: the raw comparison alone would have put a false finding at the center of the project. Always test the alternative explanation.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Games | Royal Match, Royal Kingdom (Dream Games), Toon Blast, Match Factory (Peak), Pixel Flow (Loom Games), Match Villains (Good Job Games) | Globally popular puzzle games from Turkish studios; Pixel Flow adds a newer, fast-growing game |
| Language / store | English reviews, US store | Largest volume. Limitation: non-English markets are not covered |
| History | 12 months | Royal Match ships ~25 versions/year (App Store version history), so 12 months gives 10+ updates per game. Older data represents the game less well |
| Missing versions | Keep as a separate group, never drop silently | They are much more negative than the rest (see above); dropping them would bias results upward |
| Version numbers | Always read as text | Read as numbers, "1.10" becomes 1.1 and silently merges with version "1.1" |
| Topic analysis | Keyword lists first, model later | A simple, transparent baseline first; move to a model only if the baseline is not good enough |
| Raw data | Never published | Privacy and platform terms; only aggregated results go into the repo |
| Significance | Benjamini–Hochberg, FDR 5% | 1,000+ tests at once; a fixed "z > 3" rule is arbitrary. BH guarantees at most 5% of flagged findings are false |
| Topic comparisons across games | Only reviews with 8+ words | Pixel Flow reviews are much longer (median 12 words vs 3–5); longer reviews mention more topics (confounding) |

## Feasibility check results (2026-10-07, last 25–58 days)

| Game | Reviews/day | % with version | Avg stars (our sample) | Store rating |
|---|---|---|---|---|
| Royal Match | 120 | 87.5 | 3.98 | 4.5 |
| Royal Kingdom | 75 | 84.2 | 4.43 | 4.7 |
| Toon Blast | 21 | 87.3 | 3.97 | 4.6 |
| Match Factory | 18 | 88.1 | 4.13 | 4.6 |
| Pixel Flow | 35 | 86.3 | 3.45 | 4.4 |

- Royal Match's `first_seen` for version 38911 (Sep 28) matches the App Store release date exactly, so `first_seen` is a valid release-date estimate for versions released inside the window.
- Reviews are short (8–14 words on average), so many will mention no topic.

## Known limitations

- Only players who write reviews are heard; they are more extreme than average.
- Only English-language reviews.
- Some content (levels, events) ships server-side without an app update, so it is invisible to version-based analysis.
- Results show association, not proof of cause: players who update early may differ from those who don't.

## Concepts learned

- **Virtual environment (venv):** an isolated Python per project. Packages go into the Python that runs the code. Share the recipe (`requirements.txt`), never the `.venv` folder.
- **Feasibility check:** before building, test whether the data can answer the question. Work backwards: question → assumptions → a number for each → decision rule set *before* looking.
- **Continuation token:** a bookmark for paginated APIs ("give me the next page").
- **Rate limiting:** servers block clients that send too many requests too fast; pause between requests.
- **Silent bugs:** code that runs without errors but produces wrong data (e.g., assuming reviews are sorted by date when they aren't). The most dangerous kind.
- **Censoring:** the edge of the data window cuts off true values (old versions' `first_seen` piles up at the window start).
- **Missing not at random:** missing values can belong to a specific group; dropping them biases results.
- **Standard error:** SE = std / √n. Roughly, mean ± 2·SE is a 95% interval.
- **Is a difference real?** Divide the difference by its SE, √(SE₁² + SE₂²). Above ~2, it is unlikely to be chance (this is the idea behind a t-test).
- **Confounding:** two explanations mixed together (store rating vs our sample: are reviewers more negative, or did the games get worse recently?).
- **Checkpointing and idempotency:** long network jobs will be interrupted; save progress, and make reruns safe (dedupe by ID).
- **Multiple comparisons:** run 500 tests where nothing is real and ~25 still pass a 5% test by chance. Adjust (Benjamini–Hochberg) when testing many things at once.
- **Robustness check / stratification:** compare groups at the same level of a confounder (e.g., same star rating). It doesn't assume the alternative explanation is true; it protects you in case it is.
- **Triangulation:** with no ground truth, look for several independent signals pointing the same way (stars, keywords, reading reviews).
- **Read the data behind the number:** before presenting a finding, read a sample of the raw reviews behind it.
- **Baseline first:** start with the simplest method that could work; it sets the bar a complex model must beat.
