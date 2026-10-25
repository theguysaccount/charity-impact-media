#!/usr/bin/env python3
"""Build the static site into dist/ from data/work/site_data.json.gz.

  CIM_BASE_URL=https://<user>.github.io/<repo> CIM_REPO=<user>/<repo> python3 pipeline/build_site.py

Optional: CIM_SUPPORT_URL (sponsor or donation link: the money slot), CIM_GOATCOUNTER
(https://<code>.goatcounter.com/count, cookieless analytics), CIM_OUT (default dist/).
Open Graph cards made by og_cards.py in data/work/og/ are copied in when present.
"""

import csv
import datetime
import hashlib
import io
import json
import os
import re
import shutil
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pages as P  # noqa: E402
import render as R  # noqa: E402
from build_data import CATEGORIES, STATE_NAMES  # noqa: E402
from common import PROPUBLICA_FILING, ROOT, WORK, ein_dash, read_json  # noqa: E402

SITE = os.path.join(ROOT, "site")
CONTENT = os.path.join(ROOT, "content")
SIZE_LIMIT = 950e6
PAGES_BUDGET = float(os.environ.get("CIM_PAGES_BUDGET_MB") or 700) * 1e6
CSV_COLUMNS = [
    ("ein", "IRS employer identification number"), ("name", "Display name (from the latest filing)"),
    ("also_known_as", "Doing-business-as name, when filed"), ("city", "City on the latest filing"), ("state", "State"),
    ("ntee", "NTEE code (IRS Business Master File)"), ("cause", "NTEE major group"),
    ("tax_year", "IRS tax year of the latest filing"), ("fiscal_year_end", "Last day of that fiscal year"),
    ("object_id", "IRS e-file object id of the filing"), ("filing_url", "The filing on ProPublica Nonprofit Explorer"),
    ("revenue", "Total revenue, Part I line 12"), ("contributions", "Contributions and grants, Part VIII line 1h"),
    ("government_grants", "Part VIII line 1e"), ("program_service_revenue", "Part VIII line 2g"),
    ("investment_income", "Part VIII line 3"), ("expenses", "Total functional expenses, Part IX line 25(A)"),
    ("program_expenses", "Part IX line 25(B)"), ("management_expenses", "Part IX line 25(C)"),
    ("fundraising_expenses", "Part IX line 25(D)"), ("program_share", "program_expenses / expenses"),
    ("management_share", "management_expenses / expenses"), ("fundraising_share", "fundraising_expenses / expenses"),
    ("fundraising_cost_per_dollar", "fundraising_expenses / contributions (contributions >= $250,000)"),
    ("highest_compensation", "Largest Part VII Section A total (columns D+E+F)"),
    ("highest_compensation_role", "That person's title as filed (names are not published)"),
    ("people_over_100k", "Part VII line 2"), ("net_assets", "Part X line 33(B)"),
    ("months_of_net_assets", "net_assets / (expenses / 12)"), ("board_voting", "Part VI line 1a"),
    ("board_independent", "Part VI line 1b"), ("audited", "Part XII line 2b (1 yes, 0 no, blank not answered)"),
    ("conflict_policy", "Part VI line 12a"), ("whistleblower_policy", "Part VI line 13"),
    ("years_on_file", "Tax years with a Form 990 here"), ("page_url", "This charity's page"),
]


def env(name, default=""):
    return (os.environ.get(name) or default).strip()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return len(text.encode("utf-8"))


def asset_version(stats):
    h = hashlib.sha256()
    for fn in sorted(os.listdir(os.path.join(SITE, "static"))):
        with open(os.path.join(SITE, "static", fn), "rb") as f:
            h.update(f.read())
    h.update(stats["built"].encode())
    return h.hexdigest()[:10]


def load_guides():
    out = []
    d = os.path.join(CONTENT, "guides")
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".html"):
            continue
        with open(os.path.join(d, fn), encoding="utf-8") as f:
            text = f.read()
        m = re.match(r"<!--(\{.*?\})-->\s*", text, re.S)
        meta = json.loads(m.group(1))
        out.append({**meta, "slug": fn[:-5], "body": text[m.end():]})
    out.sort(key=lambda g: g.get("order", 99))
    return out


