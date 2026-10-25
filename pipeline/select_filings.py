#!/usr/bin/env python3
"""Choose the charities the site covers and every Form 990 filing it needs for them.

  python3 pipeline/select_filings.py            # -> data/work/coverage.json.gz, data/work/needed.csv

Coverage: 501(c)(3) public charities in the current IRS Business Master File whose latest
Form 990 (tax year within the last three complete years) reports total revenue of at
least CIM_MIN_REVENUE dollars (default $10 million).

Filings: for each covered charity and tax year since 2019, the latest submission in the
GivingTuesday 990 Data Lake (an amended return supersedes the original), plus any Form 990
in the IRS's monthly e-file batches that the data lake does not have yet. When a tax year
has both, the parsed return with the later ReturnTs wins (see build_data.py).
"""

import csv
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import GT_XML_URL, IRS_XML_BASE, RAW, WORK, ensure_dir, fmt_ein, money, open_text, write_json  # noqa: E402
from sources import FIRST_YEAR  # noqa: E402

MIN_REVENUE = int(os.environ.get("CIM_MIN_REVENUE", 10_000_000))
PRIVATE_FOUNDATION_CODES = {"02", "03", "04"}
NEEDED_FIELDS = ["object_id", "ein", "ty", "source", "ref", "size"]


def load_bmf():
    out = {}
    for fn in sorted(glob.glob(os.path.join(RAW, "bmf", "eo*.csv"))):
        with open_text(fn) as f:
            for r in csv.DictReader(f):
                if r["SUBSECTION"] != "03" or r["FOUNDATION"] in PRIVATE_FOUNDATION_CODES:
                    continue
                out[fmt_ein(r["EIN"])] = {
                    "bmf_name": r["NAME"], "city": r["CITY"], "state": r["STATE"], "zip": r["ZIP"][:5],
                    "ntee": r["NTEE_CD"], "foundation": r["FOUNDATION"], "ruling": r["RULING"][:4],
                    "affiliation": r["AFFILIATION"], "group": r["GROUP"], "deductibility": r["DEDUCTIBILITY"],
                }
    return out


def gt_years():
    ys = {}
    for fn in glob.glob(os.path.join(RAW, "gt_index", "*_index.csv")):
        y = int(os.path.basename(fn)[:4])
        ys[y] = (fn, os.path.getsize(fn))
    return dict(sorted(ys.items()))


def newest_complete_year(ys):
    """Newest tax year whose index is at least 70% the size of the year before it."""
    for y in sorted(ys, reverse=True):
        if y - 1 in ys and ys[y][1] >= 0.7 * ys[y - 1][1]:
            return y
    return max(ys)


def main():
    bmf = load_bmf()
    ys = gt_years()
    full = newest_complete_year(ys)
    print(f"BMF public charities: {len(bmf)}; GT index years {min(ys)}-{max(ys)}, newest complete {full}", file=sys.stderr)

    best = {}     # (ein, ty) -> (sortkey, row)
    gt_ids = set()
    for y, (fn, _) in ys.items():
        with open_text(fn) as f:
            for r in csv.DictReader(f):
                gt_ids.add(r["ObjectId"])
                if r["FormType"] != "990":
                    continue
                ein = fmt_ein(r["EIN"])
                if ein not in bmf:
                    continue
                try:
                    ty = int(r["TaxYear"])
                except ValueError:
                    continue
                if ty < FIRST_YEAR:
                    continue
                k = (r["SubmittedOn"] or "", r["ReturnTs"] or "", r["ObjectId"])
                cur = best.get((ein, ty))
                if cur is None or k > cur[0]:
                    best[(ein, ty)] = (k, r)

    latest = {}
    for (ein, ty), (_, r) in best.items():
        if ein not in latest or ty > latest[ein][0]:
            latest[ein] = (ty, r)
    covered = {}
    for ein, (ty, r) in latest.items():
        rev = money(r["TotalRevenueCY"]) or 0
        if ty >= full - 2 and rev >= MIN_REVENUE:
            covered[ein] = {**bmf[ein], "index_name": r["OrganizationName"], "index_rev": rev, "index_ty": ty,
                            "index_website": r["Website"]}
    print(f"covered charities: {len(covered)} (latest revenue >= ${MIN_REVENUE:,}, latest tax year >= {full - 2})", file=sys.stderr)

    rows = []
    for (ein, ty), (_, r) in sorted(best.items()):
        if ein in covered:
            rows.append({"object_id": r["ObjectId"], "ein": ein, "ty": ty, "source": "gt",
                         "ref": r["URL"] or GT_XML_URL.format(object_id=r["ObjectId"]), "size": r["FileSizeBytes"] or ""})
    n_gt = len(rows)

    for fn in sorted(glob.glob(os.path.join(RAW, "irs", "index_*.csv"))):
        year = re.search(r"index_(\d{4})\.csv$", fn).group(1)
        with open_text(fn) as f:
            for r in csv.DictReader(f):
                if r["RETURN_TYPE"] != "990" or r["OBJECT_ID"] in gt_ids:
                    continue
                ein = fmt_ein(r["EIN"])
                if ein not in covered:
                    continue
                tp = r["TAX_PERIOD"]
                ty = int(tp[:4]) if tp[4:6] == "12" else int(tp[:4]) - 1
                if ty < FIRST_YEAR:
                    continue
                rows.append({"object_id": r["OBJECT_ID"], "ein": ein, "ty": ty, "source": "irs",
                             "ref": IRS_XML_BASE.format(year=year) + "|" + r["XML_BATCH_ID"], "size": ""})
    print(f"filings needed: {len(rows)} ({n_gt} from the data lake, {len(rows) - n_gt} only in IRS monthly batches)", file=sys.stderr)

    ensure_dir(WORK)
    write_json(os.path.join(WORK, "coverage.json.gz"), covered, gz=True)
    with open(os.path.join(WORK, "needed.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=NEEDED_FIELDS)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
