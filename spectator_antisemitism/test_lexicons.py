"""
Regression tests for the trope lexicons.

Every FALSE_POSITIVES entry is a real passage from the Columbia Spectator corpus
that an earlier version of the lexicon wrongly flagged. Every TRUE_POSITIVES
entry is a real passage (or a minimal paraphrase) that must keep matching.

Run: python3 test_lexicons.py
"""
import sys
import lexicons as L

# Real corpus passages that must NOT flag as classic antisemitism.
FALSE_POSITIVES = [
    ("endowed chair",        "the Henry and Gertrude Rothschild professor of computer science"),
    ("trustee policy",       "trustees owe a duty of undivided loyalty to the University"),
    ("election ads",         "both Harris and Trump are running media campaigns"),
    ("marathon running",     "most people in the running world were reminded of Bannister"),
    ("staff thank-you",      "Deps run the world, and you are the best of the best"),
    ("congress descriptor",  "a right-wing-controlled congress throughout their terms"),
    ("bank underwriting",    "Santander Bank underwrote debt while controlling the governmental agency"),
    ("ivy media poll",       "the Ivy League has recorded its own media polling points since 2004"),
    # state-as-subject: ordinary politics, not a conspiracy claim
    ("war dominates campus", "the war in Gaza have dominated the politics of Columbia"),
    ("crowd control agent",  "a chemical developed in Israel and used for crowd control in the West Bank"),
    ("israelis criticise",   "Israelis are often the first to criticize their own government"),
    # intra-Jewish political critique, not a hidden-power claim
    ("anti-zionist critique","spaces that prioritize Jewish supremacy and ethnonationalism"),
]

# Passages that MUST flag (the trope is genuinely present, whoever is speaking).
TRUE_POSITIVES = [
    ("control media",     "Jews control the media and the banks"),
    ("passive control",   "the media is controlled by Zionists"),
    ("cabal",             "a Jewish cabal running Hollywood"),
    ("run the world",     "repeating tropes about Jews running the world"),
    ("zionist control",   "conspiracy theories about Zionist control of global politics"),
    ("hidden power",      "the idea of a Jewish conspiracy in which the Jews possess hidden power"),
    ("us policy",         "claiming that Jews or Zionists control U.S. policy"),
    ("rothschild plot",   "the Rothschilds secretly control the world banking system"),
    ("holocaust hoax",    "they said the Holocaust was a hoax"),
    ("swastika",          "a swastika was drawn on the door"),
    ("dual loyalty",      "critics accused him of dual loyalty to Israel"),
]

STANCE_CASES = [
    ("hate-incident report", "A swastika was found in the Jewish student center and the dean condemned it.", "condemned"),
    ("quoted trope",         "The flyer declared that Jews control the media, according to students who found it.", "reported"),
    ("bare assertion",       "Jews control the media and run the banks, and that is simply a fact.", "unattributed"),
]


def narrow_hits(t):
    return [k for k, r in L.RX_NARROW.items() if r.search(t)]


def main():
    fails = []
    for name, t in FALSE_POSITIVES:
        hits = narrow_hits(t)
        if hits:
            fails.append(f"FALSE POSITIVE [{name}] matched {hits}: {t[:70]}")
    for name, t in TRUE_POSITIVES:
        if not narrow_hits(t):
            fails.append(f"MISSED [{name}]: {t[:70]}")

    import score
    for name, t, want in STANCE_CASES:
        _, m = score.score_article({"url": "/t", "date": "2024-01-01", "headline": "",
                                    "text": t, "section_q": "news", "subtype": ""})
        got = m[0]["stance"] if m else "none"
        if got != want:
            fails.append(f"STANCE [{name}]: want {want}, got {got}")

    n = len(FALSE_POSITIVES) + len(TRUE_POSITIVES) + len(STANCE_CASES)
    if fails:
        print(f"FAIL — {len(fails)}/{n} checks failed:")
        for f in fails:
            print("  " + f)
        return 1
    print(f"PASS — all {n} checks "
          f"({len(FALSE_POSITIVES)} false-positive guards, "
          f"{len(TRUE_POSITIVES)} true positives, {len(STANCE_CASES)} stance)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