def az_key(name):
    s = re.sub(r"^(the|a|an)\s+", "", name.strip(), flags=re.I)
    ch = (s[:1] or "0").lower()
    return ch if "a" <= ch <= "z" else "0"


def csv_row(ctx, c):
    L, m, y = c["latest"], c["m"], c["years"][-1]
    f = L.get("f") or {}
    yn = lambda v: "" if v is None else ("1" if v else "0")  # noqa: E731
    r4 = lambda v: "" if v is None else f"{v:.4f}"  # noqa: E731
    return [c["ein"], c["name"], c.get("dba", ""), c["city"], c["state"], c["ntee"], c["cat_label"], y["ty"], y.get("period_end", ""),
            y["oid"], PROPUBLICA_FILING.format(ein=c["ein"], object_id=y["oid"]), L.get("rev_total"), L.get("contributions"),
            L.get("gov_grants"), L.get("program_rev"), L.get("investment"), L.get("exp_total"), L.get("exp_program"),
            L.get("exp_mgmt"), L.get("exp_fundraising"), r4(m.get("program_share")), r4(m.get("mgmt_share")), r4(m.get("fund_share")),
            r4(m.get("cost_per_dollar")), m.get("top_comp", ""), m.get("top_comp_title", ""), m.get("n_over_100k", ""),
            L.get("net_assets"), "" if m.get("months_net_assets") is None else f"{m['months_net_assets']:.1f}",
            L.get("board_voting"), L.get("board_independent"), yn(f.get("audited")), yn(f.get("conflict_policy")),
            yn(f.get("whistleblower")), " ".join(str(x["ty"]) for x in c["years"]), ctx.abs(f"/charity/{c['ein']}/")]


def data_json(c):
    m, y = c["m"], c["years"][-1]
    ph, lab = R.period(y)
    keep = ["program_share", "mgmt_share", "fund_share", "cost_per_dollar", "contrib_share", "gov_share", "program_rev_share",
            "top_comp", "top_comp_title", "top_comp_share", "n_over_100k", "months_net_assets", "independent_share"]
    return {"e": c["ein"], "n": c["name"], "c": c["city"], "s": c["state"], "fy": lab, "ph": ph, "oid": y["oid"],
            "rev": c["latest"].get("rev_total"), "exp": c["latest"].get("exp_total"), "contrib": c["latest"].get("contributions"),
            "na": c["latest"].get("net_assets"),
            "m": {k: (round(v, 5) if isinstance(v, float) else v) for k, v in m.items() if k in keep},
            "y": [[x["ty"], R.period(x)[1], x.get("rev_total"), x.get("exp_total"),
                   None if x.get("program_share") is None else round(x["program_share"], 5)] for x in c["years"]]}


def similar_for(c, by_cat_sorted):
    """Five charities in the same cause closest in revenue (excluding itself)."""
    lst = by_cat_sorted[c["cat"]]
    i = c["_cat_rev_idx"]
    out, lo, hi = [], i - 1, i + 1
    while len(out) < 5 and (lo >= 0 or hi < len(lst)):
        if hi < len(lst):
            out.append(lst[hi])
            hi += 1
        if len(out) < 5 and lo >= 0:
            out.append(lst[lo])
            lo -= 1
    return out


