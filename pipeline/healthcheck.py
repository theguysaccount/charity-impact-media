#!/usr/bin/env python3
"""Check the live site the way a visitor and a crawler would. Exits 1 on any failure.

  python3 pipeline/healthcheck.py https://<user>.github.io/<repo> [--min-charities 20000]

Checks: home page, sitemap, robots.txt, the IndexNow key file, the search index, and five
random charity pages (status, canonical URL, the source list, the correction link and the
data file behind compare/embed). Source links to ProPublica are sampled as warnings only.
"""

import argparse
import json
import os
import random
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "charity-impact-media-healthcheck (+https://github.com/theguysaccount/charity-impact-media)"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read().decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--min-charities", type=int, default=20000)
    ap.add_argument("--sample", type=int, default=5)
    a = ap.parse_args()
    base = a.base.rstrip("/")
    fails, warns = [], []

    def check(label, cond, detail=""):
        print(f"{'ok  ' if cond else 'FAIL'} {label}{(': ' + detail) if detail and not cond else ''}")
        if not cond:
            fails.append(label)

    try:
        st, home = get(base + "/")
        check("home page", st == 200 and "Where does the money go?" in home)
    except Exception as e:  # noqa: BLE001
        check("home page", False, str(e))
    charity_urls = []
    try:
        st, sm = get(base + "/sitemap.xml")
        locs = re.findall(r"<loc>([^<]+)</loc>", sm)
        charity_urls = [u for u in locs if "/charity/" in u]
        check("sitemap", st == 200 and len(charity_urls) >= a.min_charities, f"{len(charity_urls)} charity URLs")
    except Exception as e:  # noqa: BLE001
        check("sitemap", False, str(e))
    try:
        st, rb = get(base + "/robots.txt")
        check("robots.txt", st == 200 and "Sitemap:" in rb)
    except Exception as e:  # noqa: BLE001
        check("robots.txt", False, str(e))
    try:
        key = open(os.path.join(ROOT, "site", "indexnow-key.txt")).read().strip()
        st, body = get(f"{base}/{key}.txt")
        check("IndexNow key file", st == 200 and body.strip() == key)
    except Exception as e:  # noqa: BLE001
        check("IndexNow key file", False, str(e))
    try:
        st, body = get(base + "/assets/search.json")
        check("search index", st == 200 and len(json.loads(body)) >= a.min_charities)
    except Exception as e:  # noqa: BLE001
        check("search index", False, str(e))
    for u in random.sample(charity_urls, min(a.sample, len(charity_urls))):
        try:
            st, s = get(u)
            ok = (st == 200 and f'<link rel="canonical" href="{u}">' in s and 'id="reply"' in s
                  and "template=correction.yml" in s and re.search(r'<li id="f\d{4,6}">', s) is not None)
            check(f"charity page {u}", ok)
            st2, dj = get(u + "data.json")
            check(f"data.json {u}", st2 == 200 and json.loads(dj)["e"] in u)
            m = re.search(r'href="(https://projects\.propublica\.org/nonprofits/organizations/\d+/\d+/full)"', s)
            if m:
                try:
                    st3, _ = get(m.group(1))
                    if st3 != 200:
                        warns.append(f"source link {m.group(1)} answered {st3}")
                except Exception as e:  # noqa: BLE001
                    warns.append(f"source link {m.group(1)}: {e}")
        except Exception as e:  # noqa: BLE001
            check(f"charity page {u}", False, str(e))
    for w in warns:
        print(f"warn {w}")
    print(f"{len(fails)} failures, {len(warns)} warnings")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"### Live site check\n\n{len(fails)} failures, {len(warns)} warnings\n\n"
                    + "".join(f"- FAIL {x}\n" for x in fails) + "".join(f"- warn {x}\n" for x in warns))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
