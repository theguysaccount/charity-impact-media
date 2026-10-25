#!/usr/bin/env python3
"""Turn the parse cache into one record per covered charity: its filings by tax year,
the scorecard measures from its latest filing, and category medians for context.

  python3 pipeline/build_data.py        # -> data/work/site_data.json.gz, data/work/stats.json

Inputs (data/work): coverage.json.gz, filings.jsonl.gz, and when present
first_seen.json.gz (when each filing was first published here), whofunds.json
(cross-links) and replies.json (right-of-reply and correction issues).

The scorecard never grades. Each measure is a ratio of two lines on the same filing,
shown with the filing year, its source lines and the median across covered charities
in the same category.
"""

import datetime
import gzip
import json
import os
import re
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import WORK, ascii_upper, nice_name, read_json, write_json  # noqa: E402

CATEGORIES = {
    "A": ("arts-culture-humanities", "Arts, culture & humanities"),
    "B": ("education", "Education"),
    "C": ("environment", "Environment"),
    "D": ("animals", "Animal-related"),
    "E": ("health-care", "Health care"),
    "F": ("mental-health", "Mental health & crisis intervention"),
    "G": ("diseases-disorders", "Diseases, disorders & medical disciplines"),
    "H": ("medical-research", "Medical research"),
    "I": ("crime-legal", "Crime & legal-related"),
    "J": ("employment", "Employment"),
    "K": ("food-agriculture-nutrition", "Food, agriculture & nutrition"),
    "L": ("housing-shelter", "Housing & shelter"),
    "M": ("public-safety-disaster-relief", "Public safety, disaster preparedness & relief"),
    "N": ("recreation-sports", "Recreation & sports"),
    "O": ("youth-development", "Youth development"),
    "P": ("human-services", "Human services"),
    "Q": ("international", "International, foreign affairs & national security"),
    "R": ("civil-rights-advocacy", "Civil rights, social action & advocacy"),
    "S": ("community-improvement", "Community improvement & capacity building"),
    "T": ("philanthropy-grantmaking", "Philanthropy, voluntarism & grantmaking"),
    "U": ("science-technology", "Science & technology"),
    "V": ("social-science", "Social science"),
    "W": ("public-societal-benefit", "Public & societal benefit"),
    "X": ("religion-related", "Religion-related"),
    "Y": ("mutual-membership-benefit", "Mutual & membership benefit"),
    "Z": ("unclassified", "Unclassified"),
}

# BMF FOUNDATION codes for public charities (IRS EO BMF documentation).
CHARITY_TYPES = {
    "10": "Church", "11": "School", "12": "Hospital or medical research organization",
    "13": "Organization operated for a governmental college or university", "14": "Governmental unit",
    "15": "Publicly supported organization (170(b)(1)(A)(vi))", "16": "Publicly supported organization (509(a)(2))",
    "17": "Supporting organization (509(a)(3))", "18": "Organization that tests for public safety",
    "21": "Supporting organization, Type I", "22": "Supporting organization, Type II",
    "23": "Supporting organization, Type III functionally integrated", "24": "Supporting organization, Type III other",
}

YEAR_KEYS = ["rev_total", "contributions", "gov_grants", "program_rev", "investment", "exp_total", "exp_program",
             "exp_mgmt", "exp_fundraising", "net_assets", "assets", "liabilities", "employees", "n_over_100k"]
MIN_CONTRIB_FOR_COST = 250_000
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "PR": "Puerto Rico", "GU": "Guam", "VI": "U.S. Virgin Islands", "AS": "American Samoa", "MP": "Northern Mariana Islands",
}


def share(a, b):
    if a is None or not b or b <= 0:
        return None
    return a / b


def display_name(rec, cov):
    n1 = " ".join((rec.get("name") or "").split())
    n2 = " ".join((rec.get("name2") or "").split())
    dba = rec.get("dba") or ""
    u2 = ascii_upper(n2)
    if n2 and re.match(r"^(DBA|D/B/A|D B A)\b", u2):
        dba = dba or re.sub(r"^(DBA|D/B/A|D B A)\s*:?\s*", "", n2, flags=re.I)
    elif n2 and not re.match(r"^(C/O|C/0|CO |ATTN|%|IN CARE OF|AKA|FKA|F/K/A|A/K/A)", u2) and \
            re.match(r"^(OF|AND|&|FOR|THE|IN|AT|INC|INCORPORATED|FOUNDATION|FUND|SOCIETY|ASSOCIATION|CENTER|HOSPITAL|UNIVERSITY)\b", u2):
        n1 = f"{n1} {n2}"
    name = nice_name(n1 or cov.get("index_name") or cov.get("bmf_name", ""))
    name = re.sub(r"\s+(Inc|Incorporated|INC|INCORPORATED)\.?$", "", name).rstrip(" ,")
    return name, nice_name(dba) if dba else ""


