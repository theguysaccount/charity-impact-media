"""HTML templates for the static site. Pure functions: data in, HTML string out.

Content rules enforced here (and tested in tests/test_render.py):
  * every figure names its filing year and links to its source (the in-page source list,
    which links to the filing itself);
  * no grades, ratings or verdicts: measures are shown with the category median, never
    labelled good or bad, and colors are categorical, never status colors;
  * people are never named; compensation is listed by role;
  * every charity page carries a visible correction link and the right-of-reply box.
"""

import datetime
import html
import json
import re
import urllib.parse

from common import PROPUBLICA_FILING, PROPUBLICA_ORG, clip, ein_dash

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
FORM_LINES = {
    "program_share": "Part IX 25(B) ÷ 25(A)",
    "mgmt_share": "Part IX 25(C) ÷ 25(A)",
    "fund_share": "Part IX 25(D) ÷ 25(A)",
    "cost_per_dollar": "Part IX 25(D) ÷ Part VIII 1h",
    "contrib_share": "Part VIII 1h ÷ 12",
    "gov_share": "Part VIII 1e ÷ 12",
    "program_rev_share": "Part VIII 2g ÷ 12",
    "top_comp": "Part VII-A, columns D–F",
    "top_comp_share": "Part VII-A ÷ Part IX 25(A)",
    "n_over_100k": "Part VII, line 2",
    "months_net_assets": "Part X 33(B) ÷ monthly expenses",
    "independent_share": "Part VI 1a–1b",
}


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


# --------------------------------------------------------------------------
# Number formatting
# --------------------------------------------------------------------------

def usd(v, short=True):
    if v is None:
        return "—"
    neg, a = v < 0, abs(v)
    if short and a >= 1e10:
        s = f"${a / 1e9:.1f}B"
    elif short and a >= 1e9:
        s = f"${a / 1e9:.2f}B"
    elif short and a >= 1e7:
        s = f"${a / 1e6:.0f}M"
    elif short and a >= 1e6:
        s = f"${a / 1e6:.1f}M"
    elif short and a >= 1e5:
        s = f"${a / 1e3:.0f}K"
    else:
        s = f"${a:,.0f}"
    return ("−" if neg else "") + s


def usd_words(v):
    if v is None:
        return "an unreported amount"
    neg, a = v < 0, abs(v)
    if a >= 1e9:
        s = f"${a / 1e9:.2f} billion"
    elif a >= 1e6:
        s = f"${a / 1e6:.1f} million"
    else:
        s = f"${a:,.0f}"
    return ("negative " if neg else "") + s


def pct(x, d=1):
    return "—" if x is None else f"{x * 100:.{d}f}%"


def num(v):
    return "—" if v is None else f"{v:,.0f}"


def cents(x):
    return f"${x / 100:,.2f}"


def hundred_split(parts):
    """Split $100 (10,000 cents) across shares so the parts add up exactly (largest remainder)."""
    total = sum(p for p in parts if p and p > 0)
    if total <= 0:
        return [0] * len(parts)
    raw = [(p if p and p > 0 else 0) / total * 10000 for p in parts]
    base = [int(r) for r in raw]
    rest = 10000 - sum(base)
    order = sorted(range(len(raw)), key=lambda i: -(raw[i] - base[i]))
    for i in order[:rest]:
        base[i] += 1
    return base


def period(y):
    """Readable fiscal period for one filing-year dict (needs ty and period_end)."""
    pe = y.get("period_end") or ""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", pe)
    if not m:
        return f"tax year {y['ty']}", str(y["ty"])
    yr, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if mo == 12:
        return f"calendar year {yr}", str(yr)
    return f"the fiscal year ending {MONTHS[mo - 1]} {d}, {yr}", f"FY{yr}"


# --------------------------------------------------------------------------
# Site context
# --------------------------------------------------------------------------

class Ctx:
    def __init__(self, base_url, repo, asset_v, support_url="", goatcounter="", built=None, n=0):
        u = urllib.parse.urlparse(base_url.rstrip("/"))
        self.origin = f"{u.scheme}://{u.netloc}"
        self.base = u.path.rstrip("/")  # e.g. /charity-impact-media
        self.base_url = self.origin + self.base
        self.repo = repo
        self.v = asset_v
        self.support_url = support_url
        self.goatcounter = goatcounter
        self.built = built or datetime.date.today().isoformat()
        self.n = n

    def u(self, path):
        return f"{self.base}{path}"

    def abs(self, path):
        return f"{self.origin}{self.base}{path}"

    def charity(self, ein):
        return self.u(f"/charity/{ein}/")

    def issue_url(self, template, title, **fields):
        q = {"template": template, "title": title, **fields}
        return f"https://github.com/{self.repo}/issues/new?" + urllib.parse.urlencode(q)


SITE_NAME = "Charity Impact Media"
TAGLINE = "Where the money goes, from each charity's own IRS filings"


