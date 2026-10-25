#!/usr/bin/env python3
"""Right-of-reply and correction issues, by EIN, for the charity pages.

  GH_TOKEN=... CIM_REPO=owner/repo python3 pipeline/replies.py     # -> data/work/replies.json

Lists issues labelled `right-of-reply` or `correction` (open and closed) and maps each to
the EIN in its title or form body. Pages link to the issues; they never copy their text.
Issues labelled `invalid` or `spam` are left out. Fail-safe: on error, keeps the old file.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import WORK, fmt_ein, http, write_json  # noqa: E402

LABELS = {"right-of-reply": "reply", "correction": "correction"}
SKIP = {"invalid", "spam", "duplicate"}


def ein_in(issue):
    for text in (issue.get("title") or "", issue.get("body") or ""):
        m = re.search(r"\b(\d{2})-?(\d{7})\b", text)
        if m:
            return fmt_ein(m.group(1) + m.group(2))
    return ""


def fetch(repo, label, token):
    out, page = [], 1
    while True:
        url = f"https://api.github.com/repos/{repo}/issues?labels={label}&state=all&per_page=100&page={page}"
        hdr = {"Accept": "application/vnd.github+json"}
        if token:
            hdr["Authorization"] = "Bearer " + token
        with http(url, headers=hdr) as r:
            batch = json.loads(r.read())
        out += [i for i in batch if "pull_request" not in i]
        if len(batch) < 100:
            return out
        page += 1


def main():
    repo = os.environ.get("CIM_REPO") or os.environ.get("GITHUB_REPOSITORY") or "theguysaccount/charity-impact-media"
    token = os.environ.get("GH_TOKEN", "")
    path = os.path.join(WORK, "replies.json")
    try:
        by = {}
        for label, kind in LABELS.items():
            for i in fetch(repo, label, token):
                labels = {lb["name"] for lb in i.get("labels", [])}
                ein = ein_in(i)
                if not ein or labels & SKIP:
                    continue
                by.setdefault(ein, []).append({"n": i["number"], "state": i["state"], "url": i["html_url"], "kind": kind})
        for v in by.values():
            v.sort(key=lambda r: -r["n"])
        write_json(path, by)
        print(f"replies: {sum(len(v) for v in by.values())} issues for {len(by)} charities", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"replies skipped ({e}); keeping the previous file if any", file=sys.stderr)


if __name__ == "__main__":
    main()
