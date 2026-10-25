"""Site-wide pages: home, causes, states, A-Z, compare, embed, method, corrections, data,
updates, guides and 404. Same content rules as render.py."""

import re

from common import ein_dash
from render import (SITE_NAME, cents, esc, hundred_split, layout, mini_bar, pct, period, usd)


def row_list(ctx, items, show_rank=True):
    out = []
    for c in items:
        m = c["m"]
        bits = [f'{esc(c["city"])}, {esc(c["state"])}', f'contributions {esc(usd(c["latest"].get("contributions")))}',
                f'revenue {esc(usd(c["latest"].get("rev_total")))}']
        if "program_share" in m:
            p, mg, f = hundred_split([m["program_share"], m["mgmt_share"], m["fund_share"]])
            bits.append(f"of $100 spent: {cents(p)} programs · {cents(mg)} management · {cents(f)} fundraising")
        bits.append(esc(period(c["years"][-1])[1]))
        out.append(f'<li><a class="t" href="{ctx.charity(c["ein"])}">{esc(c["name"])}</a>'
                   f'<div class="s">{" · ".join(bits)}</div>{mini_bar(m)}</li>')
    return f'<ul class="list">{"".join(out)}</ul>'


def table(ctx, items, cols):
    head = "".join(f'<th scope="col"{" class=r" if r else ""}>{esc(h)}</th>' for h, _, r in cols)
    rows = []
    for c in items:
        cells = []
        for _, fn, r in cols:
            cells.append(f'<td{" class=r" if r else ""}>{fn(c)}</td>')
        rows.append(f'<tr>{"".join(cells)}</tr>')
    return f'<div class="scroll"><table class="tbl"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def name_cell(ctx):
    return lambda c: f'<a href="{ctx.charity(c["ein"])}">{esc(c["name"])}</a><br><span class="src">{esc(c["city"])}, {esc(c["state"])} · {esc(period(c["years"][-1])[1])}</span>'


def std_cols(ctx):
    return [
        ("Charity", name_cell(ctx), False),
        ("Contributions", lambda c: esc(usd(c["latest"].get("contributions"))), True),
        ("Revenue", lambda c: esc(usd(c["latest"].get("rev_total"))), True),
        ("Programs", lambda c: esc(pct(c["m"].get("program_share"))), True),
        ("Fundraising", lambda c: esc(pct(c["m"].get("fund_share"))), True),
        ("Top pay", lambda c: esc(usd(c["m"].get("top_comp"))), True),
    ]