def layout(ctx, *, title, description, path, body, og_image=None, jsonld=None, noindex=False, page="",
           og_type="website"):
    canonical = ctx.abs(path)
    og = og_image or ctx.abs(f"/assets/og.png?v={ctx.v}")
    ld = ""
    for block in (jsonld or []):
        ld += '<script type="application/ld+json">' + json.dumps(block, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"
    gc = f'<meta name="cim-gc" content="{esc(ctx.goatcounter)}">' if ctx.goatcounter else ""
    support = (f' · <a href="{esc(ctx.support_url)}" rel="noopener" data-ev="support">Support this project</a>'
               if ctx.support_url else "")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">{'<meta name="robots" content="noindex">' if noindex else ''}
<meta property="og:site_name" content="{SITE_NAME}"><meta property="og:type" content="{og_type}"><meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}"><meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(og)}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image"><meta name="theme-color" content="#1c5cab">
<link rel="icon" href="{ctx.u('/assets/favicon.svg')}" type="image/svg+xml">
<link rel="alternate" type="application/atom+xml" title="New filings" href="{ctx.u('/feed.xml')}">
<link rel="stylesheet" href="{ctx.u('/assets/app.css')}?v={ctx.v}">{gc}{ld}
</head><body data-page="{esc(page)}" data-base="{esc(ctx.base)}">
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="wrap"><a class="brand" href="{ctx.u('/')}">{SITE_NAME}</a>
<nav class="main" aria-label="Main"><a href="{ctx.u('/charities/')}">Charities A–Z</a><a href="{ctx.u('/category/')}">Causes</a><a href="{ctx.u('/compare/')}">Compare</a><a href="{ctx.u('/guides/')}">Guides</a><a href="{ctx.u('/method/')}">Method</a></nav>
<div class="search" role="search"><input type="search" placeholder="Search {ctx.n:,} charities or an EIN" aria-label="Search charities by name or EIN" autocomplete="off" data-search><ul hidden role="listbox"></ul></div>
</div></header>
<main id="main"><div class="wrap">{body}</div></main>
<footer class="bot"><div class="wrap">
<p><strong>{SITE_NAME}</strong>: {TAGLINE}. Figures are as each organization reported them on IRS Form 990, with the filing linked. No ratings or grades; not financial, legal or tax advice.</p>
<p><a href="{ctx.u('/method/')}">Method</a> · <a href="{ctx.u('/corrections/')}">Corrections &amp; right of reply</a> · <a href="{ctx.u('/data/')}">Data (CC0)</a> · <a href="{ctx.u('/updates/')}">New filings</a> · <a href="{ctx.u('/about/')}">About</a> · <a href="https://github.com/{esc(ctx.repo)}">Code</a>{support}</p>
<p>Sources: IRS e-file data via the <a href="https://990data.givingtuesday.org/">GivingTuesday 990 Data Lake</a> and <a href="https://www.irs.gov/charities-non-profits/form-990-series-downloads">IRS</a>; IRS EO Business Master File. Updated {esc(ctx.built)}.</p>
</div></footer>
<script src="{ctx.u('/assets/app.js')}?v={ctx.v}" defer></script>
</body></html>
"""


# --------------------------------------------------------------------------
# Pieces
# --------------------------------------------------------------------------

def stacked(parts, label):
    """A horizontal 100% bar plus legend. parts: [(name, value, css_class, note)]."""
    c = hundred_split([p[1] for p in parts])
    segs, rows = [], []
    for (name, value, cls, note), cc in zip(parts, c):
        if cc > 0:
            segs.append(f'<span class="{cls}" style="width:{cc / 100:.2f}%" title="{esc(name)}: {cents(cc)}"></span>')
        rows.append(f'<li><i class="{cls}" aria-hidden="true"></i><span>{esc(name)}</span><b>{note}</b></li>')
    return (f'<div class="bar" role="img" aria-label="{esc(label)}">{"".join(segs)}</div>'
            f'<ul class="legend">{"".join(rows)}</ul>')


def ref(ty, text):
    """A figure, linked to the citation for its filing year in the page's source list."""
    return f'<a href=#f{ty}>{text}</a>'


def trend_svg(years):
    """Revenue and expenses over the filed years: one dollar axis, two 2px lines, end labels."""
    pts = [y for y in years if y.get("rev_total") is not None and y.get("exp_total") is not None]
    if len(pts) < 2:
        return ""
    W, H, L, R, T, B = 640, 220, 56, 84, 14, 28
    vmax = max(max(p["rev_total"], p["exp_total"]) for p in pts)
    lo = min(0, min(min(p["rev_total"], p["exp_total"]) for p in pts))
    raw = ((vmax - lo) or 1) / 4
    mag = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 1
    step = next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)
    top = lo + step * 4
    n = len(pts)
    sx = lambda i: round(L + (W - L - R) * (i / (n - 1)))  # noqa: E731
    sy = lambda v: round(T + (H - T - B) * (1 - (v - lo) / ((top - lo) or 1)))  # noqa: E731
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Revenue and expenses by year; the values are in the table below">']
    k = 0
    while k <= 4:
        v = lo + step * k
        y = sy(v)
        out.append(f'<line class="gl" x1="{L}" x2="{W - R}" y1="{y}" y2="{y}"/><text class="e" x="{L - 8}" y="{y + 4}">{esc(usd(v))}</text>')
        k += 1
    for i, p in enumerate(pts):
        out.append(f'<text class="m" x="{sx(i)}" y="{H - 8}">{esc(period(p)[1])}</text>')
    for key, cls in (("rev_total", "1"), ("exp_total", "2")):
        d = "M" + " L".join(f"{sx(i)},{sy(p[key])}" for i, p in enumerate(pts))
        out.append(f'<path class="ln l{cls}" d="{d}"/><circle class="dot d{cls}" cx="{sx(n - 1)}" cy="{sy(pts[-1][key])}" r="4"/>')
    ra, ea = sy(pts[-1]["rev_total"]), sy(pts[-1]["exp_total"])
    if abs(ra - ea) < 14:
        ra, ea = (ra - 7, ea + 7) if ra <= ea else (ra + 7, ea - 7)
    out.append(f'<text x="{W - R + 8}" y="{ra + 4}">{esc(usd(pts[-1]["rev_total"]))}</text><text x="{W - R + 8}" y="{ea + 4}">{esc(usd(pts[-1]["exp_total"]))}</text>')
    out.append(f'<line class="xh" x1="0" x2="0" y1="{T}" y2="{H - B}"/>')
    for i, p in enumerate(pts):
        a = L if i == 0 else (sx(i - 1) + sx(i)) // 2
        b = W - R if i == n - 1 else (sx(i) + sx(i + 1)) // 2
        out.append(f'<rect class="hit" x="{a}" y="{T}" width="{b - a}" height="{H - T - B}" tabindex="0" data-x="{sx(i)}" '
                   f'data-t="{esc(period(p)[1])}" data-v="{esc(usd(p["rev_total"]))}|{esc(usd(p["exp_total"]))}"/>')
    out.append("</svg>")
    return "".join(out)


