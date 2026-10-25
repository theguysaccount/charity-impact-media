#!/usr/bin/env python3
"""Tell IndexNow search engines (Bing, Yandex, Seznam, Naver and others) which pages changed.

  CIM_BASE_URL=https://<user>.github.io/<repo> python3 pipeline/indexnow.py data/work/urls_changed.txt

The key file (<key>.txt) is published at the site root by build_site.py. A failed
submission is logged but never fails the workflow: the site itself is already live.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCH = 10000


def main():
    base = (os.environ.get("CIM_BASE_URL") or "").rstrip("/")
    if not base or len(sys.argv) < 2:
        sys.exit("usage: CIM_BASE_URL=... indexnow.py urls.txt")
    key = open(os.path.join(ROOT, "site", "indexnow-key.txt")).read().strip()
    host = urllib.parse.urlparse(base).netloc
    with open(sys.argv[1]) as f:
        urls = [u.strip() for u in f if u.strip() and urllib.parse.urlparse(u.strip()).netloc == host]
    print(f"IndexNow: {len(urls)} URLs", file=sys.stderr)
    for i in range(0, len(urls), BATCH):
        body = json.dumps({"host": host, "key": key, "keyLocation": f"{base}/{key}.txt", "urlList": urls[i:i + BATCH]}).encode()
        # A new key answers 403 until the engine has fetched the key file: retry a few times.
        for attempt in range(4):
            if attempt:
                time.sleep(60 * attempt)
            req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
                                         headers={"Content-Type": "application/json; charset=utf-8"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    print(f"  batch {i // BATCH + 1}: {r.status}", file=sys.stderr)
                    break
            except urllib.error.HTTPError as e:
                print(f"  batch {i // BATCH + 1}: {e.code} {e.read()[:200]!r}", file=sys.stderr)
                if not (e.code in (403, 429) or e.code >= 500):
                    break
            except Exception as e:  # noqa: BLE001
                print(f"  batch {i // BATCH + 1}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
