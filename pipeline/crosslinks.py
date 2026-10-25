#!/usr/bin/env python3
"""Cross-links to WHOFUNDS (which private foundations fund an organization).

  python3 pipeline/crosslinks.py        # -> data/work/whofunds.json

Reads the latest public WHOFUNDS data release (organizations CSV) and the WHOFUNDS
sitemap, and keeps covered charities that private foundations reported grants to.
Read-only and fail-safe: on any error it keeps the previous whofunds.json and exits 0.
"""

import csv
import gzip
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import WORK, http, read_json, write_json  # noqa: E402

REPO = "theguysaccount/whofunds-open-grant-graph"
SITE = "https://theguysaccount.github.io/whofunds-open-grant-graph"


def get(url, headers=None):
    with http(url, headers=headers, timeout=180) as r:
        return r.read()


def main():
    cov = read_json(os.path.join(WORK, "coverage.json.gz"))
    out_path = os.path.join(WORK, "whofunds.json")
    try:
        hdr = {"Accept": "application/vnd.github+json"}
        if os.environ.get("GH_TOKEN"):
            hdr["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
        rel = json.loads(get(f"https://api.github.com/repos/{REPO}/releases/latest", hdr))
        asset = next(a for a in rel["assets"] if re.match(r"whofunds_ty\d{4}_organizations\.csv\.gz$", a["name"]))
        year = int(re.search(r"ty(\d{4})", asset["name"]).group(1))
        raw = gzip.decompress(get(asset["browser_download_url"]))
        static = set()
        idx = get(f"{SITE}/sitemap.xml").decode()
        for loc in re.findall(r"<loc>([^<]+)</loc>", idx):
            body = get(loc)
            if body[:2] == b"\x1f\x8b":
                body = gzip.decompress(body)
            static.update(re.findall(r"/org/(\d{9})/</loc>", body.decode()))
        out = {}
        for r in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
            ein = r["ein"]
            if ein in cov and int(r["n_funders"] or 0) >= 1:
                url = f"{SITE}/org/{ein}/" if ein in static else f"{SITE}/org/?ein={ein}"
                out[ein] = {"n": int(r["n_funders"]), "total": int(float(r["received_total"] or 0)), "year": year, "url": url}
        write_json(out_path, out)
        print(f"WHOFUNDS cross-links: {len(out)} covered charities have foundation funders (TY{year})", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"WHOFUNDS cross-links skipped ({e}); keeping the previous file if any", file=sys.stderr)


if __name__ == "__main__":
    main()