def mini_bar(m):
    if "program_share" not in m:
        return ""
    c = hundred_split([m["program_share"], m["mgmt_share"], m["fund_share"]])
    return ('<div class="mini" aria-hidden="true">' + "".join(
        f'<span class="c{i + 1}" style="width:{x / 100:.2f}%"></span>' for i, x in enumerate(c) if x > 0) + "</div>")


# --------------------------------------------------------------------------
# Charity page
# --------------------------------------------------------------------------

def narrative(c):
    """A short factual summary, generated from the latest filing (no adjectives about quality)."""
    L, m, y = c["latest"], c["m"], c["years"][-1]
    ph, _ = period(y)
    s = [f"{c['name']} reported {usd_words(L.get('rev_total'))} in revenue and {usd_words(L.get('exp_total'))} in expenses for {ph}."]
    if "program_share" in m:
        p, mg, f = hundred_split([m["program_share"], m["mgmt_share"], m["fund_share"]])
        s.append(f"Of every $100 it spent, {cents(p)} went to program services, {cents(mg)} to management and general costs and {cents(f)} to fundraising.")
    rev = L.get("rev_total") or 0
    if rev > 0:
        srcs = [("contributions and grants", L.get("contributions") or 0), ("program service revenue such as fees, sales and contracts", L.get("program_rev") or 0),
                ("investment income", L.get("investment") or 0)]
        name, val = max(srcs, key=lambda t: t[1])
        if val > 0:
            s.append(f"Its largest source of revenue was {name}: {pct(val / rev)} of the total.")
        g = L.get("gov_grants") or 0
        if g > 0.05 * rev:
            s.append(f"Government grants made up {pct(g / rev)}.")
    if "top_comp" in m:
        role = f" ({m['top_comp_title']})" if m.get("top_comp_title") else ""
        s.append(f"The highest compensation it reported for one person was {usd(m['top_comp'], short=False)}{role}.")
    if m.get("n_over_100k"):
        n = m["n_over_100k"]
        s.append(f"{n:,} {'person' if n == 1 else 'people'} received more than $100,000 in reportable compensation.")
    ys = [x for x in c["years"] if x.get("rev_total")]
    if len(ys) >= 4 and ys[0]["rev_total"] > 0:
        ch = ys[-1]["rev_total"] / ys[0]["rev_total"] - 1
        verb = "rose" if ch >= 0 else "fell"
        s.append(f"Revenue {verb} {pct(abs(ch), 0)} between {period(ys[0])[1]} and {period(ys[-1])[1]}.")
    return " ".join(s)


def faq(c):
    L, m, y = c["latest"], c["m"], c["years"][-1]
    ph, lab = period(y)
    n = c["name"]
    qa = []
    if "program_share" in m:
        qa.append((f"How much of {n}'s spending goes to programs?",
                   f"In {ph}, {n} reported that {pct(m['program_share'])} of its {usd_words(L.get('exp_total'))} in expenses went to program services, "
                   f"{pct(m['mgmt_share'])} to management and general and {pct(m['fund_share'])} to fundraising (Form 990, Part IX)."))
    if "top_comp" in m:
        qa.append((f"How much does {n} pay its top executive?",
                   f"The largest total compensation {n} reported for one person in {ph} was {usd(m['top_comp'], short=False)}"
                   + (f", for the role of {m['top_comp_title']}" if m.get("top_comp_title") else "") + " (Form 990, Part VII, including compensation from related organizations and other compensation)."))
    if L.get("rev_total"):
        qa.append((f"Where does {n} get its money?",
                   f"Of {usd_words(L['rev_total'])} in revenue in {ph}, {pct((L.get('contributions') or 0) / L['rev_total'])} came from contributions and grants"
                   + (f" (including {pct(L['gov_grants'] / L['rev_total'])} from government grants)" if (L.get("gov_grants") or 0) > 0 else "")
                   + f" and {pct((L.get('program_rev') or 0) / L['rev_total'])} from program service revenue (Form 990, Part VIII)."))
    years = ", ".join(str(x["ty"]) for x in c["years"])
    qa.append((f"Is {n} a registered charity?",
               f"The IRS lists EIN {ein_dash(c['ein'])} as a 501(c)(3) organization"
               + (f" ({c['type'].lower()})" if c.get("type") else "")
               + (", and its records show contributions as tax-deductible" if c.get("deductible") else "")
               + f". Form 990 filings on record here cover tax years {years}. A filing shows what the organization reported; it doesn't by itself show whether a program works."))
    return qa


