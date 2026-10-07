# Columbia Daily Spectator — Jewish/Israel coverage and antisemitism measurement

Measures how much the *Columbia Daily Spectator* covered Jewish- and
Israel-related topics year over year, and tests whether antisemitism in that
coverage rose — under **two rival definitions that disagree**, with reporting
separated from assertion.

## Read this first: the period is not the one requested

The request was **1950 onward**. That is not what this measures.

| Source | Span | Status |
|---|---|---|
| Columbia's historical *Spectator* archive | 1877–2016 | **Unavailable.** Cloudflare bot challenge, HTTP 403 on every request. |
| Wayback Machine mirror of that archive | — | **Unusable.** 14 text-mode captures domain-wide; the rest are viewer shells whose OCR loads by JS. |
| `columbiaspectator.com` Arc Publishing API | ~2013–2026 | **Fully available**, full body text. |

The Arc content index caps near 9,900 items per section, which is what pins the
earliest reachable year to roughly 2013. Coverage is dense only from 2017.
**No pre-2013 result is reported, because no pre-2013 text was obtainable.**

To extend the series back to 1950 you need archive access this analysis did not
have — Columbia Libraries credentials, a ProQuest Historical Newspapers export,
or a bulk OCR dump. The pipeline will ingest it unchanged: `score.py` reads any
JSONL with `url`, `date`, `headline`, `text` fields.

## The headline result

Coverage of these topics exploded. Classic antisemitic tropes did not.

- Articles discussing antisemitism rose from **0.5% (2022) to 21.7% (2025)**.
- **Narrow-definition** flags stayed in the low single digits every year.
- **IHRA-extended** flags peaked at 62 articles in 2024 — roughly 7× the narrow count.

Nearly the entire apparent "rise in antisemitism" under an IHRA-style measure is
Israel-related political speech, not classic antisemitism.

And the validation result matters more than either number: **all 62
narrow-definition matches were reviewed by hand, and not one is the *Spectator*
asserting antisemitism.** They are swastika-vandalism reports, the "Yid" slur
sprayed on a Holocaust-studies professor's door, and op-eds naming the "Jews run
the world" trope *in order to condemn it*. The narrow series measures how much
antisemitism the paper was **reporting on and arguing against**.

## Why two measures

There is no consensus operational definition of antisemitism:

- The **IHRA Working Definition** includes Israel-related examples (denying
  Jewish self-determination, double standards, Nazi comparisons).
- The **Jerusalem Declaration (JDA)** explicitly *excludes* criticism of Israel
  and Zionism, including BDS support.

Scoring one and calling it "the" antisemitism level hides a political choice
inside a number. Both are computed and reported side by side, so the
definitional dependency is a visible finding rather than a buried assumption.

## Two precision gates (and why they exist)

An earlier lexicon matched bare phrases like "control the media" and "run the
world." Manual review of **all 13** of its own-voice hits found **13 false
positives and zero true positives** — an endowed "Rothschild professor" chair,
"undivided loyalty" boilerplate from a trustee conflict-of-interest policy,
"running media campaigns" about election ads, the marathon "running world," and
"Deps run the world" from a staff acknowledgments column. Precision: 0%.

Two gates now apply:

1. **Subject gate** — conspiracy and dual-loyalty patterns require an explicit
   Jewish/Zionist subject in the same sentence as the predicate. Conspiracy
   tropes take a *people* subject, never a state: "Israel dominated the politics
   of Columbia" and "a chemical developed in Israel used for crowd control" are
   ordinary politics, not conspiracy claims.
2. **Anchor gate** — a match is discarded unless a Jewish or Israel anchor term
   appears in the surrounding ±400-character window.

`test_lexicons.py` pins all of this: 12 false-positive guards drawn from real
corpus passages, 11 true positives, 3 stance cases. All 26 pass.

## Stance: reporting on it vs. saying it

A paper covering a swastika in a dormitory contains the word "swastika" and much
negative language about Jews. It is not thereby antisemitic. Naive sentiment
analysis inverts this. Every match is classified from its window as
**condemned** / **reported** / **unattributed**, and condemnation dominates.

## Files

| File | Purpose |
|---|---|
| `arc.py` | Arc Publishing API client (retrying) |
| `crawl.py` | Section crawler → `corpus.jsonl` (resumable) |
| `lexicons.py` | Anchors, trope families, stance cues, precision gates |
| `score.py` | Per-article scoring, stance, sentiment → CSVs |
| `validate.py` | Stratified sampler for manual review |
| `test_lexicons.py` | Regression suite (26 checks) |
| `report.py` + `report_template.html` | Builds `report.html` |
| `final_yearly.csv` | Year-level results |
| `final_matches.csv` | Every flagged passage with window + stance (auditable) |
| `final_articles.csv` | Per-article scores |
| `validation_labels.csv` | Hand labels: 62 narrow census + 18 IHRA sample |

`corpus.jsonl` (65 MB) is gitignored; regenerate with `python3 crawl.py`.

## Reproduce

```bash
pip install vaderSentiment
python3 crawl.py                      # ~12k articles, resumable
python3 test_lexicons.py              # must print PASS
python3 score.py corpus.jsonl final   # ~3 min
python3 report.py final report.html
```

## Limitations

- **1950–2012 is absent entirely**; 2013–2016 is too thin to rate and is excluded
  from all rates (shown as `*` in the report table).
- **Lexicons detect topics, not intent.** Precision is measured, not assumed.
- **Stance cues are shallow.** "Denounced" fires whoever is denouncing, so
  protesters denouncing Israel can read as the paper condemning antisemitism.
  This inflates `condemned` in the IHRA-extended family.
- **Sentiment is not antisemitism.** VADER measures valence; war coverage is
  negative regardless of animus. Kept separate from flag counts, never summed.
- **Section mix shifts year to year**, so the denominator is not a constant
  sample. Rates per 100 topic-relevant articles accompany raw counts.
- **The IHRA-extended series is a definitional artifact as much as an empirical
  one.** It rises when Israel-related political speech rises; whether that is
  antisemitism is the contested question this quantifies rather than settles.

No single "antisemitism score" for a newspaper should be trusted — including any
produced by this pipeline.
