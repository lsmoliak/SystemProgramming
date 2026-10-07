"""
Lexicons for measuring Jewish/Israel-related coverage in the Columbia Daily
Spectator, and for detecting antisemitic tropes under two competing definitions.

WHY TWO MEASURES, NOT ONE
-------------------------
There is no consensus operational definition of antisemitism, and the two most
widely used frameworks disagree in a way that matters enormously for a campus
newspaper corpus:

  * The IHRA Working Definition includes contemporary examples tied to Israel
    (denying Jewish self-determination, applying double standards, comparing
    Israeli policy to Nazism).
  * The Jerusalem Declaration on Antisemitism (JDA) explicitly EXCLUDES
    criticism of Israel and Zionism, including support for BDS.

Scoring one and calling it "the" antisemitism level hides a political choice
inside a number. So two families are defined:

  NARROW   - classic antisemitism aimed at Jews as Jews. Both frameworks agree.
  IHRA_EXT - the additional Israel-related examples IHRA counts and JDA does not.

An IHRA-style score is NARROW + IHRA_EXT. Reporting both makes the definitional
dependency a visible finding rather than a buried assumption.

PRECISION IS MEASURED, NOT ASSUMED
----------------------------------
A keyword match is evidence a topic was discussed, not proof of authorial
intent. Two safeguards, both added after manual review of real flagged output:

 1. SUBJECT GATE. Every "Jewish power" and "dual loyalty" pattern requires an
    explicit Jewish/Zionist subject next to the predicate. An earlier version
    matched bare "control the media" and "run the world"; manual review of its
    13 own-voice hits found 13 false positives -- an endowed "Rothschild
    professor" chair, "undivided loyalty" boilerplate in a trustee
    conflict-of-interest policy, "running media campaigns" about election ads,
    the marathon "running world", and "Deps run the world" in a staff
    acknowledgments column. Precision was 0%.
 2. ANCHOR GATE (enforced in score.py). A trope match is only counted when a
    Jewish or Israel anchor term also appears in the surrounding window.

Stance detection (below) then separates reporting ON antisemitism from
expressing it -- the failure mode that would otherwise invert the entire series.
"""

import re

def _rx(terms):
    """Compile an alternation of terms into one word-boundary regex."""
    return re.compile(r"(?<![\w-])(?:" + "|".join(terms) + r")(?![\w-])", re.I)

# --------------------------------------------------------------------------
# ANCHORS: what makes an article "about" Jewish / Israel-related topics.
# Kept separate so Jewish-community coverage can be measured independently
# from Israel/Palestine coverage -- they are not the same beat.
# --------------------------------------------------------------------------

JEWISH_ANCHOR = [
    r"jew", r"jews", r"jewish", r"jewry", r"judaism", r"judaic",
    r"rabbi", r"rabbis", r"rabbinical", r"synagogue", r"shul", r"yeshiva",
    r"hillel", r"chabad", r"kosher", r"shabbat", r"sabbath",
    r"torah", r"talmud", r"yiddish", r"bar\s+mitzvah", r"bat\s+mitzvah",
    r"hanukkah", r"chanukah", r"passover", r"seder", r"purim",
    r"yom\s+kippur", r"rosh\s+hashanah", r"sukkot",
    r"semite", r"semites", r"semitic", r"semitism",
    r"holocaust", r"shoah", r"kristallnacht",
]

ISRAEL_ANCHOR = [
    r"israel", r"israeli", r"israelis",
    r"zionism", r"zionist", r"zionists", r"anti-?zionist", r"anti-?zionism",
    r"idf", r"knesset", r"netanyahu", r"likud", r"mossad",
    r"gaza", r"west\s+bank", r"jerusalem", r"tel\s+aviv", r"golan",
    r"hamas", r"hezbollah", r"intifada", r"nakba",
    r"palestine", r"palestinian", r"palestinians",
    r"bds", r"boycott,?\s+divestment",
]

ANTISEMITISM_TOPIC = [
    r"anti-?semitism", r"anti-?semitic", r"anti-?semite", r"anti-?semites",
    r"jew-?hatred", r"anti-?jewish",
]

# --------------------------------------------------------------------------
# Subject patterns -- the precision gate described in the module docstring.
# `_NB` = "not a sentence boundary", so a subject and predicate must sit in
# the same sentence rather than merely near each other in the text.
# --------------------------------------------------------------------------

_SUBJ_BARE = r"(?:jews?|jewish|jewry|zionists?|zionism|israelis?|israel|rothschilds?)"
_SUBJ = r"\b" + _SUBJ_BARE + r"\b"

# Conspiracy/control tropes take a PEOPLE subject only. A state controlling
# things is ordinary politics, not a conspiracy claim -- including "Israel ...
# dominated the politics of Columbia", "a chemical developed in Israel and used
# for crowd control", and "Israelis are often the first to criticize their own
# government", all of which the state-inclusive subject list wrongly flagged.
_PSUBJ_BARE = r"(?:jews?|jewish|jewry|zionists?|zionism|rothschilds?)"
_PSUBJ = r"\b" + _PSUBJ_BARE + r"\b"
_NB = r"(?:(?!\.\s).){0,%d}?"   # bounded, sentence-internal gap