def scorecard_rows(c):
    m, peer = c["m"], c.get("peer", {})
    ty = c["years"][-1]["ty"]
    lab = period(c["years"][-1])[1]
    scope = "all covered charities" if peer.get("scope") == "all" else "this category"
    rows = [
        ("Program services", "program_share", pct), ("Management & general", "mgmt_share", pct),
        ("Fundraising", "fund_share", pct),
        ("Fundraising cost per $1 of contributions", "cost_per_dollar", lambda x: f"${x:.2f}"),
        ("Contributions & grants share of revenue", "contrib_share", pct),
        ("Government grants share of revenue", "gov_share", pct),
        ("Program service revenue share", "program_rev_share", pct),
        ("Highest reported compensation", "top_comp", lambda x: usd(x, short=False)),
        ("Highest compensation as share of expenses", "top_comp_share", lambda x: pct(x, 2)),
        ("People paid over $100,000", "n_over_100k", num),
        ("Net assets, in months of expenses", "months_net_assets", lambda x: f"{x:,.1f}"),
        ("Independent voting board members", "independent_share", pct),
    ]
    out = []
    for label, key, fmt in rows:
        if key not in m:
            val = "Not reported"
        else:
            val = ref(ty, esc(fmt(m[key])))
            if key == "independent_share":
                val = ref(ty, esc(f"{m.get('board_independent') or 0} of {m['board_voting']}"))
        med = esc(fmt(peer[key])) if key in peer else "—"
        out.append(f'<tr><td>{esc(label)}<br><span class="src">{esc(FORM_LINES[key])}</span></td><td class="r">{val}</td><td class="r">{med}</td></tr>')
    return (f'<table class="tbl"><caption class="cap" style="caption-side:top;text-align:left">{esc(lab)} filing. '
            f'Median across {peer.get("n", 0):,} covered charities in {esc(scope)}, from their latest filings.</caption>'
            f'<thead><tr><th scope="col">Measure</th><th scope="col" class="r">{esc(lab)}</th><th scope="col" class="r">Median</th></tr></thead>'
            f'<tbody>{"".join(out)}</tbody></table>')


GOV_QUESTIONS = [
    ("audited", "Audited financial statements", "XII 2b"),
    ("conflict_policy", "Conflict-of-interest policy", "VI 12a"),
    ("whistleblower", "Whistleblower policy", "VI 13"),
    ("doc_retention", "Document retention policy", "VI 14"),
    ("ceo_comp_process", "Independent process for top executive pay", "VI 15a"),
    ("board_saw_990", "Board given the 990 before filing", "VI 11a"),
    ("family_business", "Family or business ties among insiders", "VI 2"),
    ("diversion", "Aware of a significant diversion of assets", "VI 5"),
    ("excess_benefit", "Excess benefit transaction with an insider", "IV 25a"),
    ("loans_insiders", "Loans to or from insiders outstanding", "IV 26"),
    ("lobbying", "Lobbying, or a 501(h) election in effect", "IV 4"),
    ("prof_fundraisers", "Over $15,000 of professional fundraising services", "IV 18"),
    ("foreign", "Over $10,000 of activity outside the U.S.", "IV 14b"),
]


