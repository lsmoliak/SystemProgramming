"""
Score Columbia Daily Spectator articles for Jewish/Israel-related content and
for antisemitic tropes, under two competing definitions, with stance separation.

Run:  python3 score.py <corpus.jsonl> <out_prefix>

Emits:
  <out_prefix>_articles.csv   one row per article
  <out_prefix>_matches.csv    one row per trope match (for validation/audit)
  <out_prefix>_yearly.csv     aggregated by year
"""

import csv, json, re, sys, statistics
from collections import defaultdict
import lexicons as L
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

VADER = SentimentIntensityAnalyzer()
WINDOW = 400          # chars either side of a trope match used for stance
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def sentences(text):
    return [s for s in SENT_SPLIT.split(text) if s.strip()]


def classify_stance(window):
    """
    Decide whether flagged language in `window` is the paper's own assertion,
    neutral reporting, or critical/condemnatory coverage.

    Ordering matters: condemnation dominates. An article that quotes a slur and
    calls it a hate incident is coverage OF antisemitism. Treating that as the
    paper being antisemitic is the single biggest failure mode of naive
    sentiment scoring, and it would invert the sign of the whole series.
    """
    condemn = bool(L.RX_CONDEMN.search(window))
    attrib = bool(L.RX_ATTRIB.search(window))
    if condemn:
        return "condemned"       # critical coverage of antisemitism
    if attrib:
        return "reported"        # quoted/attributed, paper not asserting
    return "unattributed"        # closest thing to the paper's own voice


def score_article(rec):
    text = (rec.get("headline", "") + ". " + rec.get("text", "")).strip()
    low = text

    jewish_n = len(L.RX_JEWISH.findall(low))
    israel_n = len(L.RX_ISRAEL.findall(low))
    antisem_n = len(L.RX_ANTISEM_TOPIC.findall(low))

    # "Jewish-relevant" = mentions Jewish life/identity OR antisemitism itself.
    rel_jewish = (jewish_n + antisem_n) > 0
    rel_israel = israel_n > 0

    matches = []
    for family, table in (("narrow", L.RX_NARROW), ("ihra_ext", L.RX_IHRA_EXT)):
        for trope, rx in table.items():
            for m in rx.finditer(low):
                a, b = max(0, m.start() - WINDOW), min(len(low), m.end() + WINDOW)
                win = low[a:b]
                # ANCHOR GATE: a trope only counts if the surrounding window
                # actually mentions Jews or Israel. Defense in depth behind the
                # subject gate in lexicons.py -- catches cases where a generic
                # phrase slips through in text that has nothing to do with the
                # topic (sports copy, election ads, debt reporting).
                if not (L.RX_JEWISH.search(win) or L.RX_ISRAEL.search(win)
                        or L.RX_ANTISEM_TOPIC.search(win)):
                    continue
                matches.append({
                    "url": rec["url"], "date": rec["date"], "year": rec["date"][:4],
                    "section": rec.get("section_q", ""), "subtype": rec.get("subtype", ""),
                    "family": family, "trope": trope,
                    "matched_text": m.group(0)[:120],
                    "stance": classify_stance(win),
                    "window": win.replace("\n", " ")[:900],
                })

    # Contextual sentiment: VADER over sentences that mention a Jewish anchor.
    jew_sents = [s for s in sentences(text) if L.RX_JEWISH.search(s) or L.RX_ANTISEM_TOPIC.search(s)]
    isr_sents = [s for s in sentences(text) if L.RX_ISRAEL.search(s)]
    jew_sent = statistics.fmean([VADER.polarity_scores(s)["compound"] for s in jew_sents]) if jew_sents else None
    isr_sent = statistics.fmean([VADER.polarity_scores(s)["compound"] for s in isr_sents]) if isr_sents else None

    def agg(family, stances):
        return sum(1 for m in matches if m["family"] == family and m["stance"] in stances)

    row = {
        "url": rec["url"], "date": rec["date"], "year": rec["date"][:4],
        "section": rec.get("section_q", ""), "subtype": rec.get("subtype", ""),
        "headline": rec.get("headline", "")[:200],
        "words": len(text.split()),
        "jewish_terms": jewish_n, "israel_terms": israel_n, "antisem_terms": antisem_n,
        "rel_jewish": int(rel_jewish), "rel_israel": int(rel_israel),
        "rel_any": int(rel_jewish or rel_israel),
        # NARROW (consensus definition)
        "narrow_any": agg("narrow", {"condemned", "reported", "unattributed"}),
        "narrow_unattributed": agg("narrow", {"unattributed"}),
        "narrow_condemned": agg("narrow", {"condemned"}),
        # IHRA extension (contested, Israel-related)
        "ihra_ext_any": agg("ihra_ext", {"condemned", "reported", "unattributed"}),
        "ihra_ext_unattributed": agg("ihra_ext", {"unattributed"}),
        "jewish_sentiment": jew_sent, "israel_sentiment": isr_sent,
        "n_jewish_sents": len(jew_sents), "n_israel_sents": len(isr_sents),
    }
    # IHRA-style total = narrow + extension
    row["ihra_total_any"] = row["narrow_any"] + row["ihra_ext_any"]
    row["ihra_total_unattributed"] = row["narrow_unattributed"] + row["ihra_ext_unattributed"]
    return row, matches


