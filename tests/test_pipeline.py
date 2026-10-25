"""Pipeline and site tests (standard library only): python3 -m unittest discover -s tests -v"""

import csv
import gzip
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.dom.minidom
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
sys.path.insert(0, HERE)

import build_data  # noqa: E402
import inflate64  # noqa: E402
import irszip  # noqa: E402
import render  # noqa: E402
import sources  # noqa: E402
from common import safe_business_name, safe_title  # noqa: E402
from fixtures import PEOPLE, ez_xml, return_xml  # noqa: E402
from parse990 import parse  # noqa: E402

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


RATING_WORDS = re.compile(r"\b(good|bad|best|worst|scam|fraud\w*|legit(imate)?|trustworth\w*|grade[sd]?|stars?|rating|rated|"
                          r"excellent|poor|red flag|warning|efficient|inefficient|waste\w*)\b", re.I)
# Sentences where these words describe what the site does NOT do, or quote a source.
RATING_OK = ["No ratings or grades", "No ratings", "no ratings", "no grades", "We don't rate", "don't rate or grade",
             "never as a grade", "not a verdict", "ratings, rankings by merit"]


class ParserTest(unittest.TestCase):
    def test_fields(self):
        r = parse(return_xml())
        self.assertEqual(r["ein"], "123456789")
        self.assertEqual(r["tax_year"], 2024)
        self.assertEqual(r["rev_total"], 12_000_000)
        self.assertEqual(r["contributions"], 9_000_000)
        self.assertEqual(r["gov_grants"], 1_000_000)
        self.assertEqual((r["exp_total"], r["exp_program"], r["exp_mgmt"], r["exp_fundraising"]),
                         (10_000_000, 8_500_000, 900_000, 600_000))
        self.assertEqual(r["net_assets"], 15_000_000)
        self.assertEqual(r["n_over_100k"], 9)
        self.assertEqual(r["board_voting"], 12)
        self.assertTrue(r["f"]["conflict_policy"])
        self.assertFalse(r["f"]["doc_retention"])
        self.assertIsNone(r["f"]["hospital"])
        self.assertEqual(len(r["programs"]), 2)
        self.assertEqual(r["programs_other_exp"], 500_000)

    def test_compensation_by_role_without_names(self):
        r = parse(return_xml())
        self.assertEqual(r["comp"][0]["total"], 390_000)
        self.assertEqual(r["comp"][0]["title"], "PRESIDENT & CEO")  # "(JANE DOE)" removed
        self.assertEqual(r["comp"][1]["total"], 245_000)
        self.assertEqual(r["n_listed"], 3)
        self.assertEqual(len(r["comp"]), 2)  # unpaid board chair not listed

    def test_contractors_businesses_only(self):
        r = parse(return_xml())
        self.assertEqual([c["name"] for c in r["contractors"]], ["ACME DIRECT MAIL LLC"])

    def test_no_person_names_anywhere(self):
        blob = json.dumps(parse(return_xml())).upper()
        for p in PEOPLE + ["JANE DOE", "DOE", "5555550100"]:
            self.assertNotIn(p, blob)

    def test_not_a_990(self):
        self.assertIsNone(parse(ez_xml()))

    def test_amended_flag(self):
        self.assertTrue(parse(return_xml(amended=True))["amended"])


class SanitizerTest(unittest.TestCase):
    def test_titles(self):
        self.assertEqual(safe_title("PRESIDENT & CEO AS OF 7/1/2024"), "PRESIDENT & CEO AS OF 7/1/2024")
        self.assertEqual(safe_title("DIRECTOR (JOHN SMITH)"), "DIRECTOR")
        self.assertEqual(safe_title("TRUSTEE - MARY JONES"), "TRUSTEE")
        self.assertEqual(safe_title("CEO (DR. JANE DOE, MD)"), "CEO")
        self.assertEqual(safe_title("MICHAEL JORDAN"), "")
        self.assertEqual(safe_title("SVP, CFO (THRU 3/2024)"), "SVP, CFO (THRU 3/2024)")

    def test_business_names(self):
        for keep in ["DELOITTE & TOUCHE LLP", "TURNER CONSTRUCTION COMPANY", "CCS FUNDRAISING", "RUFFALO NOEL LEVITZ LLC"]:
            self.assertEqual(safe_business_name(keep), keep)
        for drop in ["JOHN SMITH", "Doe, Jane", "JOHN SMITH CONSULTING LLC", "MARY ANN LEE MD PC", "DR JOHN SMITH"]:
            self.assertEqual(safe_business_name(drop), "", drop)