def charity_page(ctx, c, similar, og_image=None, slim=False):
    """slim=True drops the trend chart, contractors, similar list and FAQ (used only to fit the Pages size budget)."""
    L, m, years = c["latest"], c["m"], c["years"]
    y = years[-1]
    ty = y["ty"]
    ph, lab = period(y)
    ein = c["ein"]
    name = c["name"]
    url = ctx.charity(ein)
    filing_url = PROPUBLICA_FILING.format(ein=ein, object_id=y["oid"])
    cat_slug, cat_label = c["cat_slug"], c["cat_label"]

    head = (f'<p class="crumbs"><a href="{ctx.u("/")}">Home</a> › <a href="{ctx.u(f"/category/{cat_slug}/")}">{esc(cat_label)}</a></p>'
            f'<h1>{esc(name)}</h1>'
            + (f'<p class="sub">Also known as {esc(c["dba"])}</p>' if c.get("dba") else "")
            + f'<p class="meta">{esc(c["city"])}{", " if c["city"] else ""}{esc(c["state"])} · EIN {ein_dash(ein)} · 501(c)(3)'
            + (f' · {esc(c["type"])}' if c.get("type") else "")
            + f'<br>Latest filing: Form 990 for {esc(ph)} (tax year {ty}) · <a href="{esc(filing_url)}" data-ev="source_open">View the filing</a>'
            + f' · <a href="#reply">Correct or respond</a></p>')

    brief = f'<p class="brief">{esc(narrative(c))} <a href=#f{ty}>Source: Form 990, {esc(lab)}</a>.</p>'

    # Where $100 went / came from.
    spend = ""
    if "program_share" in m:
        p, mg, f = hundred_split([m["program_share"], m["mgmt_share"], m["fund_share"]])
        peer = c.get("peer", {})
        ctx_line = ""
        if "program_share" in peer:
            scope = "all covered charities" if peer.get("scope") == "all" else f"covered {cat_label.lower()} charities"
            pp, pm, pf = hundred_split([peer["program_share"], peer.get("mgmt_share", 0), peer.get("fund_share", 0)])
            ctx_line = f'<p class="ctx">For context, the median across {peer["n"]:,} {esc(scope)}: {cents(pp)} programs, {cents(pm)} management, {cents(pf)} fundraising (medians computed separately, so they may not sum to $100).</p>'
        spend = (f'<section class="card" aria-labelledby="spend"><h2 id="spend">Where $100 of spending went</h2>'
                 f'<span class="cap">{esc(ph[0].upper() + ph[1:])} · Form 990, Part IX, line 25 · total expenses {ref(ty, esc(usd(L.get("exp_total"))))}</span>'
                 + stacked([("Program services", m["program_share"], "c1", ref(ty, cents(p)) + f' <span class="src">{ref(ty, esc(usd(L.get("exp_program"))))}</span>'),
                            ("Management & general", m["mgmt_share"], "c2", ref(ty, cents(mg)) + f' <span class="src">{ref(ty, esc(usd(L.get("exp_mgmt"))))}</span>'),
                            ("Fundraising", m["fund_share"], "c3", ref(ty, cents(f)) + f' <span class="src">{ref(ty, esc(usd(L.get("exp_fundraising"))))}</span>')],
                           f"Of every $100 spent: {cents(p)} programs, {cents(mg)} management and general, {cents(f)} fundraising")
                 + ctx_line + "</section>")
    else:
        spend = ('<section class="card"><h2>Where $100 of spending went</h2><p>This filing does not split expenses by function '
                 f'(Part IX columns B–D), so there is no breakdown for {esc(lab)}.</p></section>')

    came = ""
    rev = L.get("rev_total") or 0
    if rev > 0:
        contrib = L.get("contributions") or 0
        gov = min(L.get("gov_grants") or 0, contrib)
        prog = L.get("program_rev") or 0
        inv = L.get("investment") or 0
        other = rev - contrib - prog - inv
        parts = [("Contributions & grants (non-government)", contrib - gov, "c1"), ("Government grants", gov, "c2"),
                 ("Program service revenue", prog, "c3"), ("Investment income", inv, "c4"), ("Other revenue", other, "c5")]
        pos = [p for p in parts if p[1] > 0]
        shares = hundred_split([p[1] for p in pos])
        legend = []
        for (nm, val, cls), cc in zip(pos, shares):
            legend.append((nm, val, cls, ref(ty, cents(cc)) + f' <span class="src">{ref(ty, esc(usd(val)))}</span>'))
        neg = [p for p in parts if p[1] < 0]
        negnote = "".join(f'<p class="ctx">{esc(nm)} was negative: {ref(ty, esc(usd(val)))}. The bar shows the positive sources only.</p>' for nm, val, _ in neg)
        came = (f'<section class="card" aria-labelledby="came"><h2 id="came">Where $100 of revenue came from</h2>'
                f'<span class="cap">{esc(ph[0].upper() + ph[1:])} · Form 990, Part VIII · total revenue {ref(ty, esc(usd(rev)))}</span>'
                + stacked(legend, "Revenue sources per $100") + negnote + "</section>")

    score = (f'<section class="card" aria-labelledby="score"><h2 id="score">The 990 scorecard <small>· same measures for every charity, no grades</small></h2>'
             f'<div class="scroll">{scorecard_rows(c)}</div>'
             f'<p class="ctx">A median is context, not a target: hospitals, universities, food banks and grantmakers spend in very different ways. '
             f'<a href="{ctx.u("/guides/program-expense-ratio/")}">What these measures can and can\'t tell you</a>.</p></section>')

    pay = ""
    comp = L.get("comp") or []
    if comp:
        rows = "".join(
            f'<tr><td>{esc(p["title"] or "Listed person")}<br><span class="src">{esc(role_words(p["roles"]))}{", " + esc(p["hours"]) + " hrs/week" if p.get("hours") else ""}</span></td>'
            f'<td class="r">{ref(ty, esc(usd(p["org"], short=False)))}</td><td class="r">{ref(ty, esc(usd(p["related"], short=False)))}</td>'
            f'<td class="r">{ref(ty, esc(usd(p["other"], short=False)))}</td><td class="r"><b>{ref(ty, esc(usd(p["total"], short=False)))}</b></td></tr>'
            for p in comp[:8])
        extra = ""
        if m.get("n_over_100k") is not None:
            extra += f'<p class="ctx">{ref(ty, esc(num(m["n_over_100k"])))} people received more than $100,000 in reportable compensation from {esc(name)} (Part VII, line 2).'
            if L.get("officer_comp") is not None:
                extra += f' Compensation of current officers, directors and key employees totaled {ref(ty, esc(usd(L["officer_comp"])))} (Part IX, line 5).'
            extra += "</p>"
        pay = (f'<section class="card" aria-labelledby="pay"><h2 id="pay">Highest reported compensation</h2>'
               f'<span class="cap">{esc(lab)} · Form 990, Part VII, Section A · roles as filed; names are in the filing, not here</span>'
               f'<div class="scroll"><table class="tbl"><thead><tr><th scope="col">Role</th><th scope="col" class="r">From this org</th><th scope="col" class="r">From related orgs</th><th scope="col" class="r">Other</th><th scope="col" class="r">Total</th></tr></thead><tbody>{rows}</tbody></table></div>'
               f'{extra}</section>')

    progs = ""
    pl = L.get("programs") or []
    if pl:
        pt = L.get("programs_total_exp") or sum(p.get("exp") or 0 for p in pl) or 0
        items = []
        for p in pl:
            sh = f" · {ref(ty, esc(pct(p['exp'] / pt)))} of program spending" if pt and p.get("exp") else ""
            items.append(f'<div class="prog"><strong>{ref(ty, esc(usd(p.get("exp"))))}</strong> <span class="src">expenses{sh}'
                         + (f' · grants {ref(ty, esc(usd(p["grants"])))}' if p.get("grants") else "")
                         + (f' · revenue {ref(ty, esc(usd(p["rev"])))}' if p.get("rev") else "")
                         + f'</span><p>{esc(clip(sentence_case(useful_text(p.get("desc")) or "No description in Part III; see the filing."), 600))}</p></div>')
        oth = L.get("programs_other_exp")
        if oth:
            items.append(f'<div class="prog"><strong>{ref(ty, esc(usd(oth)))}</strong> <span class="src">all other programs (line 4d)</span></div>')
        progs = (f'<section class="card" aria-labelledby="progs"><h2 id="progs">What the money paid for, in its own words</h2>'
                 f'<span class="cap">{esc(lab)} · Form 990, Part III · the three largest programs by expense</span>{"".join(items)}</section>')

    hist_rows = []
    for x in reversed(years):
        _, xl = period(x)
        fu = PROPUBLICA_FILING.format(ein=ein, object_id=x["oid"])
        hist_rows.append(f'<tr><td><a href="{esc(fu)}">{esc(xl)}</a>{" (amended)" if x.get("amended") else ""} <a href=#f{x["ty"]} aria-label="source details">ⓘ</a>'
                         f'<td class=r>{esc(usd(x.get("rev_total")))}<td class=r>{esc(usd(x.get("exp_total")))}'
                         f'<td class=r>{esc(pct(x.get("program_share")))}<td class=r>{esc(usd(x.get("net_assets")))}'
                         f'<td class=r>{esc(usd(x.get("top_comp"), short=False))}</tr>')
    chart = "" if slim else trend_svg(years)
    trend = (f'<section class="card" aria-labelledby="trend"><h2 id="trend">{len(years)} years of filings</h2>'
             f'<span class="cap">Form 990, Parts I, VII, IX and X · each row is that year\'s own filing, linked</span>'
             + (f'<div class="keyrow"><span><i class="c1"></i>Revenue</span><span><i class="c2"></i>Expenses</span></div><div class="chart">{chart}</div>' if chart else "")
             + f'<div class="scroll"><table class="tbl"><thead><tr><th scope="col">Filing</th><th scope="col" class="r">Revenue</th><th scope="col" class="r">Expenses</th>'
               f'<th scope="col" class="r">Programs</th><th scope="col" class="r">Net assets</th><th scope="col" class="r">Top pay</th></tr></thead><tbody>{"".join(hist_rows)}</tbody></table></div></section>')

    f = L.get("f") or {}
    gov_items = []
    for key, q, line in GOV_QUESTIONS:
        v = f.get(key)
        ans = "Not answered" if v is None else ("Yes" if v else "No")
        gov_items.append(f'<li><span>{esc(q)} <span class="src">Part {esc(line)}</span></span><span>{ref(ty, ans)}</span></li>')
    bv, bi = L.get("board_voting"), L.get("board_independent")
    if bv:
        gov_items.insert(0, f'<li><span>Voting board members, and how many are independent <span class="src">Part VI, lines 1a–1b</span></span><span>{ref(ty, esc(f"{bv:,} · {bi or 0:,} independent"))}</span></li>')
    if L.get("employees") is not None:
        gov_items.append(f'<li><span>Employees <span class="src">Part I, line 5</span></span><span>{ref(ty, esc(num(L["employees"])))}</span></li>')
    if L.get("volunteers"):
        gov_items.append(f'<li><span>Volunteers <span class="src">Part I, line 6</span></span><span>{ref(ty, esc(num(L["volunteers"])))}</span></li>')
    gov = (f'<section class="card" aria-labelledby="gov"><h2 id="gov">Governance answers, as filed</h2>'
           f'<span class="cap">{esc(lab)} · the organization\'s own yes/no answers; explanations, if any, are in Schedule O of the filing · <a href="{ctx.u("/guides/governance-questions/")}">what each means</a></span>'
           f'<ul class="facts">{"".join(gov_items)}</ul></section>')

    cons = ""
    if L.get("contractors") and not slim:
        rows = "".join(f'<tr><td>{esc(x["name"])}<br><span class="src">{esc(sentence_case(x["services"]))}</span></td><td class="r">{ref(ty, esc(usd(x["amount"], short=False)))}</td></tr>'
                       for x in L["contractors"])
        more = f' {ref(ty, esc(num(L["n_contractors_100k"])))} contractors were paid more than $100,000 in all.' if L.get("n_contractors_100k") else ""
        cons = (f'<section class="card" aria-labelledby="cons"><h2 id="cons">Largest outside contractors</h2>'
                f'<span class="cap">{esc(lab)} · Form 990, Part VII, Section B · businesses only{esc("")}</span>'
                f'<div class="scroll"><table class="tbl"><tbody>{rows}</tbody></table></div><p class="ctx">Individuals listed as contractors are left out.{more}</p></section>')

    wf = ""
    if c.get("whofunds"):
        w = c["whofunds"]
        wf = (f'<section class="card" aria-labelledby="wf"><h2 id="wf">Private foundation grants it received</h2>'
              f'<p>{w["n"]:,} private foundation{"s" if w["n"] != 1 else ""} reported grants to {esc(name)} totaling {esc(usd(w["total"]))} on their tax year {w["year"]} Form 990-PF returns. '
              f'<a href="{esc(w["url"])}" data-ev="whofunds_open">See which foundations, on WHOFUNDS</a>.</p>'
              f'<p class="src">Source: WHOFUNDS open grant graph, matched from Form 990-PF Part XV.</p></section>')

    replies = c.get("replies") or []
    reply_list = ""
    if replies:
        reply_list = ('<p><strong>On file:</strong> ' + ", ".join(
            f'<a href="{esc(r["url"])}">{"response" if r["kind"] == "reply" else "correction"} #{r["n"]}</a> ({esc(r["state"])})'
            for r in replies[:12]) + '. Posted publicly on GitHub by whoever submitted them; we link them without editing.</p>')
    reply = (f'<section class="card reply" id="reply" aria-labelledby="replyh"><h2 id="replyh">Correct a figure or respond</h2>'
             f'<p>Every number above is copied from {esc(name)}\'s own Form 990. If one doesn\'t match the filing, that\'s our error and we\'ll fix it. '
             f'If you work for {esc(name)}, you can publish a response that is linked from this page.</p>{reply_list}'
             f'<div class="btns"><a class="btn" href="{esc(ctx.issue_url("correction.yml", f"Correction: {name} ({ein_dash(ein)})", ein=ein_dash(ein), page=ctx.abs(f"/charity/{ein}/")))}" data-ev="correction_open">Report a correction</a>'
             f'<a class="btn" href="{esc(ctx.issue_url("reply.yml", f"Reply: {name} ({ein_dash(ein)})", ein=ein_dash(ein), page=ctx.abs(f"/charity/{ein}/")))}" data-ev="reply_open">Respond as {esc(short(name))}</a>'
             f'<a class="btn" href="{ctx.u("/corrections/")}">How this works</a></div></section>')

    share_text = narrative_share(c)
    embed = (f'<iframe src="{esc(ctx.abs(f"/embed/?ein={ein}"))}" title="Where the money goes: {esc(name)}" width="100%" height="330" '
             f'style="border:0;max-width:440px" loading="lazy"></iframe>')
    share = (f'<section class="card share" aria-labelledby="shareh"><h2 id="shareh">Share or embed this breakdown</h2>'
             f'<p class="src">{esc(share_text)}</p>'
             f'<div class="btns" data-share data-title="{esc(name)}: where the money goes" data-text="{esc(share_text)}" data-url="{esc(ctx.abs(f"/charity/{ein}/"))}">'
             f'<button class="btn primary" type="button" data-act="share">Share</button><button class="btn" type="button" data-act="copy">Copy link</button>'
             f'<a class="btn" data-act="x" href="#" rel="noopener">X</a><a class="btn" data-act="linkedin" href="#" rel="noopener">LinkedIn</a>'
             f'<a class="btn" data-act="facebook" href="#" rel="noopener">Facebook</a><a class="btn" data-act="email" href="#">Email</a>'
             f'<a class="btn" href="{ctx.u(f"/compare/?e={ein}")}" data-ev="compare_open">Compare with another charity</a></div>'
             f'<h3>Embed on your site</h3><textarea class="embed" readonly aria-label="Embed code" data-ev="embed_copy">{esc(embed)}</textarea></section>')

    sim = ""
    if similar and not slim:
        sim = ('<section class="card" aria-labelledby="sim"><h2 id="sim">Similar-sized charities in this cause</h2><ul class="list">' + "".join(
            f'<li><a class="t" href="{ctx.charity(s["ein"])}">{esc(s["name"])}</a><div class="s">{esc(s["city"])}, {esc(s["state"])} · revenue {esc(usd(s["latest"].get("rev_total")))}'
            + (f' · programs {pct(s["m"]["program_share"])}' if "program_share" in s["m"] else "") + f' · {esc(period(s["years"][-1])[1])}</div></li>'
            for s in similar) + f'</ul><p class="ctx"><a href="{ctx.u(f"/category/{cat_slug}/")}">All {esc(cat_label.lower())} charities</a> · '
            f'<a href="{ctx.u("/state/" + c["state"].lower() + "/")}">Largest charities in {esc(c.get("state_name") or c["state"])}</a></p></section>')

    qa = faq(c)
    faq_html = "" if slim else ('<section class="card" aria-labelledby="faqh"><h2 id="faqh">Questions people ask</h2>' + "".join(
        f'<h3>{esc(q)}</h3><p>{esc(a)}</p>' for q, a in qa) + "</section>")

    src_items = []
    for x in reversed(years):
        xph, xl = period(x)
        fu = PROPUBLICA_FILING.format(ein=ein, object_id=x["oid"])
        raw = (f' · <a href="https://gt990datalake-rawdata.s3.amazonaws.com/EfileData/XmlFiles/{x["oid"]}_public.xml">XML</a>'
               if x.get("src") == "gt" and x is years[-1] else "")
        src_items.append(f'<li id="f{x["ty"]}"><b>{esc(xl)}</b>: Form 990 for {esc(xph)}{" (amended)" if x.get("amended") else ""}, '
                         f'object {esc(x["oid"])} · <a href="{esc(fu)}">read the filing</a>{raw}</li>')
    sources = (f'<section class="card" aria-labelledby="srcs"><h2 id="srcs">Sources</h2><ul class="list">{"".join(src_items)}</ul>'
               f'<p class="ctx">All filings for EIN {ein_dash(ein)}: <a href="{esc(PROPUBLICA_ORG.format(ein=ein))}">ProPublica Nonprofit Explorer</a> · '
               f'<a href="https://apps.irs.gov/app/eos/">IRS Tax Exempt Organization Search</a>. '
               f'Figures are as the organization reported them; we have not audited them.</p></section>')

    support = ""
    if ctx.support_url:
        support = (f'<section class="card support"><p>These breakdowns are free and ad-free. '
                   f'<a href="{esc(ctx.support_url)}" rel="noopener" data-ev="support">Help keep them that way</a>.</p></section>')

    body = (head + brief + '<div class="grid2">' + spend + came + "</div>" + score + progs + pay + trend
            + '<div class="grid2">' + gov + (cons or wf or "") + "</div>" + (wf if cons and wf else "") + reply + share + sim + faq_html + sources + support)

    desc = description_for(c)
    title = f"{name}: where the money goes ({lab} Form 990)"
    ld = [{
        "@context": "https://schema.org", "@type": "NGO", "name": name, **({"alternateName": c["dba"]} if c.get("dba") else {}),
        "taxID": ein_dash(ein), "nonprofitStatus": "Nonprofit501c3", "url": normalize_url(c.get("website")) or ctx.abs(url[len(ctx.base):]),
        "address": {"@type": "PostalAddress", "addressLocality": c["city"], "addressRegion": c["state"], "addressCountry": "US"},
        **({"foundingDate": str(c["formation_year"])} if c.get("formation_year") else {}),
        **({"description": sentence_case(useful_text(c["mission"]))} if useful_text(c.get("mission")) else {}),
        **({"numberOfEmployees": {"@type": "QuantitativeValue", "value": L["employees"]}} if L.get("employees") else {}),
    }, {
        "@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": ctx.abs("/")},
            {"@type": "ListItem", "position": 2, "name": cat_label, "item": ctx.abs(f"/category/{cat_slug}/")},
            {"@type": "ListItem", "position": 3, "name": name, "item": ctx.abs(f"/charity/{ein}/")}]
    }]
    return layout(ctx, title=title, description=desc, path=f"/charity/{ein}/", body=body, og_image=og_image, jsonld=ld,
                  page="charity", og_type="article")


