#!/usr/bin/env python3
"""Public inputs: fingerprint them, download them, and guard a rebuild.

  python3 pipeline/sources.py check [previous_sources.json]
      Fingerprints the GivingTuesday 990 Data Lake yearly indexes, the IRS monthly e-file
      indexes (this year and last), the IRS EO Business Master File and this pipeline's code.
      Prints changed=true|false (for $GITHUB_OUTPUT) and writes data/work/sources.json.
  python3 pipeline/sources.py download
      Downloads every input named in data/work/sources.json (about 2.5 GB).
  python3 pipeline/sources.py guard previous_stats.json new_stats.json
      Refuses to publish a rebuild that looks broken next to the last good release.

All sources are anonymous and need no key.
"""

import datetime
import hashlib
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BMF_URL, GT, IRS_XML_BASE, RAW, ROOT, WORK, ensure_dir, fetch_to, http  # noqa: E402

FIRST_YEAR = 2019


def gt_indexes():
    """{tax_year: (built_date, key, size)}: the newest index build of each year."""
    out, token = {}, ""
    while True:
        url = f"{GT}/?list-type=2&prefix=Indices/990xmls/yearly/" + (
            f"&continuation-token={urllib.parse.quote(token)}" if token else "")
        body = http(url).read().decode()
        for key, size in re.findall(r"<Key>([^<]+)</Key>.*?<Size>(\d+)</Size>", body):
            m = re.search(r"/(\d{4})_efiledata_xmls_created_on_(\d{4}-\d{2}-\d{2})\.csv$", key)
            if m:
                y, built = int(m.group(1)), m.group(2)
                if y >= FIRST_YEAR and (y not in out or built > out[y][0]):
                    out[y] = (built, key, int(size))
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", body)
        if not m:
            return out
        token = m.group(1)


def irs_years(today=None):
    y = (today or datetime.date.today()).year
    return [y - 1, y]


def irs_index_url(year):
    return IRS_XML_BASE.format(year=year) + f"index_{year}.csv"


def last_modified(url):
    """A version stamp for a URL: Last-Modified, else ETag, else Content-Length ("" if unreachable)."""
    try:
        with http(url, method="HEAD") as r:
            h = r.headers
            return h.get("Last-Modified") or h.get("ETag") or h.get("Content-Length") or "present"
    except RuntimeError:
        return ""


DATA_CODE = ["common.py", "parse990.py", "irszip.py", "select_filings.py", "fetch_filings.py", "build_data.py",
             "names_first.txt", "names_last.txt"]


def code_hash():
    """Hash of the code that shapes the data release (page templates only need a redeploy)."""
    h = hashlib.sha256()
    d = os.path.join(ROOT, "pipeline")
    for fn in DATA_CODE:
        with open(os.path.join(d, fn), "rb") as f:
            h.update(fn.encode() + f.read())
    return h.hexdigest()[:16]


def fingerprint():
    gt = gt_indexes()
    return {
        "gt": {str(y): {"built": b, "key": k, "size": s} for y, (b, k, s) in sorted(gt.items())},
        "irs": {str(y): last_modified(irs_index_url(y)) for y in irs_years()},
        "bmf": {f"eo{i}": last_modified(BMF_URL.format(i=i)) for i in range(1, 5)},
        "code": code_hash(),
    }


def check(prev_path):
    fp = fingerprint()
    ensure_dir(WORK)
    with open(os.path.join(WORK, "sources.json"), "w") as f:
        json.dump(fp, f, indent=1, sort_keys=True)
    prev = {}
    if prev_path and os.path.exists(prev_path):
        with open(prev_path) as f:
            prev = json.load(f)
    changed = fp != prev
    print(f"changed={'true' if changed else 'false'}")
    print(json.dumps(fp, sort_keys=True), file=sys.stderr)


def download():
    with open(os.path.join(WORK, "sources.json")) as f:
        fp = json.load(f)
    for i in range(1, 5):
        fetch_to(BMF_URL.format(i=i), os.path.join(RAW, "bmf", f"eo{i}.csv"))
    for y, v in fp["gt"].items():
        dest = os.path.join(RAW, "gt_index", f"{y}_index.csv")
        stamp = dest + ".built"
        if os.path.exists(dest) and os.path.exists(stamp) and open(stamp).read().strip() == v["built"]:
            continue
        fetch_to(f"{GT}/{v['key']}", dest)
        with open(stamp, "w") as f:
            f.write(v["built"])
    for y in fp["irs"]:
        # Downloaded whatever HEAD said: losing the IRS indexes would silently drop every filing
        # the data lake doesn't have yet. Only this year's index may legitimately not exist yet.
        try:
            fetch_to(irs_index_url(int(y)), os.path.join(RAW, "irs", f"index_{y}.csv"))
        except RuntimeError as e:
            if int(y) < max(map(int, fp["irs"])):
                raise
            print(f"  no IRS index for {y} yet ({e})", file=sys.stderr)


def guard(prev_path, new_path):
    with open(new_path) as f:
        new = json.load(f)
    problems = []
    if new["charities"] < 5000:
        problems.append(f"only {new['charities']} charities")
    if new["filings"] < 4 * new["charities"]:
        problems.append(f"only {new['filings']} filings for {new['charities']} charities")
    if new.get("fetch_failed_share", 0) > 0.02:
        problems.append(f"{new['fetch_failed_share']:.1%} of filings failed to download or parse")
    if prev_path and os.path.exists(prev_path):
        with open(prev_path) as f:
            prev = json.load(f)
        # Coverage moves slowly (charities cross the $10M line, merge or file late); filings only
        # accumulate. A sharper fall means a source or a step broke.
        for label, tol in (("charities", 0.05), ("filings", 0.03), ("with_functional", 0.05)):
            if new[label] < prev[label] * (1 - tol):
                problems.append(f"{label} fell from {prev[label]} to {new[label]}")
        if prev.get("irs_filings", 0) > 1000 and new.get("irs_filings", 0) < 0.5 * prev["irs_filings"]:
            problems.append(f"filings read from the IRS monthly releases fell from {prev['irs_filings']} to {new.get('irs_filings', 0)}")
    if problems:
        print("GUARD FAILED: " + "; ".join(problems), file=sys.stderr)
        sys.exit(1)
    print("guard ok", file=sys.stderr)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "check":
        check(sys.argv[2] if len(sys.argv) > 2 else "")
    elif cmd == "download":
        download()
    elif cmd == "guard":
        guard(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
        sys.exit(2)
