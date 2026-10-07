"""
Draw a stratified random sample of trope matches for manual precision review.

Lexicon methods are only as good as their measured precision. This script
produces a reviewable sample; judgments are recorded in validation_labels.csv
and precision is computed by report.py. Nothing in the pipeline assumes
precision -- it is measured and published alongside the rates.

Run: python3 validate.py <prefix>_matches.csv <n_per_stratum> > sample.txt
"""
import csv, random, sys
from collections import defaultdict

def main(path, n=6, seed=20260101):
    random.seed(seed)
    strata = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            strata[(r["family"], r["trope"])].append(r)
    out = []
    for key in sorted(strata):
        rows = strata[key]
        pick = random.sample(rows, min(n, len(rows)))
        for r in pick:
            out.append(r)
    w = csv.DictWriter(sys.stdout, fieldnames=["family","trope","stance","year","section","url","matched_text","window"], extrasaction="ignore")
    w.writeheader()
    for r in out:
        w.writerow(r)
    print(f"\n# sampled {len(out)} matches across {len(strata)} strata", file=sys.stderr)

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 6)