def description_for(c):
    m, y = c["m"], c["years"][-1]
    _, lab = period(y)
    bits = []
    if "program_share" in m:
        p, mg, f = hundred_split([m["program_share"], m["mgmt_share"], m["fund_share"]])
        bits.append(f"Of every $100 spent in {lab}: {cents(p)} programs, {cents(mg)} management, {cents(f)} fundraising.")
    bits.append(f"Revenue {usd(c['latest'].get('rev_total'))}.")
    if "top_comp" in m:
        bits.append(f"Top pay {usd(m['top_comp'], short=False)}" + (f" ({m['top_comp_title']})." if m.get("top_comp_title") else "."))
    bits.append(f"{len(c['years'])} years of IRS Form 990 data, sourced.")
    return " ".join(bits)[:300]


def narrative_share(c):
    m, y = c["m"], c["years"][-1]
    _, lab = period(y)
    if "program_share" in m:
        p, _, _ = hundred_split([m["program_share"], m["mgmt_share"], m["fund_share"]])
        return f"Of every $100 {c['name']} spent in {lab}, {cents(p)} went to programs. The full breakdown, from its IRS Form 990:"
    return f"Where {c['name']}'s money comes from and goes, from its IRS Form 990:"


def role_words(roles):
    words = {"D": "director/trustee", "O": "officer", "K": "key employee", "H": "highest compensated employee", "F": "former"}
    out = []
    for ch in roles or "":
        w = words.get(ch)
        if w and w not in out:
            out.append(w)
    return ", ".join(out).capitalize() if out else "Listed in Part VII"