class MetricsTest(unittest.TestCase):
    def test_hundred_split_sums_to_100(self):
        for parts in ([0.9834, 0.0034, 0.0132], [1, 1, 1], [0.5, 0.25, 0.25], [0.99999, 0.000005, 0.000005], [3, 0, 0]):
            self.assertEqual(sum(render.hundred_split(parts)), 10000)
        self.assertEqual(render.hundred_split([0, 0, 0]), [0, 0, 0])

    def test_metrics(self):
        m = build_data.metrics(parse(return_xml()))
        self.assertAlmostEqual(m["program_share"], 0.85)
        self.assertAlmostEqual(m["fund_share"], 0.06)
        self.assertAlmostEqual(m["cost_per_dollar"], 600_000 / 9_000_000)
        self.assertAlmostEqual(m["months_net_assets"], 18.0)
        self.assertEqual(m["top_comp"], 390_000)

    def test_inconsistent_functional_split_is_not_shown(self):
        r = parse(return_xml(prog=5_000_000))  # columns don't add up to the total
        self.assertNotIn("program_share", build_data.metrics(r))

    def test_amended_return_wins(self):
        orig = {"oid": "1", "src": "gt", "rec": parse(return_xml(return_ts="2025-11-10T10:00:00-05:00"))}
        amend = {"oid": "2", "src": "irs", "rec": parse(return_xml(return_ts="2026-02-01T10:00:00-05:00", amended=True, exp=10_000_000))}
        self.assertEqual(build_data.pick_years([orig, amend])["202506"]["oid"], "2")
        self.assertEqual(build_data.pick_years([amend, orig])["202506"]["oid"], "2")

    def test_fiscal_year_change_keeps_both_returns(self):
        # A charity moving from June to December year-ends files a full year and a 6-month
        # short period with the same tax year; both are kept and the scorecard uses the full year.
        full = {"oid": "1", "src": "gt", "rec": parse(return_xml(tax_year=2024, period_end="2025-06-30"))}
        short_xml = return_xml(tax_year=2024, period_end="2025-12-31", rev=5_000_000, return_ts="2026-03-01T10:00:00-05:00")
        short_xml = short_xml.replace(b"<TaxPeriodBeginDt>2024-07-01</TaxPeriodBeginDt>", b"<TaxPeriodBeginDt>2025-07-01</TaxPeriodBeginDt>")
        short = {"oid": "2", "src": "gt", "rec": parse(short_xml)}
        picked = build_data.pick_years([full, short])
        self.assertEqual(set(picked), {"202506", "202512"})
        self.assertEqual(build_data.months(picked["202506"]["rec"]), 12)
        self.assertEqual(build_data.months(picked["202512"]["rec"]), 6)
        self.assertEqual(render.period({"ty": 2024, "period_end": "2025-12-31", "months": 6})[1], "FY2025 (6 mo.)")

    def test_text_cleanup(self):
        self.assertEqual(render.useful_text("Food Procurement - See Schedule O"), "Food Procurement")
        self.assertEqual(render.useful_text("SEE SCHEDULE O"), "")
        self.assertEqual(render.sentence_case("PROVIDES MEALS TO FAMILIES. SERVES THE U.S."), "Provides meals to families. Serves the U.S.")