def home(ctx, stats, top, cats, states, guides):
    n = stats["charities"]
    body = (f'<section class="hero"><h1>Where does the money go?</h1>'
            f'<p class="lede">Spending breakdowns of {n:,} US charities, straight from the IRS Form 990 each one files. '
            f'Program spending, executive pay, revenue sources and up to seven years of trends. Every number links to its filing. No ratings, no paywall.</p>'
            f'<div class="search" role="search"><input type="search" placeholder="Search a charity, e.g. Red Cross, St. Jude, Feeding America" aria-label="Search charities" autocomplete="off" data-search><ul hidden role="listbox"></ul></div>'
            f'<p class="src">Covers every US 501(c)(3) public charity with $10 million or more in revenue on its latest Form 990. '
            f'<a href="{ctx.u("/guides/givingtuesday-checklist/")}">Giving on GivingTuesday? A five-minute filing check</a>.</p></section>'
            f'<section class="card"><h2>Where $100 went at the charities that raise the most</h2>'
            f'<span class="cap">Ranked by contributions and grants on each one\'s latest Form 990, leaving out grantmakers and donor-advised fund sponsors. Size isn\'t a recommendation.</span>'
            f'{row_list(ctx, top)}<p class="ctx"><a href="{ctx.u("/guides/largest-charities/")}">The 100 charities that raised the most</a> · '
            f'<a href="{ctx.u("/charities/")}">All {n:,} charities A–Z</a></p></section>'
            f'<section class="card"><h2>Browse by cause</h2><ul class="tiles">' + "".join(
                f'<li><a href="{ctx.u(f"/category/{slug}/")}">{esc(label)}<small>{cnt:,} charities</small></a></li>'
                for slug, label, cnt in cats) + '</ul></section>'
            f'<section class="card"><h2>Browse by state</h2><ul class="tiles">' + "".join(
                f'<li><a href="{ctx.u(f"/state/{code.lower()}/")}">{esc(name)}<small>{cnt:,} charities</small></a></li>'
                for code, name, cnt in states) + '</ul></section>'
            f'<section class="card"><h2>Read a 990 like a pro</h2><ul class="list">' + "".join(
                f'<li><a class="t" href="{ctx.u("/guides/" + g["slug"] + "/")}">{esc(g["title"])}</a><div class="s">{esc(g["description"])}</div></li>'
                for g in guides[:6]) + f'</ul><p class="ctx"><a href="{ctx.u("/guides/")}">All guides</a></p></section>')
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": ctx.abs("/"),
           "potentialAction": {"@type": "SearchAction", "target": ctx.abs("/search/?q={search_term_string}"),
                               "query-input": "required name=search_term_string"}},
          {"@context": "https://schema.org", "@type": "Dataset", "name": "Charity Form 990 spending breakdowns",
           "description": f"Program, management and fundraising spending, revenue sources, compensation and governance answers for {n:,} US public charities, from IRS Form 990 e-file data.",
           "url": ctx.abs("/data/"), "license": "https://creativecommons.org/publicdomain/zero/1.0/",
           "creator": {"@type": "Organization", "name": SITE_NAME}, "isBasedOn": "https://www.irs.gov/charities-non-profits/form-990-series-downloads",
           "distribution": {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": ctx.abs("/data/charities.csv")}}]
    return layout(ctx, title=f"{SITE_NAME}: where charities' money goes, from their IRS Form 990",
                  description=f"Free, sourced spending breakdowns of {n:,} US charities from their own Form 990 filings: program share, executive pay, revenue mix and trends. No ratings.",
                  path="/", body=body, jsonld=ld, page="home")


def category_index(ctx, cats):
    body = ('<h1>Charities by cause</h1><p class="lede">Causes follow the IRS\'s National Taxonomy of Exempt Entities (NTEE) code for each organization.</p>'
            '<ul class="tiles">' + "".join(f'<li><a href="{ctx.u(f"/category/{slug}/")}">{esc(label)}<small>{cnt:,} charities</small></a></li>'
                                           for slug, label, cnt in cats) + "</ul>")
    return layout(ctx, title="US charities by cause: where the money goes", description="Browse Form 990 spending breakdowns of US charities by cause.",
                  path="/category/", body=body)


def medians_note(meds, label):
    if not meds or "program_share" not in meds:
        return ""
    p, mg, f = hundred_split([meds["program_share"], meds.get("mgmt_share", 0), meds.get("fund_share", 0)])
    bits = [f"programs {pct(meds['program_share'])}", f"management {pct(meds.get('mgmt_share'))}", f"fundraising {pct(meds.get('fund_share'))}"]
    if "top_comp" in meds:
        bits.append(f"highest reported compensation {usd(meds['top_comp'], short=False)}")
    return (f'<p class="ctx">Medians across the {meds["n"]:,} covered {esc(label.lower())} charities (latest filings): ' + ", ".join(bits) + ".</p>")


def category_page(ctx, slug, label, items, meds, limit=250):
    shown = items[:limit]
    body = (f'<p class="crumbs"><a href="{ctx.u("/")}">Home</a> › <a href="{ctx.u("/category/")}">Causes</a></p>'
            f'<h1>{esc(label)} charities: where the money goes</h1>'
            f'<p class="lede">The {len(shown):,} largest of {len(items):,} covered {esc(label.lower())} charities by contributions and grants, from their latest IRS Form 990.</p>'
            + medians_note(meds, label) + table(ctx, shown, std_cols(ctx))
            + (f'<p class="ctx">{len(items) - len(shown):,} more are in the <a href="{ctx.u("/charities/")}">A–Z list</a> and search.</p>' if len(items) > len(shown) else ""))
    return layout(ctx, title=f"Largest {label.lower()} charities: spending, pay and revenue from Form 990",
                  description=f"Where the money goes at {len(items):,} US {label.lower()} charities: program share, fundraising costs and executive pay from IRS Form 990 filings.",
                  path=f"/category/{slug}/", body=body)


def state_index(ctx, states):
    body = ('<h1>Charities by state</h1><p class="lede">By the state on each organization\'s latest Form 990.</p><ul class="tiles">' + "".join(
        f'<li><a href="{ctx.u(f"/state/{code.lower()}/")}">{esc(name)}<small>{cnt:,} charities</small></a></li>' for code, name, cnt in states) + "</ul>")
    return layout(ctx, title="US charities by state: where the money goes", description="Browse Form 990 spending breakdowns of US charities by state.",
                  path="/state/", body=body)


def state_page(ctx, code, name, items, limit=200):
    shown = items[:limit]
    body = (f'<p class="crumbs"><a href="{ctx.u("/")}">Home</a> › <a href="{ctx.u("/state/")}">States</a></p>'
            f'<h1>Largest charities in {esc(name)}</h1>'
            f'<p class="lede">{len(shown):,} of {len(items):,} covered charities based in {esc(name)}, by contributions and grants on their latest IRS Form 990.</p>'
            + table(ctx, shown, std_cols(ctx)))
    return layout(ctx, title=f"Largest charities in {name}: where the money goes (Form 990)",
                  description=f"Spending breakdowns of {len(items):,} {name} charities from their IRS Form 990: program share, fundraising and executive pay.",
                  path=f"/state/{code.lower()}/", body=body)


def az_index(ctx, letters):
    body = ('<h1>All charities, A–Z</h1><p class="lede">Every charity on this site, by name.</p><ul class="tiles">' + "".join(
        f'<li><a href="{ctx.u(f"/charities/{k}/")}">{esc(k.upper() if k != "0" else "0–9")}<small>{n:,} charities</small></a></li>' for k, n in letters) + "</ul>")
    return layout(ctx, title="All charities A–Z: Form 990 spending breakdowns", description="Every charity covered by Charity Impact Media, by name.",
                  path="/charities/", body=body)


def az_page(ctx, key, items):
    lab = key.upper() if key != "0" else "0–9"
    body = (f'<p class="crumbs"><a href="{ctx.u("/")}">Home</a> › <a href="{ctx.u("/charities/")}">A–Z</a></p><h1>Charities: {esc(lab)}</h1>'
            '<ul class="list">' + "".join(
                f'<li><a class="t" href="{ctx.charity(c["ein"])}">{esc(c["name"])}</a> <span class="s">{esc(c["city"])}, {esc(c["state"])} · revenue {esc(usd(c["latest"].get("rev_total")))}</span></li>'
                for c in items) + "</ul>")
    return layout(ctx, title=f"Charities starting with {lab}: Form 990 breakdowns", description=f"{len(items):,} charities whose names start with {lab}.",
                  path=f"/charities/{key}/", body=body)


def compare_page(ctx):
    body = ('<h1>Compare charities</h1><p class="lede">Put up to three charities side by side. Every figure comes from each one\'s latest Form 990.</p>'
            '<div class="card"><label for="cmp-add"><strong>Add a charity</strong></label><div class="search" role="search" style="max-width:520px;margin:8px 0 0">'
            '<input id="cmp-add" type="search" placeholder="Search by name or EIN" autocomplete="off" data-search data-mode="compare"><ul hidden role="listbox"></ul></div>'
            '<div id="cmp" class="scroll" style="margin-top:14px" data-compare><p class="src">Pick charities to compare.</p></div>'
            '<div class="btns"><button class="btn" type="button" data-act="copy-compare">Copy link to this comparison</button></div></div>'
            '<noscript><p>Comparing needs JavaScript. Each charity page has the same figures.</p></noscript>')
    return layout(ctx, title="Compare charities side by side (Form 990)", description="Compare up to three charities' spending, revenue and pay from their IRS Form 990 filings.",
                  path="/compare/", body=body, page="compare")


def embed_page(ctx):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Where the money goes</title><meta name="robots" content="noindex"><link rel="stylesheet" href="{ctx.u('/assets/app.css')}?v={ctx.v}">
<style>body{{background:transparent}}</style></head><body data-page="embed" data-base="{esc(ctx.base)}">
<div class="embedcard" id="embed" data-embed><p class="src">Loading…</p></div>
<script src="{ctx.u('/assets/app.js')}?v={ctx.v}" defer></script></body></html>
"""


def search_page(ctx):
    body = ('<h1>Search charities</h1><div class="search" role="search" style="max-width:640px;margin:0 0 16px">'
            '<input type="search" placeholder="Name or EIN" aria-label="Search charities" autocomplete="off" data-search data-autofocus><ul hidden role="listbox"></ul></div>'
            f'<p class="src">Or browse <a href="{ctx.u("/charities/")}">A–Z</a>, <a href="{ctx.u("/category/")}">by cause</a> or <a href="{ctx.u("/state/")}">by state</a>.</p>')
    return layout(ctx, title="Search charities", description="Search Form 990 breakdowns of US charities by name or EIN.", path="/search/", body=body, noindex=True)


def method_page(ctx, stats):
    s = stats
    yrs = ", ".join(f"{y}: {n:,}" for y, n in s["latest_years"].items())
    body = f"""<div class="prose"><h1>How we build this</h1>
<p class="lede">Every figure on this site is a number a charity reported to the IRS on its own Form 990, or a ratio of two such numbers from the same filing. We don't estimate, adjust, score or grade anything.</p>
<h2>Which charities</h2>
<p>Every 501(c)(3) public charity in the IRS Exempt Organizations Business Master File whose latest Form 990 reports total revenue of $10 million or more, provided that filing is for one of the last three complete tax years. That is {s['charities']:,} organizations today. Private foundations (Form 990-PF) and small organizations that file Form 990-EZ or 990-N aren't covered. Churches generally don't file a Form 990, so most aren't here.</p>
<p>Latest filing year across covered charities: {esc(yrs)}.</p>
<h2>Which filings</h2>
<p>For each charity and each tax year since 2019 we use the latest return the IRS released. An amended return replaces the original. Filings come from the IRS's public e-file data, read from the <a href="https://990data.givingtuesday.org/">GivingTuesday 990 Data Lake</a> and, for returns the data lake doesn't have yet, from the <a href="https://www.irs.gov/charities-non-profits/form-990-series-downloads">IRS's monthly Form 990 releases</a>. {s['filings']:,} filings are on the site.</p>
<h2>The measures</h2>
<ul>
<li><strong>Program services, management &amp; general, fundraising</strong>: each column of Part IX, line 25 (total functional expenses) divided by column A. How costs are split across the three columns is the organization's own allocation.</li>
<li><strong>Where $100 went</strong>: the same three shares, as cents of $100 (rounded so the parts add to exactly $100).</li>
<li><strong>Fundraising cost per $1 of contributions</strong>: Part IX, line 25, column D divided by Part VIII, line 1h (all contributions, gifts and grants, including government grants). Shown only when contributions are $250,000 or more.</li>
<li><strong>Revenue shares</strong>: Part VIII, line 1h (contributions and grants), line 1e (government grants, a part of 1h) and line 2g (program service revenue) divided by line 12 (total revenue).</li>
<li><strong>Highest reported compensation</strong>: the largest total of Part VII, Section A, columns D, E and F (reportable compensation from the organization and from related organizations, plus other compensation such as benefits) for any listed person. Shown by role, not name.</li>
<li><strong>Net assets in months of expenses</strong>: Part X, line 33 (end of year) divided by one month of total expenses.</li>
<li><strong>Governance answers</strong>: the organization's yes/no answers in Parts IV, VI and XII, copied as filed. Many have explanations in Schedule O of the filing.</li>
</ul>
<h2>Medians, not ratings</h2>
<p>Each scorecard shows the median for covered charities in the same cause (NTEE major group) when there are at least 30 of them, and across all covered charities otherwise. A median describes the group; it isn't a benchmark. A low program share can reflect a startup year, a capital campaign or an accounting choice, and a high one says nothing about whether programs work. We never label a charity or a number good or bad.</p>
<h2>What the 990 can't tell you</h2>
<ul><li>Whether programs achieve their goals. The 990 reports spending, not outcomes.</li>
<li>Exact apples-to-apples comparisons. Fiscal years end in different months, hospitals and universities report differently from grantmakers, and group returns combine many affiliates.</li>
<li>Anything after the latest filing. Large charities often file 10 to 11 months after their fiscal year ends.</li></ul>
<h2>People</h2>
<p>Form 990 lists officers, directors and key employees by name. We show their roles and compensation, not their names: the filing linked on every page has the names for anyone who needs them. Contractors are listed only when they are businesses.</p>
<h2>Updates</h2>
<p>A scheduled job checks the IRS and data-lake indexes every week. When new filings appear it rebuilds every page and records each new filing on the <a href="{ctx.u('/updates/')}">new filings</a> page and <a href="{ctx.u('/feed.xml')}">feed</a>. The code is public: <a href="https://github.com/{esc(ctx.repo)}">github.com/{esc(ctx.repo)}</a>.</p>
<h2>Mistakes</h2>
<p>If a figure here doesn't match the filing, that's our error. <a href="{ctx.u('/corrections/')}">Report it</a> and it's fixed in the next build.</p></div>"""
    return layout(ctx, title="Method: how Charity Impact Media reads Form 990 filings",
                  description="Sources, definitions and limits of the Form 990 spending breakdowns on Charity Impact Media.", path="/method/", body=body)


def corrections_page(ctx, recent):
    items = "".join(f'<li><a href="{esc(r["url"])}" rel="noopener">{"Response" if r["kind"] == "reply" else "Correction"} #{r["n"]}</a> about '
                    f'<a href="{ctx.charity(r["ein"])}">{esc(r["name"])}</a> ({esc(r["state"])})</li>' for r in recent[:50])
    body = f"""<div class="prose"><h1>Corrections and right of reply</h1>
<p class="lede">Every charity page has two public buttons: <strong>Report a correction</strong> and <strong>Respond</strong>. Both open a public issue on GitHub, linked from that charity's page.</p>
<h2>If a number is wrong</h2>
<p>We copy figures from each organization's own Form 990. If a figure on this site doesn't match the filing, that's our mistake: report it and the fix ships with the next weekly build, noted on the issue. If the filing itself is wrong, the organization can file an amended return with the IRS. When the IRS releases it, the amended return replaces the original here automatically.</p>
<h2>If you work for a charity on this site</h2>
<p>You can publish a response: context for a number, a program result, a change since the filing. Responses are public, linked from your page as filed, and never edited by us. Please don't include personal contact details. We don't sell services to the charities we cover, and responding costs nothing.</p>
<h2>How to submit</h2>
<ul><li><a href="{esc(ctx.issue_url('correction.yml', 'Correction: '))}" rel="noopener">Report a correction</a></li>
<li><a href="{esc(ctx.issue_url('reply.yml', 'Reply: '))}" rel="noopener">Respond on behalf of an organization</a></li></ul>
<p>Both need a free GitHub account. The public issue list is <a href="https://github.com/{esc(ctx.repo)}/issues">here</a>.</p>
<h2>On file</h2>{f'<ul>{items}</ul>' if items else '<p>Nothing yet.</p>'}</div>"""
    return layout(ctx, title="Corrections and right of reply", description="How charities and readers correct a figure or publish a response on Charity Impact Media.",
                  path="/corrections/", body=body)


def about_page(ctx, stats):
    body = f"""<div class="prose"><h1>About</h1>
<p class="lede">{SITE_NAME} shows what the largest US charities report about their own money: where it came from, where it went and who was paid the most, with the filing behind every number.</p>
<p>It's built and refreshed by software from public IRS data. There are no ratings, rankings by merit, sponsored placements or ads, and nothing here is financial, legal or tax advice. We don't consult for or take money from the charities we cover.</p>
<p>Covered today: {stats['charities']:,} charities and {stats['filings']:,} filings. The data is in the public domain (<a href="{ctx.u('/data/')}">download it</a>), and so is the <a href="https://github.com/{esc(ctx.repo)}">code</a>.</p>
<p>Companion project: <a href="https://theguysaccount.github.io/whofunds-open-grant-graph/">WHOFUNDS</a>, an open graph of which private foundations fund which organizations.</p>
<p>Questions, corrections and responses: <a href="{ctx.u('/corrections/')}">corrections and right of reply</a>.</p></div>"""
    return layout(ctx, title=f"About {SITE_NAME}", description="Who builds Charity Impact Media and how.", path="/about/", body=body)


def data_page(ctx, stats, columns):
    cols = "".join(f"<li><code>{esc(c)}</code>: {esc(d)}</li>" for c, d in columns)
    body = f"""<div class="prose"><h1>Download the data</h1>
<p class="lede">Every charity's scorecard from its latest Form 990, as one CSV. Public domain (CC0 1.0): use it for anything, no attribution required.</p>
<p><a class="btn primary" href="{ctx.u('/data/charities.csv')}" data-ev="download">charities.csv</a> <span class="src">{stats['charities']:,} rows · updated {esc(stats['built'])}</span></p>
<p>Every filing and the parse cache are attached to each <a href="https://github.com/{esc(ctx.repo)}/releases/latest">data release</a> on GitHub.</p>
<h2>Columns</h2><ul>{cols}</ul></div>"""
    ld = [{"@context": "https://schema.org", "@type": "Dataset", "name": "Charity Form 990 scorecards",
           "description": f"Form 990 spending, revenue, compensation and governance measures for {stats['charities']:,} US public charities.",
           "url": ctx.abs("/data/"), "license": "https://creativecommons.org/publicdomain/zero/1.0/", "dateModified": stats["built"],
           "distribution": {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": ctx.abs("/data/charities.csv")}}]
    return layout(ctx, title="Download: Form 990 scorecards for 25,000+ US charities (CSV, CC0)", description="Free CSV of Form 990 spending breakdowns for US public charities.",
                  path="/data/", body=body, jsonld=ld)


def updates_page(ctx, recent):
    rows = "".join(f'<li><a class="t" href="{ctx.charity(c["ein"])}">{esc(c["name"])}</a><div class="s">{esc(seen)} · added the Form 990 for {esc(period(y)[0])}'
                   f' · revenue {esc(usd(y.get("rev_total")))}</div></li>' for seen, c, y in recent[:200])
    body = (f'<h1>New filings</h1><p class="lede">Filings added in recent weekly updates, newest first. '
            f'<a href="{ctx.u("/feed.xml")}">Follow with a feed reader</a>.</p><ul class="list">{rows}</ul>')
    return layout(ctx, title="New charity Form 990 filings", description="The latest Form 990 filings added to Charity Impact Media.", path="/updates/", body=body)


def guides_index(ctx, guides):
    body = ('<h1>Guides</h1><p class="lede">How to read what a charity reports, in plain English.</p><ul class="list">' + "".join(
        f'<li><a class="t" href="{ctx.u("/guides/" + g["slug"] + "/")}">{esc(g["title"])}</a><div class="s">{esc(g["description"])}</div></li>' for g in guides) + "</ul>")
    return layout(ctx, title="Guides: how to read a charity's Form 990", description="Plain-English guides to charity filings: program ratios, executive pay, fundraising costs.",
                  path="/guides/", body=body)


def guide_page(ctx, g, html_body):
    body = (f'<p class="crumbs"><a href="{ctx.u("/")}">Home</a> › <a href="{ctx.u("/guides/")}">Guides</a></p>'
            f'<article class="prose"><h1>{esc(g["title"])}</h1><p class="meta">Updated {esc(ctx.built)}</p>{html_body}</article>')
    ld = [{"@context": "https://schema.org", "@type": "Article", "headline": g["title"], "description": g["description"],
           "dateModified": ctx.built, "author": {"@type": "Organization", "name": SITE_NAME}, "publisher": {"@type": "Organization", "name": SITE_NAME},
           "mainEntityOfPage": ctx.abs(f"/guides/{g['slug']}/")}]
    return layout(ctx, title=g["title"], description=g["description"], path=f"/guides/{g['slug']}/", body=body, jsonld=ld, og_type="article")


def not_found(ctx):
    body = ('<h1>Page not found</h1><p>That page isn\'t here. Search for a charity instead:</p>'
            '<div class="search" role="search" style="max-width:640px"><input type="search" placeholder="Name or EIN" aria-label="Search charities" autocomplete="off" data-search><ul hidden role="listbox"></ul></div>'
            f'<p class="src" style="margin-top:12px"><a href="{ctx.u("/")}">Home</a> · <a href="{ctx.u("/charities/")}">A–Z</a></p>')
    return layout(ctx, title="Page not found", description="Page not found.", path="/404.html", body=body, noindex=True, page="404")


PLACEHOLDER = re.compile(r"\{\{(\w+)(?::([\w/-]+))?(?::(\d+))?\}\}")


def fill_guide(ctx, text, data):
    """Replace {{name:arg:n}} placeholders in a guide with live tables built from the data."""
    def rep(mm):
        kind, arg, n = mm.group(1), mm.group(2) or "", int(mm.group(3) or 25)
        fn = data.get(kind)
        return fn(arg, n) if fn else mm.group(0)
    return PLACEHOLDER.sub(rep, text)


def feed(ctx, recent):
    entries = []
    for seen, c, y in recent[:100]:
        u = ctx.abs(f"/charity/{c['ein']}/")
        title = f"{c['name']}: Form 990 for {period(y)[0]}"
        summary = "Revenue " + usd(y.get("rev_total")) + ", expenses " + usd(y.get("exp_total")) + "."
        entries.append(f"<entry><title>{esc(title)}</title><link href=\"{esc(u)}\"/><id>{esc(u)}#{esc(y['oid'])}</id>"
                       f"<updated>{esc(seen)}T00:00:00Z</updated><summary>{esc(summary)}</summary></entry>")
    updated = recent[0][0] if recent else ctx.built
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom"><title>{SITE_NAME}: new Form 990 filings</title>'
            f'<link href="{esc(ctx.abs("/feed.xml"))}" rel="self"/><link href="{esc(ctx.abs("/"))}"/><id>{esc(ctx.abs("/"))}</id>'
            f'<updated>{esc(updated)}T00:00:00Z</updated>{"".join(entries)}</feed>\n')


def ein_label(e):
    return ein_dash(e)