def short(name, n=34):
    return name if len(name) <= n else name[:n].rsplit(" ", 1)[0] + "…"


def sentence_case(s):
    """Filed text is often all caps; make it readable without changing its words."""
    s = " ".join((s or "").split())
    if not s or re.search(r"[a-z]", s):
        return s
    t = s.lower()
    t = re.sub(r"(^|[.!?]\s+)([a-z])", lambda mm: mm.group(1) + mm.group(2).upper(), t)
    t = re.sub(r"\bi\b", "I", t)
    t = re.sub(r"\b(u\.?s\.?a?|usa|covid|hiv|aids|ymca|ywca|unicef|fy\d\d|fy|ceo|cfo|irs|stem|lgbtq?\+?|nfl|nba)\b",
               lambda mm: mm.group(0).upper(), t)
    return t


def normalize_url(u):
    u = (u or "").strip()
    if not u or u.upper() in ("N/A", "NONE", "NA", "0"):
        return ""
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u.lstrip("/")
    u = u.lower() if u.isupper() else u
    return u if re.match(r"^https?://[A-Za-z0-9.-]+\.[A-Za-z]{2,}", u) else ""


def useful_text(t):
    """Filed text without pointers elsewhere ("Food procurement - see Schedule O" -> "Food procurement")."""
    t = " ".join((t or "").split())
    t = re.sub(r"(?i)[\s,;:.(-]*\(?\s*(see|refer to|per|described (in|on))\s+(the\s+)?(attached\s+)?(schedule|sch\.?)\s*o\b.*$", "", t).strip(" -,;:.")
    if not t or re.fullmatch(r"(?i)(schedule|sch\.?)\s*o|n/?a|none|see attached|attached", t):
        return ""
    return t
