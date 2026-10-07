"""
Build the HTML report (publishable as an Artifact) from scored CSVs.

Run: python3 report.py <prefix> <out.html>
Reads <prefix>_yearly.csv, <prefix>_matches.csv, <prefix>_articles.csv
plus validation_labels.csv if present.
"""
import csv, json, sys, collections, statistics, html


def read(p):
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(v):
    if v in ("", None):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def build(prefix, out):
    yearly = read(f"{prefix}_yearly.csv")
    matches = read(f"{prefix}_matches.csv")
    arts = read(f"{prefix}_articles.csv")

    # Years with a usable denominator. Below this the Arc index is too sparse
    # for a rate to mean anything -- 1-30 articles for a whole year.
    MIN_ARTICLES = 200
    full = [y for y in yearly if int(y["articles"]) >= MIN_ARTICLES]
    thin = [y for y in yearly if int(y["articles"]) < MIN_ARTICLES]

    try:
        labels = read("validation_labels.csv")
    except FileNotFoundError:
        labels = []

    # Two-axis validation. Axis A: is the flagged language genuinely present and
    # on-topic (lexicon precision)? Axis B: is the author ASSERTING the claim,
    # versus quoting it, naming it to condemn it, or reporting an incident
    # (construct precision)? A lexicon can score 100% on A and still say nothing
    # about whether the paper was antisemitic -- which is the headline result.
    prec = {}
    if labels:
        byfam = collections.defaultdict(list)
        for r in labels:
            byfam[r["family"]].append(r)
        for fam, rs in byfam.items():
            tp = sum(1 for r in rs if r["verdict"].strip().lower() == "tp")
            ov = sum(1 for r in rs if r["own_voice"].strip().lower() == "yes")
            prec[fam] = {
                "n": len(rs), "tp": tp,
                "pct": round(tp / len(rs) * 100, 1) if rs else None,
                "own_voice": ov,
                "own_pct": round(ov / len(rs) * 100, 1) if rs else None,
                "basis": "census (all matches)" if fam == "narrow" else "random sample",
            }
    notes = [r for r in labels if r.get("note") and r["own_voice"].strip().lower() == "yes"]

    trope_counts = collections.Counter((m["family"], m["trope"]) for m in matches)
    stance_by_fam = collections.defaultdict(collections.Counter)
    for m in matches:
        stance_by_fam[m["family"]][m["stance"]] += 1

    # stance composition per year, narrow family only
    stance_year = collections.defaultdict(collections.Counter)
    for m in matches:
        if m["family"] == "narrow":
            stance_year[m["year"]][m["stance"]] += 1

    data = {
        "years": [y["year"] for y in full],
        "salience": {
            "jewish": [num(y["jewish_rel_pct"]) for y in full],
            "israel": [num(y["israel_rel_pct"]) for y in full],
            "antisem": [num(y["antisem_topic_pct"]) for y in full],
        },
        "counts": {
            "narrow": [int(y["narrow_flagged_articles"]) for y in full],
            "ihra": [int(y["ihra_flagged_articles"]) for y in full],
            "articles": [int(y["articles"]) for y in full],
        },
        "rates": {
            "narrow": [num(y["narrow_flag_per100rel"]) for y in full],
            "ihra": [num(y["ihra_flag_per100rel"]) for y in full],
        },
        "sentiment": {
            "jewish": [num(y["mean_jewish_sentiment"]) for y in full],
            "israel": [num(y["mean_israel_sentiment"]) for y in full],
        },
        "stance_year": {y: dict(stance_year.get(y, {})) for y in [f["year"] for f in full]},
        "tropes": [{"family": k[0], "trope": k[1], "n": v} for k, v in trope_counts.most_common()],
        "stance_by_fam": {k: dict(v) for k, v in stance_by_fam.items()},
        "precision": prec,
        "own_voice_examples": [{"year": r["year"], "trope": r["trope"], "note": r["note"]} for r in notes],
        "thin_years": [{"year": y["year"], "articles": int(y["articles"])} for y in thin],
        "totals": {
            "articles": len(arts),
            "matches": len(matches),
            "min_year": full[0]["year"] if full else None,
            "max_year": full[-1]["year"] if full else None,
        },
    }

    tmpl = open("report_template.html", encoding="utf-8").read()
    htmlout = tmpl.replace("/*__DATA__*/null", json.dumps(data, indent=1))
    open(out, "w", encoding="utf-8").write(htmlout)
    print(f"wrote {out} ({len(htmlout)} bytes); years {data['totals']['min_year']}-{data['totals']['max_year']}")
    return data


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
