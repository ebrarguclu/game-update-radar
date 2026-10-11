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

## Match Villains findings (2026-10-09)
- Release rhythm: every 14 days, almost always Monday (first-seen dates). Off-cycle builds (26 Dec, 26 Jan, 15 May) look like fixes.
- No consecutive-release rating change survives BH correction. Spring dip: 6969 (13 Apr) 3.22 stars, 7011 (4 May) +0.60 (q ≈ 0.07).
- Monthly English review volume: ~900–1,000 (Oct–Jan) → ~450–560 (Feb–May) → ~130–200 (Jun–Sep). Indexed: 100 → ~50 → ~14–21. Comparison games mostly flat; Match Factory −44%; Pixel Flow growing. So the drop is game-specific.
- Two sudden steps (Feb, Jun) rather than gradual decline → points to a discrete event.
- Test of "rating prompt removed": would lower the five-star share. Observed the opposite (~50% → 53–68%). Hypothesis rejected. Still open: fewer new players (loyal base remains), a prompt shown less often at happy moments, a market shift. Needs download data.
- Release notes (App Store) only describe content (100 levels, new item, event); no hint of the cause.
- Since June each build has <100 reviews → per-release analysis needs grouping.

## Verification by reading: the "ads" topic mixes three things (2026-10-10)
- Read and labeled 140 reviews matched by the "ads" keywords (RK 28796 before/after by me, RM 37281 and a random sample across games labeled with Claude's help; agreement on RK checked: 48/50).
- Only ~25% are complaints about ads *inside* the game. ~55% say the game doesn't match its marketing ads ("nothing like the ad"), ~12% praise having no ads.
- Royal Match: **zero** in-game ad complaints in 50 reviews. The README finding "RM 37281: ad mentions rose, maybe a server-side ad change" is therefore wrong; the rise is misleading-ad complaints. In-game ad complaints come mostly from Pixel Flow.
- RK 28796: both rose, but misleading-ad complaints are the larger share (48% → 64% of matches). Alternative explanation: new players always install the latest version, so a marketing campaign shows up as a "release" effect.
- Decision: split "ads" into `ads_ingame`, `ads_misleading`, `ads_none` (kept "ads" for comparison). Rules built on the RK+RM sheets, tested on the random 40: precision 86–100%, recall 60–100% (small sample).
- Lesson: precision of the old "ads" list for "complaint about in-game ads" was ~25%. A keyword is not a meaning. Different meanings go to different teams (monetization vs user acquisition).

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
- **Indexing:** scale each series to its own starting point (= 100) to compare trends of very different sizes.
- **The shape of a change is evidence:** sudden steps suggest a discrete event; gradual decline suggests slow attrition.
- **Test a hypothesis by its predicted signature:** decide what you'd see if it were true (e.g., five-star share falls), then check. Seeing the opposite rejects it.
- **Semantic versioning:** X.Y.Z. Y up = planned feature release; Z up = patch/fix. Android build codes and iOS versions differ, so match platforms by date.
- **Minimum detectable effect:** with n reviews, SE ≈ 1.5/√n; a difference needs ~2–3 SE to be detectable. Fewer reviews → only big changes are visible.
- **Excel + Turkish locale:** opening a comma CSV can silently turn 4.15 into "15 April" and 12.145 into 12145. Export real .xlsx from Python instead.
- **Precision vs recall:** precision = of what the rule flagged, how much is right; recall = of what is really there, how much the rule caught.
- **Gold set:** a small hand-labeled set used as the answer key to evaluate any method (keywords, LLM, model). Labeled once, re-checked occasionally (monitoring).
- **Build vs test set:** rules written while looking at some reviews look better on those same reviews; measure them on reviews not used to write them.
- **Reading a traceback:** start at the last line (what went wrong), go up to the last line in your own file (where), then ask which value could cause it.
- **Baseline first:** start with the simplest method that could work; it sets the bar a complex model must beat.
