import json, urllib.parse, urllib.request, gzip, io, time

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
BASE = "https://www.columbiaspectator.com/pf/api/v3/content/fetch/"

def fetch(source, query, tries=4):
    q = urllib.parse.quote(json.dumps(query))
    url = f"{BASE}{source}?query={q}&d=252&mxId=00000000&_website=spectator"
    last = None
    for i in range(tries):
        try:
            rq = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip", "Accept": "application/json"})
            with urllib.request.urlopen(rq, timeout=45) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return json.loads(raw.decode("utf-8", "replace"))
        except Exception as e:
            last = e; time.sleep(1.5 * (i + 1))
    raise last

if __name__ == "__main__":
    import sys
    for frm in [0, 1000, 3000, 6000, 9000, 9900, 10000, 12000]:
        try:
            d = fetch("site-service", {"section": "news", "numArticles": "1", "from": str(frm)})
            ce = d.get("content_elements") or []
            if not ce:
                print(f"from={frm}: EMPTY"); continue
            a = ce[0]
            print(f"from={frm}: {a.get('display_date','?')[:10]}  {a.get('canonical_url','')[:60]}")
        except Exception as e:
            print(f"from={frm}: ERROR {type(e).__name__} {str(e)[:80]}")