# --------------------------------------------------------------------------
# NARROW: classic antisemitic tropes. Consensus across frameworks.
# --------------------------------------------------------------------------

NARROW_TROPES = {
    "conspiracy_control": [
        _PSUBJ + (_NB % 60) + r"\b(?:control(?:s|led|ling)?|run(?:s|ning)?|own(?:s|ed|ing)?|dominat\w*|manipulat\w*)\b" + (_NB % 30) + r"\b(?:media|bank|banks|banking|press|money|finance|financial|government|economy|world|hollywood|congress|everything|politics|foreign\s+policy|u\.?s\.?\s+policy)\b",
        r"\b(?:media|banks?|banking|press|hollywood|congress|government|economy)\b" + (_NB % 40) + r"\b(?:controlled|run|owned|dominated)\s+by\s+(?:the\s+)?" + _PSUBJ_BARE,
        r"jewish\s+(?:conspiracy|cabal|plot|power\s+structure)",
        r"(?:zionist|jewish)\s+(?:cabal|puppet\s*master|new\s+world\s+order)",
        r"protocols\s+of\s+(?:the\s+)?(?:learned\s+)?elders",
        r"international\s+jewry",
        # Rothschild counts only in conspiratorial co-text, never as the endowed
        # professorship name it almost always is in this corpus.
        r"rothschilds?" + (_NB % 80) + r"\b(?:control|conspirac|cabal|puppet|new\s+world\s+order|secret|own\s+the)",
        r"\b(?:control|conspirac\w*|cabal|puppet|new\s+world\s+order)\b" + (_NB % 80) + r"rothschilds?",
        r"globalist\s+(?:elite|cabal|agenda)" + (_NB % 60) + _PSUBJ_BARE,
    ],
    "dual_loyalty": [
        # "undivided loyalty" is boilerplate in trustee policy, so require subject.
        r"\b(?:dual|divided|split|conflicting)\s+loyalt(?:y|ies)" + (_NB % 80) + _SUBJ_BARE,
        _SUBJ + (_NB % 80) + r"\b(?:dual|divided|split|conflicting)\s+loyalt(?:y|ies)",
        r"more\s+loyal\s+to\s+israel", r"loyal(?:ty)?\s+to\s+israel\s+than",
        r"fifth\s+column" + (_NB % 60) + _SUBJ_BARE,
        r"foreign\s+agents?\s+(?:for|of)\s+israel",
    ],
    "holocaust_denial": [
        r"holocaust\s+(?:was\s+a\s+)?(?:hoax|myth|lie|fabrication|exaggerat\w*)",
        r"holocaust\s+(?:never\s+happened|did\s+not\s+happen|didn'?t\s+happen)",
        r"den(?:y|ies|ied|ying)\s+(?:the\s+)?holocaust", r"holocaust\s+denial",
        r"six\s+million\s+(?:lie|myth|hoax)",
        r"gas\s+chambers?\s+(?:were\s+a\s+)?(?:hoax|myth|fake)",
    ],
    "dehumanization": [
        r"\bkikes?\b", r"\byids?\b", r"\bhebes?\b", r"\bshylock", r"christ-?killer",
        r"jews?\s+(?:are\s+)?(?:vermin|parasites?|rats?|subhuman|cockroaches|a\s+disease|filth)",
        r"\b(?:vermin|parasites?|cockroaches)\b" + (_NB % 40) + r"\bjews?\b",
        r"greedy\s+jew", r"\bjew(?:ing|ed)?\s+(?:him|her|them|me)\s+down\b",
        r"\bjew\s+down\b",
    ],
    "nazi_symbol": [
        r"swastikas?", r"sieg\s+heil", r"heil\s+hitler", r"hitler\s+was\s+right",
        r"gas\s+the\s+jews?", r"\b1488\b", r"blood\s+libel",
    ],
    "exclusion": [
        r"no\s+jews?\s+allowed", r"jew-?free",
        r"jews?\s+(?:should\s+)?(?:be\s+)?(?:banned|expelled|excluded)",
        r"ban\s+(?:the\s+)?jews?", r"expel\s+(?:the\s+)?jews?",
        r"jewish\s+quota", r"quota\s+on\s+jew",
        r"jews?\s+(?:are\s+)?not\s+welcome", r"keep\s+jews?\s+out",
    ],
    "collective_blame": [
        r"(?:all\s+)?jews?\s+(?:are\s+)?(?:responsible|to\s+blame|accountable)\s+for\s+(?:gaza|israel|the\s+occupation|zionism)",
        r"blame\s+(?:all\s+)?(?:the\s+)?jews?\s+for",
        r"every\s+jew\s+(?:is|supports)",
    ],
}

