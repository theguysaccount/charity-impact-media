"""Shared helpers for the Charity Impact Media pipeline: paths, HTTP, EINs, money,
display names and the person-name checks that keep private individuals out of the
published pages. Standard library only (Python 3.9+).

The name normalisation and person checks are adapted from WHOFUNDS
(github.com/theguysaccount/whofunds-open-grant-graph, CC0)."""

import csv
import gzip
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
WORK = os.environ.get("CIM_WORK") or os.path.join(ROOT, "data", "work")

GT = "https://gt990datalake-rawdata.s3.amazonaws.com"
GT_XML_URL = GT + "/EfileData/XmlFiles/{object_id}_public.xml"
IRS_XML_BASE = "https://apps.irs.gov/pub/epostcard/990/xml/{year}/"
BMF_URL = "https://www.irs.gov/pub/irs-soi/eo{i}.csv"
PROPUBLICA_FILING = "https://projects.propublica.org/nonprofits/organizations/{ein}/{object_id}/full"
PROPUBLICA_ORG = "https://projects.propublica.org/nonprofits/organizations/{ein}"
IRS_TEOS = "https://apps.irs.gov/app/eos/allSearch?ein1={ein}&names=&resultsPerPage=25&indexOfFirstRow=0&dispatchMethod=searchAll&city=&state=All+States&country=US&postDateFrom=&postDateTo=&exemptTypeCode=al&deductibility=all&sortColumn=orgName&isDescending=false&submitName=Search"

UA = {"User-Agent": "charity-impact-media (+https://github.com/theguysaccount/charity-impact-media)"}

csv.field_size_limit(sys.maxsize)


def open_text(path, mode="r"):
    """Open .csv/.jsonl or their .gz versions transparently (utf-8)."""
    if path.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, mode + "b"), encoding="utf-8", newline="")
    return open(path, mode, encoding="utf-8", newline="")


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def http(url, method="GET", headers=None, retries=4, timeout=120):
    """urlopen with retries and backoff. Returns the response object."""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, method=method, headers={**UA, **(headers or {})})
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404, 416):
                break
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"{method} {url}: {last}")


def fetch_to(url, dest):
    """Download url to dest atomically."""
    ensure_dir(os.path.dirname(dest))
    tmp = dest + ".part"
    with http(url) as r, open(tmp, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    os.replace(tmp, dest)
    print(f"  {url} -> {dest} ({os.path.getsize(dest) / 1e6:.0f} MB)", file=sys.stderr)


def write_json(path, obj, gz=False):
    ensure_dir(os.path.dirname(path) or ".")
    data = json.dumps(obj, separators=(",", ":"), ensure_ascii=False, sort_keys=True).encode("utf-8")
    if gz:
        with gzip.GzipFile(path, "wb", compresslevel=9, mtime=0) as f:
            f.write(data)
    else:
        with open(path, "wb") as f:
            f.write(data)
    return len(data)


def read_json(path):
    if path.endswith(".gz"):
        with gzip.open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8"))
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt_ein(ein):
    ein = re.sub(r"[^0-9]", "", str(ein or ""))
    return ein.zfill(9) if ein else ""


def ein_dash(ein):
    ein = fmt_ein(ein)
    return f"{ein[:2]}-{ein[2:]}" if ein else ""


def money(v):
    """Integer dollars from a filed amount; None when the field is absent."""
    if v is None:
        return None
    try:
        return int(round(float(str(v).replace(",", "").strip())))
    except ValueError:
        return None


def ascii_upper(s):
    s = unicodedata.normalize("NFKD", s or "")
    return s.encode("ascii", "ignore").decode("ascii").upper()


# --------------------------------------------------------------------------
# Display names
# --------------------------------------------------------------------------

SMALL = {"OF", "AND", "THE", "FOR", "IN", "AT", "ON", "TO", "A", "AN", "BY", "WITH", "FROM", "DE", "LA", "DEL", "Y", "OR"}
ACRONYMS = set("""YMCA YWCA YMHA YWHA NAACP ACLU USA US PTA PTO PTSA PTSO SPCA ASPCA NPR PBS WGBH WBUR WNET KQED WNYC
MIT UCLA NYU UCSF USC UNC LSU SMU TCU BYU CUNY SUNY AIDS HIV LGBT LGBTQ LGBTQIA STEM VFW NAMI JCC UJA ADL UNICEF
UNCF NFL NBA MLB NHL NCAA ALS MS CF ARC AARP KIPP IDEA TED RSVP UN WWF NRDC EDF IRC CRS HFH HFHI
II III IV VI VII VIII IX XI NY NYC LA DC SF USO PFLAG GLSEN NARAL IJM ONE CARE AJC JDC HIAS ORT AIPAC JNF ZOA
GE IBM UPS CVS PNC HSBC KPMG PWC AIG BMO UBS HP BP ESPN NBC CBS HCA AMD GM BNY TIAA USAA PGA LPGA WNBA MLS
UPMC UCHEALTH UCSD UCI UCD UAB UNLV UTSA OHSU VCU MUSC NIH CDC FBI CIA HHS HUD DOD VA RN MD DDS PHD
ASU FSU OSU PSU MSU ISU KSU WSU UNH UVM URI UMASS SCAD RISD CALTECH WGBY WQED KCET WTTW CPB YMCAS ALSAC
AFL CIO SEIU UAW ACS ADA AHA AMA ACOG ACP NEA AFT AAUW ACLJ SPLC CASA BBBS CCF EWTN CBN TBN JW CRU""".split())
MIXED = {"AMAZONSMILE": "AmazonSmile", "JPMORGAN": "JPMorgan", "PAYPAL": "PayPal", "FEDEX": "FedEx",
         "BLACKROCK": "BlackRock", "PEPSICO": "PepsiCo", "GOFUNDME": "GoFundMe", "YOUTUBE": "YouTube",
         "MCDONALDS": "McDonalds", "IHEART": "iHeart", "LINKEDIN": "LinkedIn", "GIVEWELL": "GiveWell",
         "DONORSCHOOSE": "DonorsChoose", "WORLDVISION": "WorldVision", "UCHEALTH": "UCHealth"}


def nice_name(s):
    """Readable display casing for an all-caps filed or registered name (mixed case is kept)."""
    s = " ".join((s or "").split())
    if not s:
        return s
    if re.search(r"[a-z]", s) and re.search(r"[A-Z]", s):
        return s
    out = []
    for i, w in enumerate(s.split(" ")):
        core = re.sub(r"[^A-Za-z0-9]", "", w).upper()
        if core in MIXED and core in w.upper():
            out.append(w.upper().replace(core, MIXED[core]))
        elif core in ACRONYMS or (any(c.isdigit() for c in core) and not re.match(r"^\d+(ST|ND|RD|TH)$", core)):
            out.append(w.upper())
        elif i > 0 and core in SMALL:
            out.append(w.lower())
        else:
            parts = re.split(r"([\-/'.&(])", w.lower())
            out.append("".join(p[:1].upper() + p[1:] if p and p[0].isalpha() else p for p in parts))
    t = " ".join(out)
    t = re.sub(r"'S\b", "'s", t)
    t = re.sub(r"\bMc([a-z])", lambda m: "Mc" + m.group(1).upper(), t)
    t = re.sub(r"\bInc\b\.?", "Inc.", t)
    return t


def slugify(s, n=60):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"['’]", "", s).replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:n].rstrip("-")