def main():
    base_url = env("CIM_BASE_URL")
    if not base_url:
        sys.exit("CIM_BASE_URL is required, e.g. https://theguysaccount.github.io/charity-impact-media")
    data = read_json(os.path.join(WORK, "site_data.json.gz"))
    stats, charities = data["stats"], data["charities"]
    ctx = R.Ctx(base_url, env("CIM_REPO", "theguysaccount/charity-impact-media"), asset_version(stats),
                support_url=env("CIM_SUPPORT_URL"), goatcounter=env("CIM_GOATCOUNTER"), built=stats["built"],
                n=stats["charities"])
    out = env("CIM_OUT", os.path.join(ROOT, "dist"))
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "assets"))
    for fn in os.listdir(os.path.join(SITE, "static")):
        shutil.copyfile(os.path.join(SITE, "static", fn), os.path.join(out, "assets", fn))
    write(os.path.join(out, ".nojekyll"), "")
    og_dir = os.path.join(WORK, "og")
    if os.path.exists(os.path.join(og_dir, "site.png")):
        shutil.copyfile(os.path.join(og_dir, "site.png"), os.path.join(out, "assets", "og.png"))

    for c in charities:
        c["cat_slug"], c["cat_label"] = CATEGORIES[c["cat"]]
        c["state_name"] = STATE_NAMES.get(c["state"], c["state"])
    by_cat = defaultdict(list)
    by_state = defaultdict(list)
    for c in charities:  # already sorted by contributions
        by_cat[c["cat"]].append(c)
        by_state[c["state"]].append(c)
    by_cat_rev = {}
    for k, lst in by_cat.items():
        srt = sorted(lst, key=lambda c: (-(c["latest"].get("rev_total") or 0), c["ein"]))
        for i, c in enumerate(srt):
            c["_cat_rev_idx"] = i
        by_cat_rev[k] = srt

    urls = []        # (path, lastmod)
    changed = []     # paths whose content changed in this build (for IndexNow)
    recent_cut = (datetime.date.fromisoformat(stats["built"]) - datetime.timedelta(days=8)).isoformat()
    sizes = {}
    n_og = 0
    og_urls = {}
    for c in charities:
        ein = c["ein"]
        card = os.path.join(og_dir, f"{ein}.png")
        if os.path.exists(card):
            os.makedirs(os.path.join(out, "charity", ein), exist_ok=True)
            shutil.copyfile(card, os.path.join(out, "charity", ein, "card.png"))
            og_urls[ein] = ctx.abs(f"/charity/{ein}/card.png?v={c['years'][-1]['oid']}")
            n_og += 1
        html_text = R.charity_page(ctx, c, similar_for(c, by_cat_rev), og_image=og_urls.get(ein))
        sizes[ein] = write(os.path.join(out, "charity", ein, "index.html"), html_text)
        write(os.path.join(out, "charity", ein, "data.json"), json.dumps(data_json(c), separators=(",", ":"), ensure_ascii=False))
        lastmod = max(x["seen"] for x in c["years"])
        urls.append((f"/charity/{ein}/", lastmod))
        if lastmod >= recent_cut:
            changed.append(f"/charity/{ein}/")
    # Stay inside the GitHub Pages budget as coverage grows: from the smallest charity up,
    # switch pages to the slim layout (no trend chart, contractors, similar list or FAQ).
    total, n_slim = sum(sizes.values()), 0
    for c in reversed(charities):
        if total <= PAGES_BUDGET:
            break
        ein = c["ein"]
        html_text = R.charity_page(ctx, c, [], og_image=og_urls.get(ein), slim=True)
        new = write(os.path.join(out, "charity", ein, "index.html"), html_text)
        total += new - sizes[ein]
        n_slim += 1
    print(f"charity pages: {len(charities)} ({total / 1e6:.0f} MB HTML, {n_slim} slim), {n_og} with share cards", file=sys.stderr)

    cats = [(CATEGORIES[k][0], CATEGORIES[k][1], len(v)) for k, v in sorted(by_cat.items(), key=lambda kv: -len(kv[1])) if len(v) >= 5]
    for k, lst in by_cat.items():
        if len(lst) < 5:
            continue
        slug, label = CATEGORIES[k]
        write(os.path.join(out, "category", slug, "index.html"), P.category_page(ctx, slug, label, lst, stats["category_medians"].get(k)))
        urls.append((f"/category/{slug}/", stats["built"]))
    write(os.path.join(out, "category", "index.html"), P.category_index(ctx, cats))
    states = [(code, STATE_NAMES[code], len(v)) for code, v in sorted(by_state.items(), key=lambda kv: STATE_NAMES.get(kv[0], kv[0]))
              if code in STATE_NAMES]
    for code, name, _ in states:
        write(os.path.join(out, "state", code.lower(), "index.html"), P.state_page(ctx, code, name, by_state[code]))
        urls.append((f"/state/{code.lower()}/", stats["built"]))
    write(os.path.join(out, "state", "index.html"), P.state_index(ctx, states))

    az = defaultdict(list)
    for c in sorted(charities, key=lambda c: (re.sub(r"^(the|a|an)\s+", "", c["name"].lower()), c["ein"])):
        az[az_key(c["name"])].append(c)
    letters = sorted(az.items())
    for k, lst in letters:
        write(os.path.join(out, "charities", k, "index.html"), P.az_page(ctx, k, lst))
        urls.append((f"/charities/{k}/", stats["built"]))
    write(os.path.join(out, "charities", "index.html"), P.az_index(ctx, [(k, len(v)) for k, v in letters]))

    guides = load_guides()
    gdata = guide_data(ctx, charities, stats)
    for g in guides:
        body = P.fill_guide(ctx, g["body"], gdata)
        write(os.path.join(out, "guides", g["slug"], "index.html"), P.guide_page(ctx, g, body))
        urls.append((f"/guides/{g['slug']}/", stats["built"]))
    write(os.path.join(out, "guides", "index.html"), P.guides_index(ctx, guides))

    recent = []
    for c in charities:
        for y in c["years"]:
            recent.append((y["seen"], c, y))
    recent.sort(key=lambda t: (t[0], t[1]["latest"].get("contributions") or 0), reverse=True)
    replies = sorted(({**r, "ein": c["ein"], "name": c["name"]} for c in charities for r in (c.get("replies") or [])),
                     key=lambda r: -r["n"])

    # Home list: operating charities donors look up, so grantmakers and donor-advised fund
    # sponsors (cause T, or DAF holders that mostly pass money on as grants) are left out.
    def featured(c):
        L = c["latest"]
        passthrough = (L.get("f") or {}).get("daf") and (L.get("grants_paid") or 0) > 0.6 * (L.get("exp_total") or 1)
        return c["cat"] != "T" and not passthrough
    write(os.path.join(out, "index.html"), P.home(ctx, stats, [c for c in charities if featured(c)][:12], cats, states, guides))
    write(os.path.join(out, "method", "index.html"), P.method_page(ctx, stats))
    write(os.path.join(out, "about", "index.html"), P.about_page(ctx, stats))
    write(os.path.join(out, "corrections", "index.html"), P.corrections_page(ctx, replies))
    write(os.path.join(out, "data", "index.html"), P.data_page(ctx, stats, CSV_COLUMNS))
    write(os.path.join(out, "updates", "index.html"), P.updates_page(ctx, recent))
    write(os.path.join(out, "compare", "index.html"), P.compare_page(ctx))
    write(os.path.join(out, "embed", "index.html"), P.embed_page(ctx))
    write(os.path.join(out, "search", "index.html"), P.search_page(ctx))
    write(os.path.join(out, "404.html"), P.not_found(ctx))
    write(os.path.join(out, "feed.xml"), P.feed(ctx, recent))
    for p in ["/", "/method/", "/about/", "/corrections/", "/data/", "/updates/", "/compare/", "/category/", "/state/", "/charities/", "/guides/"]:
        urls.append((p, stats["built"]))
    changed += ["/", "/updates/", "/guides/largest-charities/"]

    # Data download and search index.
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([c for c, _ in CSV_COLUMNS])
    for c in charities:
        w.writerow(csv_row(ctx, c))
    write(os.path.join(out, "data", "charities.csv"), buf.getvalue())
    search = [[c["name"], c["ein"], c["city"], c["state"], c.get("dba", "")] for c in charities]
    write(os.path.join(out, "assets", "search.json"), json.dumps(search, separators=(",", ":"), ensure_ascii=False))

    # Sitemap, robots.txt, IndexNow key and URL lists.
    seen_paths = set()
    lines = []
    for p, lm in urls:
        if p in seen_paths:
            continue
        seen_paths.add(p)
        lines.append(f"<url><loc>{R.esc(ctx.abs(p))}</loc><lastmod>{lm}</lastmod></url>")
    write(os.path.join(out, "sitemap.xml"), '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "\n".join(lines) + "\n</urlset>\n")
    write(os.path.join(out, "robots.txt"), f"User-agent: *\nAllow: /\nSitemap: {ctx.abs('/sitemap.xml')}\n")
    key_file = os.path.join(SITE, "indexnow-key.txt")
    if os.path.exists(key_file):
        key = open(key_file).read().strip()
        write(os.path.join(out, f"{key}.txt"), key)
    write(os.path.join(WORK, "urls_all.txt"), "\n".join(ctx.abs(p) for p in sorted(seen_paths)) + "\n")
    write(os.path.join(WORK, "urls_changed.txt"), "\n".join(ctx.abs(p) for p in dict.fromkeys(changed)) + "\n")

    size, files = 0, 0
    for d, _, fs in os.walk(out):
        for fn in fs:
            size += os.path.getsize(os.path.join(d, fn))
            files += 1
    print(f"dist: {files} files, {size / 1e6:.0f} MB; sitemap {len(seen_paths)} URLs, {len(set(changed))} changed", file=sys.stderr)
    if size > SIZE_LIMIT:
        sys.exit(f"dist is {size / 1e6:.0f} MB, over the {SIZE_LIMIT / 1e6:.0f} MB budget for GitHub Pages")


def guide_data(ctx, charities, stats):
    med = stats["overall"]

    def medtxt(key, _n):
        v = med.get(key)
        if v is None:
            return "not available"
        if key in ("program_share", "fund_share", "mgmt_share"):
            return R.pct(v)
        if key == "cost_per_dollar":
            return f"${v:.2f}"
        if key == "top_comp":
            return R.usd(v, short=False)
        if key == "months_net_assets":
            return f"{v:.1f}"
        return str(v)

    def top_contrib(_a, n):
        return P.table(ctx, charities[:n], [("#", lambda c: str(c["rank"]), True)] + P.std_cols(ctx))

    def top_comp(_a, n):
        lst = sorted([c for c in charities[:100] if "top_comp" in c["m"]], key=lambda c: -c["m"]["top_comp"])[:n]
        return P.table(ctx, lst, [("Charity", P.name_cell(ctx), False),
                                  ("Role", lambda c: R.esc(c["m"].get("top_comp_title") or "Listed person"), False),
                                  ("Total compensation", lambda c: R.esc(R.usd(c["m"]["top_comp"], short=False)), True),
                                  ("Share of expenses", lambda c: R.esc(R.pct(c["m"].get("top_comp_share"), 2)), True)])

    def daf(_a, n):
        lst = [c for c in charities if (c["latest"].get("f") or {}).get("daf")][:n]
        return P.table(ctx, lst, [("Charity", P.name_cell(ctx), False),
                                  ("Contributions", lambda c: R.esc(R.usd(c["latest"].get("contributions"))), True),
                                  ("Grants paid", lambda c: R.esc(R.usd(c["latest"].get("grants_paid"))), True),
                                  ("Net assets", lambda c: R.esc(R.usd(c["latest"].get("net_assets"))), True)])

    def cat_medians(_a, _n):
        rows = []
        for k, m in sorted(stats["category_medians"].items(), key=lambda kv: -kv[1]["n"]):
            if m["n"] < 30 or "program_share" not in m:
                continue
            slug, label = CATEGORIES[k]
            rows.append(f'<tr><td><a href="{ctx.u(f"/category/{slug}/")}">{R.esc(label)}</a></td><td class="r">{m["n"]:,}</td>'
                        f'<td class="r">{R.pct(m["program_share"])}</td><td class="r">{R.pct(m.get("fund_share"))}</td></tr>')
        return ('<div class="scroll"><table class="tbl"><thead><tr><th scope="col">Cause</th><th scope="col" class="r">Charities</th>'
                '<th scope="col" class="r">Median programs</th><th scope="col" class="r">Median fundraising</th></tr></thead><tbody>'
                + "".join(rows) + "</tbody></table></div>")

    return {
        "stat": lambda a, n: f"{stats.get(a, 0):,}",
        "median": medtxt,
        "url": lambda a, n: ctx.u(a),
        "top_contributions": top_contrib, "top_comp": top_comp, "daf": daf, "category_medians": cat_medians,
    }


if __name__ == "__main__":
    main()
