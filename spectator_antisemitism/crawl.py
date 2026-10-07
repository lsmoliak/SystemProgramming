import json, re, html, os, sys, time
from arc import fetch

SECTIONS = ["news","opinion","sports","arts-and-entertainment","the-eye","spectrum","city-news","multimedia"]
OUT = "corpus.jsonl"
seen = set()
if os.path.exists(OUT):
    for ln in open(OUT, encoding="utf-8"):
        try: seen.add(json.loads(ln)["url"])
        except Exception: pass
print(f"resume: {len(seen)} already stored", flush=True)

def strip(s):
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

def body(a):
    parts = []
    for e in (a.get("content_elements") or []):
        t = e.get("type")
        if t in ("text", "header", "blockquote"):
            parts.append(strip(e.get("content", "")))
        elif t == "list":
            for it in (e.get("items") or []):
                parts.append(strip(it.get("content", "") if isinstance(it, dict) else str(it)))
    return " ".join(p for p in parts if p)

f = open(OUT, "a", encoding="utf-8")
total_new = 0
for sec in SECTIONS:
    empties = 0
    for frm in range(0, 9900, 100):
        try:
            d = fetch("site-service", {"section": sec, "numArticles": "100", "from": str(frm)})
        except Exception as e:
            print(f"  {sec} from={frm} ERROR {str(e)[:70]}", flush=True); continue
        ce = d.get("content_elements") or []
        if not ce:
            empties += 1
            if empties >= 2: print(f"  {sec}: exhausted at from={frm}", flush=True); break
            continue
        empties = 0
        n_new = 0
        for a in ce:
            u = a.get("canonical_url") or a.get("_id")
            if not u or u in seen: continue
            seen.add(u)
            tx = body(a)
            if len(tx) < 60: continue
            tax = a.get("taxonomy") or {}
            ps = (tax.get("primary_section") or {})
            rec = {
                "url": u,
                "date": (a.get("display_date") or a.get("publish_date") or a.get("created_date") or "")[:10],
                "headline": strip((a.get("headlines") or {}).get("basic", "")),
                "section_q": sec,
                "section": ps.get("name") or ps.get("_id") or "",
                "subtype": a.get("subtype") or "",
                "authors": [c.get("name","") for c in ((a.get("credits") or {}).get("by") or []) if isinstance(c, dict)],
                "text": tx,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n"); n_new += 1; total_new += 1
        f.flush()
        if frm % 1000 == 0:
            print(f"  {sec} from={frm} new={n_new} total_new={total_new}", flush=True)
f.close()
print(f"DONE total_new={total_new} corpus={len(seen)}", flush=True)