# --------------------------------------------------------------------------
# Person-name checks (keep private individuals off the site)
# --------------------------------------------------------------------------

def _load_names(fn):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), fn)
    with open(p, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


# 1990 Census given names and the 40,000 most common 2010 Census surnames (US government, public domain).
FIRST_NAMES = _load_names("names_first.txt")
SURNAMES = _load_names("names_last.txt")

ORG_WORDS = set("""
INC INCORPORATED CORP CORPORATION COMPANY CO LTD LIMITED LLC LLP LP PC PLLC PA NA GROUP PARTNERS PARTNERSHIP
ASSOCIATES ASSOCIATION SERVICES SERVICE SOLUTIONS SYSTEMS TECHNOLOGIES TECHNOLOGY CONSULTING CONSULTANTS
CONSTRUCTION CONTRACTORS CONTRACTING BUILDERS ENGINEERING ENGINEERS ARCHITECTS ARCHITECTURE DESIGN STUDIO
MANAGEMENT MARKETING MEDIA COMMUNICATIONS ADVERTISING AGENCY PRINTING MAIL MAILING DIRECT DATA DIGITAL
HEALTH HEALTHCARE MEDICAL HOSPITAL PHYSICIANS CLINIC PHARMACY STAFFING SECURITY STAFF LABS LABORATORIES
BANK TRUST CAPITAL INVESTMENTS INVESTMENT ADVISORS ADVISORY FINANCIAL FINANCE INSURANCE AUDIT TAX ACCOUNTING
LAW LEGAL ATTORNEYS UNIVERSITY COLLEGE SCHOOL INSTITUTE FOUNDATION FUND CENTER CENTRE NETWORK INTERNATIONAL
NATIONAL AMERICA AMERICAN USA GLOBAL WORLDWIDE ENTERPRISES INDUSTRIES HOLDINGS PROPERTIES REALTY ENERGY
ELECTRIC MECHANICAL PLUMBING ROOFING LANDSCAPING CLEANING JANITORIAL FOOD FOODS TRANSPORT TRANSPORTATION
LOGISTICS FREIGHT SUPPLY SOFTWARE CLOUD SALESFORCE MICROSOFT ORACLE GOOGLE AMAZON DELOITTE ERNST YOUNG KPMG
PWC PRICEWATERHOUSECOOPERS ACCENTURE MCKINSEY BAIN BOSTON CONSULTING CAPGEMINI COGNIZANT INFOSYS WIPRO
TELEMARKETING FUNDRAISING PHILANTHROPY PHILANTHROPIC COUNSEL STRATEGIES STRATEGY PRODUCTIONS PRODUCTION
""".split())

TITLE_WORDS = set("""
PRESIDENT CEO CFO COO CIO CTO CMO CHRO CDO CAO CHIEF EXECUTIVE OFFICER DIRECTOR TRUSTEE CHAIR CHAIRMAN CHAIRWOMAN
CHAIRPERSON VICE VP SVP EVP AVP TREASURER SECRETARY FORMER INTERIM ACTING SENIOR SR EXEC GENERAL COUNSEL
MEMBER BOARD OF THE AND FOR IN AT MANAGER HEAD DEAN PROVOST PROFESSOR PHYSICIAN SURGEON NURSE CHIEF
ADMINISTRATOR SUPERINTENDENT PRINCIPAL COACH RABBI PASTOR BISHOP REV REVEREND FATHER SISTER BROTHER
OPERATIONS FINANCE FINANCIAL MEDICAL DEVELOPMENT ADVANCEMENT PROGRAMS PROGRAM MARKETING COMMUNICATIONS
TECHNOLOGY INFORMATION HUMAN RESOURCES LEGAL STRATEGY STRATEGIC OFFICER EX OFFICIO EXOFFICIO NONVOTING
EMERITUS EMERITA PAST CO FOUNDER COFOUNDER ASSOCIATE ASSISTANT DEPUTY REGIONAL DIVISION DEPARTMENT
""".split())


CREDENTIALS = {"MD", "DO", "DDS", "DMD", "PHD", "CPA", "ESQ", "JD", "RN", "NP", "PA", "PC", "JR", "SR", "II", "III",
               "IV", "MBA", "MPH", "MSW", "LCSW", "DR", "MR", "MRS", "MS", "REV", "FACS", "FACP", "DVM"}


def _tokens(s):
    return re.sub(r"[^A-Z ]+", " ", ascii_upper(s).replace("'", "")).split()


def person_like(seg):
    """True when a short fragment reads like a person's name: GIVEN [I] SURNAME or
    SURNAME, GIVEN, with no organisation words. Deliberately conservative."""
    s = ascii_upper(seg)
    if "," in s:
        a, _, b = s.partition(",")
        bt = _tokens(b)
        if bt and bt[0] in FIRST_NAMES and _tokens(a) and not (set(_tokens(a)) & ORG_WORDS):
            return True
    toks = [t for t in _tokens(s) if t not in CREDENTIALS]
    if not 2 <= len(toks) <= 4 or set(toks) & ORG_WORDS:
        return False
    core = [t for t in toks if len(t) > 1]
    if len(core) < 2:
        return False
    first, last = core[0], core[-1]
    return (first in FIRST_NAMES and last in SURNAMES) or (first in SURNAMES and last in FIRST_NAMES)


SPLIT = re.compile(r"\s*(?:\(|\)|/|;|:|,(?=\s*[A-Z]{2,}\s)|\s-+\s|\s+&\s+|\bC/O\b|\bATTN\b|%)\s*", re.I)


def safe_business_name(name):
    """A contractor's filed business name if no part of it could be a natural person, else ''."""
    n = " ".join((name or "").split())
    if not n:
        return ""
    parts = [p for p in SPLIT.split(n) if p and p.strip()]
    for p in [n] + parts:
        # "JANE DOE CONSULTING LLC" names a person too: test what is left without business words.
        bare = " ".join(t for t in _tokens(p) if t not in ORG_WORDS and t not in ("DBA", "THE"))
        if person_like(p) or person_like(bare):
            return ""
    toks = _tokens(n)
    # Two or three plain words with no business word ("JOHN SMITH CPA" is caught above;
    # "SMITH JOHNSON" is withheld here).
    if 2 <= len(toks) <= 3 and not set(toks) & ORG_WORDS and all(t in FIRST_NAMES or t in SURNAMES for t in toks):
        return ""
    return n


def safe_title(title):
    """A Part VII title with any embedded person name removed ('' when nothing safe remains)."""
    t = " ".join((title or "").split())
    if not t:
        return ""
    # Split on separators but keep them, so dates like 7/1/2024 survive untouched.
    pieces = re.split(r"(\s*(?:\(|\)|;|,|\s-+\s)\s*)", t)
    kept = []
    for p in pieces:
        if p and not re.fullmatch(r"\s*(?:\(|\)|;|,|\s-+\s)\s*", p):
            toks = _tokens(p)
            if person_like(p) and not set(toks) & TITLE_WORDS:
                continue
            if toks and all(t in CREDENTIALS for t in toks) and len(kept) > 0 and kept[-1].strip() in (",", "(", ";"):
                continue  # a credential left over from a removed name ("..., MD")
        kept.append(p)
    out = "".join(kept)
    out = re.sub(r"\(\s*[,;]?\s*\)", "", out)
    out = re.sub(r"\(\s*[,;]\s*", "(", out)
    out = re.sub(r"\s*([,;])\s*([,;]\s*)+", r"\1 ", out)
    return " ".join(out.split()).strip(" ,;-")[:80]


def clip(s, n):
    s = " ".join((s or "").split())
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"
