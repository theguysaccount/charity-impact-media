"""Live self-test against the real sources (network). Skipped unless CIM_LIVE=1.

Each test reads the tail of the newest index with an HTTP range request, picks the most
recently listed Form 990, fetches it the same way the pipeline does and parses it. A failure
means a source moved or the IRS schema changed: fix it before Monday's refresh."""

import csv
import io
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pipeline"))

import irszip  # noqa: E402
import sources  # noqa: E402
from common import GT, http  # noqa: E402
from parse990 import parse  # noqa: E402

LIVE = os.environ.get("CIM_LIVE") == "1"


def tail_rows(url, nbytes=400_000):
    """The last rows of a CSV index: a range request where the server allows it (S3), the
    whole file where it doesn't (the IRS answers 200 to ranges on its index CSVs)."""
    try:
        size = int(http(url, method="HEAD").headers["Content-Length"])
        head = irszip._range(url, 0, 4095).decode("utf-8", "replace").splitlines()[0]
        lines = irszip._range(url, max(0, size - nbytes), size - 1).decode("utf-8", "replace").splitlines()[1:]
    except (RuntimeError, TypeError, ValueError):  # no ranges, or no Content-Length on HEAD
        with http(url, timeout=300) as r:
            text = r.read().decode("utf-8", "replace").splitlines()
        head, lines = text[0], text[-3000:]
    return list(csv.DictReader(io.StringIO(head + "\n" + "\n".join(lines))))


def check(rec):
    assert rec is not None, "not parsed as a Form 990"
    assert rec["ein"] and rec["tax_year"], rec
    assert rec["rev_total"] is not None and rec["exp_total"] is not None, "revenue/expenses missing: schema change?"


@unittest.skipUnless(LIVE, "set CIM_LIVE=1 to run against the live sources")
class LiveSources(unittest.TestCase):
    def test_data_lake(self):
        idx = sources.gt_indexes()
        year = max(y for y in idx if idx[y][2] > 50_000_000)
        rows = [r for r in tail_rows(f"{GT}/{idx[year][1]}") if r.get("FormType") == "990" and r.get("URL")]
        self.assertTrue(rows, "no Form 990 rows at the end of the newest index")
        with http(rows[-1]["URL"]) as r:
            check(parse(r.read()))

    def test_irs_monthly_release(self):
        year = sources.irs_years()[-1]
        url = sources.irs_index_url(year)
        if not sources.last_modified(url):
            year -= 1  # early January: this year's index may not exist yet
            url = sources.irs_index_url(year)
        rows = tail_rows(url)
        rows = [r for r in rows if r.get("RETURN_TYPE") == "990"]
        self.assertTrue(rows, "no Form 990 rows at the end of the IRS index")
        r = rows[-1]
        base = url.rsplit("/", 1)[0] + "/"
        name = r["OBJECT_ID"] + "_public.xml"
        for zurl in irszip.batch_zip_urls(base, r["XML_BATCH_ID"]):
            cd = irszip.central_directory(zurl)
            if name in cd:
                check(parse(irszip.read_member(zurl, cd[name])))
                return
        self.fail(f"{name} not found in the {r['XML_BATCH_ID']} zips")


if __name__ == "__main__":
    unittest.main()