class IrsZipTest(unittest.TestCase):
    def test_reads_member_with_ranges(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("a_public.xml", b"<x>" + b"a" * 5000 + b"</x>")
            z.writestr("dir/2026_public.xml", return_xml())
        blob = buf.getvalue()
        orig_range, orig_size = irszip._range, irszip.zip_size
        irszip._range = lambda url, s, e: blob[s:e + 1]
        irszip.zip_size = lambda url: (len(blob), "")
        try:
            cd = irszip.central_directory("mem://zip")
            self.assertEqual(set(cd), {"a_public.xml", "2026_public.xml"})
            self.assertEqual(parse(irszip.read_member("mem://zip", cd["2026_public.xml"]))["ein"], "123456789")
        finally:
            irszip._range, irszip.zip_size = orig_range, orig_size


class _Bits:
    """Deflate bit writer: values LSB-first, Huffman codes MSB-first."""
    def __init__(self):
        self.acc, self.n, self.out = 0, 0, bytearray()

    def put(self, value, nbits):
        self.acc |= value << self.n
        self.n += nbits
        while self.n >= 8:
            self.out.append(self.acc & 0xFF)
            self.acc >>= 8
            self.n -= 8

    def huff(self, code, length):
        self.put(int(format(code, f"0{length}b")[::-1], 2), length)

    def fixed(self, sym):
        if sym < 144:
            self.huff(0x30 + sym, 8)
        elif sym < 256:
            self.huff(0x190 + sym - 144, 9)
        elif sym < 280:
            self.huff(sym - 256, 7)
        else:
            self.huff(0xC0 + sym - 280, 8)

    def bytes(self):
        return bytes(self.out) + (bytes([self.acc & 0xFF]) if self.n else b"")


class Inflate64Test(unittest.TestCase):
    def test_plain_deflate_matches_zlib(self):
        import random
        import zlib
        rnd = random.Random(7)
        for size in (0, 1, 100, 5000, 200_000):
            words = [b"<Amt>", b"</Amt>", b"GRANT", b"PROGRAM", b"FOUNDATION", b" ", b"\n"]
            data = b"".join(rnd.choice(words) + str(rnd.randint(0, 99999)).encode() for _ in range(size // 8))[:size]
            for level in (1, 6, 9):
                c = zlib.compressobj(level, zlib.DEFLATED, -15)
                raw = c.compress(data) + c.flush()
                self.assertEqual(inflate64.inflate(raw, deflate64=False), data)

    def test_deflate64_long_length_and_far_distance(self):
        history = bytes(i % 251 for i in range(33_000))
        bw = _Bits()
        bw.put(1, 1)   # final block
        bw.put(1, 2)   # fixed Huffman
        for b in history:
            bw.fixed(b)
        bw.fixed(285)      # Deflate64: length 3 + 16 extra bits
        bw.put(1000, 16)
        bw.huff(30, 5)     # Deflate64: distance base 32769 + 14 extra bits
        bw.put(5, 14)
        bw.fixed(256)
        want = bytearray(history)
        start = len(want) - (32769 + 5)
        for i in range(1003):
            want.append(want[start + i])
        self.assertEqual(inflate64.inflate(bw.bytes(), deflate64=True), bytes(want))

    def test_corrupt_input_raises(self):
        with self.assertRaises(inflate64.Error):
            inflate64.inflate(b"\xff\xff\xff", deflate64=True)


class GuardTest(unittest.TestCase):
    def run_guard(self, prev, new):  # noqa: D401
        d = tempfile.mkdtemp()
        try:
            pp, np_ = os.path.join(d, "p.json"), os.path.join(d, "n.json")
            for path, obj in ((pp, prev), (np_, new)):
                with open(path, "w") as f:
                    json.dump(obj, f)
            try:
                sources.guard(pp, np_)
                return True
            except SystemExit:
                return False
        finally:
            shutil.rmtree(d)

    def test_guard(self):
        ok = {"charities": 25000, "filings": 140000, "with_functional": 24900, "fetch_failed_share": 0.0}
        self.assertTrue(self.run_guard(ok, ok))
        self.assertFalse(self.run_guard(ok, {**ok, "charities": 20000}))
        self.assertFalse(self.run_guard(ok, {**ok, "fetch_failed_share": 0.05}))
        self.assertFalse(self.run_guard(ok, {**ok, "charities": 3000, "filings": 15000, "with_functional": 3000}))


class SiteBuildTest(unittest.TestCase):
    """Builds a small site from fixture filings and checks the content rules on the output."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        work = os.path.join(cls.tmp, "work")
        os.makedirs(work)
        cov, rows = {}, []
        for i in range(36):
            ein = f"{100000000 + i * 7919:09d}"
            cov[ein] = {"bmf_name": f"ORG {i}", "city": "SPRINGFIELD", "state": "IL" if i % 2 else "MA", "zip": "62701",
                        "ntee": "P20" if i % 3 else "K31", "foundation": "15", "ruling": "1990", "affiliation": "3",
                        "group": "0000", "deductibility": "1", "index_name": f"ORG {i}", "index_rev": 12_000_000,
                        "index_ty": 2024, "index_website": ""}
            for ty in (2021, 2022, 2023, 2024):
                xml_bytes = return_xml(ein=ein, name=f"EXAMPLE CHARITY NUMBER {i} INC", tax_year=ty, period_end=f"{ty + 1}-06-30",
                                       return_ts=f"{ty + 1}-11-10T10:00:00-05:00", rev=12_000_000 + i * 100_000 + ty,
                                       contrib=9_000_000 + i * 1000, prog=8_500_000, mgmt=900_000, fund=600_000,
                                       dba="HELPING HANDS" if i == 0 else "")
                rows.append({"oid": f"{ty + 1}0{ein}", "src": "gt", "rec": parse(xml_bytes)})
        with gzip.open(os.path.join(work, "coverage.json.gz"), "wt") as f:
            json.dump(cov, f)
        with gzip.open(os.path.join(work, "filings.jsonl.gz"), "wt") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        env = {**os.environ, "CIM_WORK": work, "CIM_OUT": os.path.join(cls.tmp, "dist"),
               "CIM_BASE_URL": "https://example.github.io/charity-impact-media", "CIM_REPO": "example/charity-impact-media"}
        cls.env = env
        subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "build_data.py")], env=env, check=True, capture_output=True)
        subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "build_site.py")], env=env, check=True, capture_output=True)
        cls.dist = os.path.join(cls.tmp, "dist")
        cls.eins = sorted(cov)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def page(self, ein):
        return read(os.path.join(self.dist, "charity", ein, "index.html"))

    def all_text(self):
        out = []
        for d, _, fs in os.walk(self.dist):
            for fn in fs:
                if fn.endswith((".html", ".json", ".xml", ".csv", ".txt")):
                    out.append(read(os.path.join(d, fn)))
        return "\n".join(out)

    def test_every_charity_has_a_page(self):
        for ein in self.eins:
            self.assertTrue(os.path.exists(os.path.join(self.dist, "charity", ein, "index.html")))
            json.loads(read(os.path.join(self.dist, "charity", ein, "data.json")))

    def test_no_person_names_published(self):
        blob = self.all_text().upper()
        for p in PEOPLE + ["JANE DOE", "ROBERT BROWN", "5555550100"]:
            self.assertNotIn(p, blob)

    def test_correction_and_reply_links(self):
        for ein in self.eins:
            s = self.page(ein)
            self.assertIn("issues/new?template=correction.yml", s)
            self.assertIn("issues/new?template=reply.yml", s)
            self.assertIn('id="reply"', s)

    def test_every_figure_cites_its_filing(self):
        s = self.page(self.eins[0])
        anchors = set(re.findall(r'<li id="f(\d{6})">', s))
        self.assertEqual(anchors, {"202206", "202306", "202406", "202506"})
        for key in re.findall(r'href=#f(\d{6})', s):
            self.assertIn(key, anchors)
        # In the figure sections, no dollar amount or percentage stands outside a citation link,
        # except the medians column (computed across charities and labelled as such).
        for sec in ("spend", "came", "score", "progs", "pay", "gov"):
            m = re.search(rf'<section[^>]*aria-labelledby="{sec}".*?</section>', s, re.S)
            self.assertIsNotNone(m, sec)
            body = m.group(0)
            body = re.sub(r'<a href=#f\d{6}>.*?</a>', "", body)
            body = re.sub(r'<p class="ctx">.*?</p>', "", body, flags=re.S)  # median context sentence
            body = re.sub(r'<caption.*?</caption>', "", body, flags=re.S)
            body = re.sub(r'<h2.*?</h2>', "", body, flags=re.S)
            if sec == "score":
                body = re.sub(r'<td class="r">[^<]*</td></tr>', "</tr>", body)  # medians column
                body = re.sub(r'<tr><td>.*?</td>', "<tr>", body)  # measure labels ("per $1", "over $100,000")
            if sec == "gov":
                body = re.sub(r'<li><span>.*?</span></span>', "<li>", body)  # question labels ("over $15,000")
            loose = re.findall(r'(?<![\w#])(\$[\d,.]+[KMB]?|\d+\.\d%)', re.sub(r"<[^>]+>", " ", body))
            self.assertEqual(loose, [], f"{sec}: uncited figures {loose[:5]}")
        # The trend table cites by row: each row starts with its filing link.
        rows = re.findall(r'<tr><td><a href="https://projects\.propublica\.org/nonprofits/organizations/\d{9}/\d+/full">', s)
        self.assertEqual(len(rows), 4)

    def test_filing_year_on_page(self):
        s = self.page(self.eins[0])
        self.assertIn("FY2025", s)
        self.assertIn("tax year 2024", s)

    def test_no_rating_language(self):
        for ein in self.eins[:6]:
            text = re.sub(r"<[^>]+>", " ", self.page(ein))
            for ok in RATING_OK:
                text = text.replace(ok, "")
            self.assertEqual(RATING_WORDS.findall(text), [], ein)

    def test_no_status_colors(self):
        css = read(os.path.join(ROOT, "site", "static", "app.css")).lower()
        for status in ("#0ca30c", "#fab219", "#ec835a", "#d03b3b", "red;", "green;"):
            self.assertNotIn(status, css)

    def test_structured_data_and_meta(self):
        s = self.page(self.eins[0])
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s):
            json.loads(block)
        self.assertIn('<link rel="canonical" href="https://example.github.io/charity-impact-media/charity/', s)
        self.assertIn('property="og:image"', s)
        self.assertIn("Also known as Helping Hands", s)

    def test_escaping(self):
        s = render.esc('<script>alert("x")</script>')
        self.assertNotIn("<script>", s)

    def test_site_files(self):
        sm = read(os.path.join(self.dist, "sitemap.xml"))
        xml.dom.minidom.parseString(sm)
        for ein in self.eins:
            self.assertIn(f"/charity/{ein}/</loc>", sm)
        self.assertIn("Sitemap: https://example.github.io/charity-impact-media/sitemap.xml",
                      read(os.path.join(self.dist, "robots.txt")))
        xml.dom.minidom.parseString(read(os.path.join(self.dist, "feed.xml")))
        search = json.loads(read(os.path.join(self.dist, "assets", "search.json")))
        self.assertEqual(len(search), len(self.eins))
        rows = list(csv.DictReader(io.StringIO(read(os.path.join(self.dist, "data", "charities.csv")))))
        self.assertEqual(len(rows), len(self.eins))
        self.assertEqual(rows[0]["program_share"], "0.8500")
        for p in ("index.html", "404.html", "compare/index.html", "embed/index.html", "method/index.html",
                  "corrections/index.html", "guides/givingtuesday-checklist/index.html", "category/human-services/index.html",
                  "state/il/index.html", "charities/e/index.html"):
            self.assertTrue(os.path.exists(os.path.join(self.dist, p)), p)

    def test_guides_have_no_unfilled_placeholders(self):
        for d, _, fs in os.walk(os.path.join(self.dist, "guides")):
            for fn in fs:
                self.assertNotIn("{{", read(os.path.join(d, fn)), d)

    def test_slim_pages_keep_the_budget(self):
        out = os.path.join(self.tmp, "dist-slim")
        env = {**self.env, "CIM_OUT": out, "CIM_PAGES_BUDGET_MB": "0.3"}
        r = subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", "build_site.py")], env=env, check=True, capture_output=True, text=True)
        self.assertRegex(r.stderr, r"\d+ slim")
        s = read(os.path.join(out, "charity", self.eins[-1], "index.html"))
        self.assertIn("issues/new?template=correction.yml", s)  # slim pages keep the right of reply
        self.assertIn('aria-labelledby="score"', s)
        self.assertIn('aria-labelledby="faqh"', s)  # slim pages keep the questions people search for


if __name__ == "__main__":
    unittest.main()