def pick_years(rows):
    """{period key: row}: one return per tax period (the latest ReturnTs wins, so an amended
    return replaces the original). Keyed by period end, not tax year: a charity that changes
    its fiscal year files two returns for one tax year (a full year and a short period)."""
    by = {}
    for row in rows:
        rec = row["rec"]
        if not rec.get("tax_year"):
            continue
        key = (rec.get("period_end") or "")[:7].replace("-", "") or str(rec["tax_year"])
        k = (rec.get("return_ts") or "", row["oid"])
        if key not in by or k > by[key][0]:
            by[key] = (k, row)
    return {key: v[1] for key, v in by.items()}


def months(rec):
    """Length of the tax period in months (12 for a normal year), or None when unknown."""
    try:
        b = datetime.date.fromisoformat(rec.get("period_begin") or "")
        e = datetime.date.fromisoformat(rec.get("period_end") or "")
    except ValueError:
        return None
    return max(1, min(12, round(((e - b).days + 1) / 30.44)))


def functional_ok(r):
    t, p, m, f = r.get("exp_total"), r.get("exp_program"), r.get("exp_mgmt"), r.get("exp_fundraising")
    if not t or t <= 0 or p is None or m is None or f is None:
        return False
    return abs((p + m + f) - t) <= max(1000, 0.02 * t)


def metrics(r):
    m = {}
    t = r.get("exp_total")
    if functional_ok(r):
        m["program_share"] = r["exp_program"] / t
        m["mgmt_share"] = r["exp_mgmt"] / t
        m["fund_share"] = r["exp_fundraising"] / t
    c = r.get("contributions")
    if c is not None and c >= MIN_CONTRIB_FOR_COST and r.get("exp_fundraising") is not None:
        m["cost_per_dollar"] = r["exp_fundraising"] / c
    rev = r.get("rev_total")
    if rev and rev > 0:
        m["contrib_share"] = share(c, rev)
        m["gov_share"] = share(r.get("gov_grants") or 0, rev)
        m["program_rev_share"] = share(r.get("program_rev") or 0, rev)
    top = (r.get("comp") or [None])[0]
    if top:
        m["top_comp"] = top["total"]
        m["top_comp_title"] = top["title"]
        m["top_comp_share"] = share(top["total"], t)
    if r.get("n_over_100k") is not None:
        m["n_over_100k"] = r["n_over_100k"]
    if r.get("net_assets") is not None and t and t > 0:
        m["months_net_assets"] = r["net_assets"] / (t / 12)
    bv, bi = r.get("board_voting"), r.get("board_independent")
    if bv:
        m["board_voting"], m["board_independent"] = bv, bi
        m["independent_share"] = share(bi, bv)
    if rev is not None and t is not None:
        m["surplus"] = rev - t
    return {k: v for k, v in m.items() if v is not None}


MEDIAN_KEYS = ["program_share", "mgmt_share", "fund_share", "cost_per_dollar", "contrib_share", "gov_share",
               "program_rev_share", "top_comp", "top_comp_share", "n_over_100k", "months_net_assets", "independent_share"]


def medians(group):
    out = {"n": len(group)}
    for k in MEDIAN_KEYS:
        vals = [c["m"][k] for c in group if k in c["m"]]
        if len(vals) >= 10:
            out[k] = statistics.median(vals)
    return out


def load_rows(path):
    rows = defaultdict(list)
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            rows[row["rec"]["ein"]].append(row)
    return rows