# --------------------------------------------------------------------------
# IHRA_EXT: Israel-related examples IHRA counts and JDA explicitly does not.
# CONTESTED BY CONSTRUCTION -- reported separately, never silently merged.
# --------------------------------------------------------------------------

IHRA_EXT_TROPES = {
    "deny_self_determination": [
        r"israel\s+(?:should\s+not|shouldn'?t|has\s+no\s+right\s+to)\s+exist",
        r"no\s+right\s+to\s+exist", r"dismantle\s+(?:the\s+state\s+of\s+)?israel",
        r"destroy(?:ing)?\s+(?:the\s+state\s+of\s+)?israel",
        r"israel\s+(?:is\s+)?an?\s+illegitimate\s+state",
        r"zionist\s+entity", r"from\s+the\s+river\s+to\s+the\s+sea",
    ],
    "zionism_is_racism": [
        r"zionism\s+(?:is|=)\s+(?:racism|racist|apartheid|colonialism|a\s+racist)",
        r"racist\s+ideology\s+of\s+zionism",
        r"zionism\s+is\s+(?:a\s+)?settler[\s-]colonial",
    ],
    "nazi_comparison": [
        r"israel\s+(?:is|acts)\s+(?:like|as)\s+(?:the\s+)?nazis?",
        r"zio-?nazi", r"israeli\s+nazis?", r"nazi\s+(?:state\s+of\s+)?israel",
        r"warsaw\s+ghetto" + (_NB % 40) + r"gaza", r"gaza" + (_NB % 40) + r"warsaw\s+ghetto",
    ],
    # The most contested of all. Many scholars, and the JDA, treat these as
    # ordinary political speech about state conduct. Broken out as their own
    # trope so a reader can subtract them.
    "apartheid_genocide_framing": [
        r"israeli?\s+apartheid", r"apartheid\s+(?:state|regime)" + (_NB % 30) + r"israel",
        r"apartheid\s+israel",
        r"israeli?\s+genocide", r"genocide\s+in\s+gaza", r"gaza\s+genocide",
        r"genocidal\s+(?:state|regime|israel)",
    ],
    "double_standard": [
        r"worst\s+human\s+rights\s+(?:abuser|violator)\s+in\s+the\s+world",
        r"israel\s+is\s+the\s+(?:most\s+evil|worst)\s+(?:country|state|nation)",
    ],
}

# --------------------------------------------------------------------------
# STANCE CUES
# --------------------------------------------------------------------------

ATTRIBUTION_CUES = [
    r"said", r"says", r"stated", r"told", r"wrote", r"according\s+to",
    r"alleged", r"allegedly", r"accus(?:ed|ing|ation)", r"claim(?:ed|s|ing)",
    r"report(?:ed|s|edly)", r"chant(?:ed|ing|s)", r"shouted", r"yelled",
    r"graffiti", r"sign\s+read", r"banner", r"placard", r"poster",
    r"tweet(?:ed)?", r"post(?:ed)?", r"email", r"flyer", r"leaflet",
    r"quoted", r"statement", r"spokesperson",
    r"scrawled", r"vandal\w*", r"defac(?:ed|ing)", r"spray-?painted",
]

CONDEMNATION_CUES = [
    r"condemn(?:ed|s|ing|ation)", r"denounc(?:ed|es|ing)", r"decri(?:ed|es)",
    r"anti-?semit\w*", r"hate\s+(?:crime|speech|incident)",
    r"bias\s+incident", r"discriminat(?:ion|ory)", r"bigot\w*", r"racis\w*",
    r"investigat(?:ion|ed|ing)", r"disciplin\w*", r"suspend(?:ed|sion)",
    r"apolog(?:y|ized|ised)", r"unacceptable", r"reprehensible", r"deplor\w*",
    r"backlash", r"outrage", r"offensive", r"harass(?:ment|ed)",
    r"task\s+force", r"no\s+place\s+(?:for|at)", r"zero\s+tolerance",
    r"civil\s+rights", r"title\s+vi", r"safety\s+concerns?",
    r"felt\s+unsafe", r"targeted", r"hostile\s+environment",
]

# --------------------------------------------------------------------------
# Compiled forms
# --------------------------------------------------------------------------

RX_JEWISH = _rx(JEWISH_ANCHOR)
RX_ISRAEL = _rx(ISRAEL_ANCHOR)
RX_ANTISEM_TOPIC = _rx(ANTISEMITISM_TOPIC)
RX_ATTRIB = _rx(ATTRIBUTION_CUES)
RX_CONDEMN = _rx(CONDEMNATION_CUES)

def _compile_tropes(d):
    return {k: re.compile("|".join(v), re.I) for k, v in d.items()}

RX_NARROW = _compile_tropes(NARROW_TROPES)
RX_IHRA_EXT = _compile_tropes(IHRA_EXT_TROPES)