def main(corpus_path, prefix):
    arows, mrows, seen = [], [], set()
    for ln in open(corpus_path, encoding="utf-8"):
        try:
            rec = json.loads(ln)
        except Exception:
            continue
        if not rec.get("date") or rec["url"] in seen:
            continue
        seen.add(rec["url"])
        a, m = score_article(rec)
        arows.append(a); mrows.extend(m)

    with open(f"{prefix}_articles.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(arows[0].keys())); w.writeheader(); w.writerows(arows)
    with open(f"{prefix}_matches.csv", "w", newline="", encoding="utf-8") as f:
        fn = ["url","date","year","section","subtype","family","trope","matched_text","stance","window"]
        w = csv.DictWriter(f, fieldnames=fn); w.writeheader(); w.writerows(mrows)

    # ---- yearly aggregation -------------------------------------------------
    by = defaultdict(list)
    for a in arows:
        by[a["year"]].append(a)

    def rate(rows, num_key, den_rows):
        d = len(den_rows)
        return (sum(1 for r in den_rows if r[num_key] > 0) / d * 100) if d else None

    yrows = []
    for y in sorted(by):
        rs = by[y]
        jew = [r for r in rs if r["rel_jewish"]]
        anyrel = [r for r in rs if r["rel_any"]]
        js = [r["jewish_sentiment"] for r in rs if r["jewish_sentiment"] is not None]
        isr = [r["israel_sentiment"] for r in rs if r["israel_sentiment"] is not None]
        yrows.append({
            "year": y,
            "articles": len(rs),
            "jewish_rel_articles": len(jew),
            "jewish_rel_pct": round(len(jew) / len(rs) * 100, 2) if rs else None,
            "israel_rel_articles": sum(1 for r in rs if r["rel_israel"]),
            "israel_rel_pct": round(sum(1 for r in rs if r["rel_israel"]) / len(rs) * 100, 2) if rs else None,
            "antisem_topic_articles": sum(1 for r in rs if r["antisem_terms"] > 0),
            "antisem_topic_pct": round(sum(1 for r in rs if r["antisem_terms"] > 0) / len(rs) * 100, 2) if rs else None,
            # per-100 relevant articles, so volume changes don't drive the trend
            "narrow_flag_per100rel": round(rate(rs, "narrow_any", anyrel), 2) if anyrel else None,
            "narrow_unattr_per100rel": round(rate(rs, "narrow_unattributed", anyrel), 2) if anyrel else None,
            "ihra_flag_per100rel": round(rate(rs, "ihra_total_any", anyrel), 2) if anyrel else None,
            "ihra_unattr_per100rel": round(rate(rs, "ihra_total_unattributed", anyrel), 2) if anyrel else None,
            "narrow_flagged_articles": sum(1 for r in rs if r["narrow_any"] > 0),
            "narrow_unattr_articles": sum(1 for r in rs if r["narrow_unattributed"] > 0),
            "ihra_flagged_articles": sum(1 for r in rs if r["ihra_total_any"] > 0),
            "mean_jewish_sentiment": round(statistics.fmean(js), 4) if js else None,
            "mean_israel_sentiment": round(statistics.fmean(isr), 4) if isr else None,
        })

    with open(f"{prefix}_yearly.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(yrows[0].keys())); w.writeheader(); w.writerows(yrows)

    print(f"scored {len(arows)} articles, {len(mrows)} trope matches, {len(yrows)} years")
    return arows, mrows, yrows


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "out")