def main():
    cov = read_json(os.path.join(WORK, "coverage.json.gz"))
    rows = load_rows(os.path.join(WORK, "filings.jsonl.gz"))
    fs_path = os.path.join(WORK, "first_seen.json.gz")
    first_seen = read_json(fs_path) if os.path.exists(fs_path) else {}
    today = datetime.date.today().isoformat()
    wf_path = os.path.join(WORK, "whofunds.json")
    whofunds = read_json(wf_path) if os.path.exists(wf_path) else {}
    rp_path = os.path.join(WORK, "replies.json")
    replies = read_json(rp_path) if os.path.exists(rp_path) else {}

    charities = []
    n_filings = 0
    for ein, meta in cov.items():
        years = pick_years(rows.get(ein, []))
        years = {k: row for k, row in years.items() if (row["rec"].get("exp_total") or 0) > 0 or (row["rec"].get("rev_total") or 0) > 0}
        if not years:
            continue
        hist = []
        for key in sorted(years):
            row = years[key]
            r = row["rec"]
            oid = row["oid"]
            first_seen.setdefault(oid, today)
            top = (r.get("comp") or [None])[0]
            hist.append({
                "key": key, "ty": r["tax_year"], "oid": oid, "src": row["src"], "period_end": r.get("period_end", ""),
                "months": months(r), "seen": first_seen[oid], "amended": r.get("amended", False),
                **{k: r.get(k) for k in YEAR_KEYS},
                "top_comp": top["total"] if top else None,
                "program_share": (r["exp_program"] / r["exp_total"]) if functional_ok(r) else None,
            })
        # The scorecard uses the latest full-year return; a short period after a fiscal-year
        # change still shows in the history and sources.
        full = [i for i, h in enumerate(hist) if not h["months"] or h["months"] >= 11]
        cur_i = full[-1] if full else len(hist) - 1
        cur = hist[cur_i]
        latest = years[cur["key"]]["rec"]
        name, dba = display_name(years[hist[-1]["key"]]["rec"], meta)
        n_filings += len(hist)
        major = (meta.get("ntee") or "Z")[:1].upper()
        if major not in CATEGORIES:
            major = "Z"
        state = latest.get("state") or meta.get("state") or ""
        rec = {
            "ein": ein, "name": name, "dba": dba, "legal_name": " ".join((latest.get("name") or "").split()),
            "city": nice_name(latest.get("city") or meta.get("city") or ""), "state": state,
            "ntee": meta.get("ntee", ""), "cat": major, "type": CHARITY_TYPES.get(meta.get("foundation", ""), ""),
            "deductible": meta.get("deductibility") == "1", "ruling": meta.get("ruling", ""),
            "website": latest.get("website") or meta.get("index_website") or "",
            "formation_year": latest.get("formation_year"), "group_return": latest.get("group_return", False),
            "mission": latest.get("mission", ""),
            "latest": {k: v for k, v in latest.items() if k not in ("name", "name2", "v")},
            "cur": cur, "years": hist, "m": metrics(latest),
        }
        if ein in whofunds:
            rec["whofunds"] = whofunds[ein]
        if ein in replies:
            rec["replies"] = replies[ein]
        charities.append(rec)

    # Context: medians by category (and overall), ranks by contributions.
    by_cat = defaultdict(list)
    for c in charities:
        by_cat[c["cat"]].append(c)
    overall = medians(charities)
    cat_meds = {k: medians(v) for k, v in by_cat.items()}
    for c in charities:
        cm = cat_meds[c["cat"]]
        c["peer"] = cm if cm["n"] >= 30 else {**overall, "scope": "all"}
    contrib = lambda c: (c["latest"].get("contributions") or 0)  # noqa: E731
    charities.sort(key=lambda c: (-contrib(c), -(c["latest"].get("rev_total") or 0), c["ein"]))
    cat_rank, st_rank = defaultdict(int), defaultdict(int)
    for i, c in enumerate(charities, 1):
        c["rank"] = i
        cat_rank[c["cat"]] += 1
        c["cat_rank"] = cat_rank[c["cat"]]
        st_rank[c["state"]] += 1
        c["state_rank"] = st_rank[c["state"]]

    stats = {
        "built": today, "charities": len(charities), "filings": n_filings,
        "with_functional": sum(1 for c in charities if "program_share" in c["m"]),
        "latest_years": {str(y): sum(1 for c in charities if c["cur"]["ty"] == y)
                         for y in sorted({c["cur"]["ty"] for c in charities})},
        "short_periods": sum(1 for c in charities for h in c["years"] if h["months"] and h["months"] < 11),
        "total_contributions": sum(contrib(c) for c in charities),
        "total_revenue": sum(c["latest"].get("rev_total") or 0 for c in charities),
        "total_expenses": sum(c["latest"].get("exp_total") or 0 for c in charities),
        "categories": {k: len(v) for k, v in sorted(by_cat.items())},
        "overall": overall, "category_medians": cat_meds,
        "newest_filing_seen": max(first_seen.values()) if first_seen else today,
    }
    fstats = os.path.join(WORK, "fetch_stats.json")
    if os.path.exists(fstats):
        stats["fetch_failed_share"] = read_json(fstats).get("failed_share", 0)
    write_json(os.path.join(WORK, "site_data.json.gz"), {"stats": stats, "charities": charities}, gz=True)
    write_json(os.path.join(WORK, "first_seen.json.gz"), first_seen, gz=True)
    with open(os.path.join(WORK, "stats.json"), "w") as f:
        json.dump({k: v for k, v in stats.items() if k not in ("category_medians",)}, f, indent=1, sort_keys=True)
    print(f"{len(charities)} charities, {n_filings} filings; {stats['with_functional']} with a functional-expense split",
          file=sys.stderr)


if __name__ == "__main__":
    main()
