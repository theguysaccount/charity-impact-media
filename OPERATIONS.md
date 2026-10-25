# OPERATIONS

How Charity Impact Media runs itself, how each job fails safely, what to watch, and the keys a human can turn later. Nothing here needs a human for the site to keep working.

**Live:** https://theguysaccount.github.io/charity-impact-media/ · **Repo:** https://github.com/theguysaccount/charity-impact-media

## Automated jobs

| Workflow | When | What it does | How it fails safely |
|---|---|---|---|
| `refresh.yml` (Refresh data) | Mondays 06:17 UTC, and by hand | Fingerprints the sources (GivingTuesday 990 Data Lake yearly indexes, IRS monthly e-file indexes for this year and last, IRS EO BMF, the data code). If anything changed: downloads the indexes, re-selects covered charities, fetches **only filings not already in the parse cache** (data lake over S3, IRS-only filings by HTTP range request into the IRS monthly zips), rebuilds the data, runs the tests, builds the site once, runs the guard, publishes a `data-YYYYMMDD-HHMM` release and dispatches the deploy. | Every step must pass before the release is published. The guard refuses a rebuild with fewer than 5,000 charities, a 10% drop in charities, filings or functional-expense coverage against the last release, or more than 2% failed fetches. A failure leaves the previous release and the live site untouched. |
| `deploy.yml` (Deploy site) | After each refresh, on pushes that touch `pipeline/`, `site/`, `content/`, when the health check sees new reply or correction issues, and by hand | Downloads the latest data release, runs the tests, pulls WHOFUNDS cross-links and the reply/correction issues, builds the data, share cards (Pillow) and every page, deploys to GitHub Pages, then submits changed URLs to IndexNow. | If any build step fails, nothing is deployed and Pages keeps serving the previous deployment. If the HTML would exceed the 740 MB page budget, the smallest charities' pages switch to a slim layout (no trend chart, contractors, similar list or embed code) instead of failing; the build fails only above 950 MB. Cross-links and replies are optional inputs: if GitHub's API is down they're skipped. IndexNow errors are logged and never fail the job. |
| `health.yml` (Health) | Daily 08:29 UTC; self-test Sundays 05:41 UTC | Daily: checks the live home page, sitemap, robots.txt, IndexNow key file, search index and five random charity pages (status, canonical URL, source list, correction link, data file), samples ProPublica source links (warnings only); redeploys when the set of reply/correction issues differs from what's live. Sunday: full test suite plus a live self-test that parses the newest Form 990 listed by each source. | Read-only against the site. A failure marks the run red, which emails the repository owner; nothing is changed. |
| `test.yml` (Tests) | Every push and pull request | Unit and build tests; syntax check of the client script. | Read-only. |

**Keep-alive.** GitHub disables scheduled workflows in a public repository after 60 days without activity. `refresh.yml` and `health.yml` (the scheduled ones) end with `scripts/keepalive.sh`, which re-enables the workflow through the API on every run and commits `.github/heartbeat` when the last commit is 45+ days old. The heartbeat commit uses the workflow token, so it doesn't trigger other workflows.

### The data path

```
IRS EO BMF ─┐
GT 990 Data Lake yearly indexes ─┼─ select_filings.py ── needed.csv ── fetch_filings.py ── filings.jsonl.gz (parse cache, released)
IRS monthly e-file indexes ──────┘            (25k charities, 150k filings)     │
                                                                                 └─ build_data.py ── site_data.json.gz ── build_site.py ── dist/ ── Pages
WHOFUNDS release + sitemap ── crosslinks.py ─┘      og_cards.py (share cards) ─┘
GitHub issues (right-of-reply, correction) ── replies.py ─┘
```

Each tax year of each charity uses the latest return released (an amended return wins by its `ReturnTs`). New filings get a `first_seen` date, which drives the sitemap `lastmod`, the `/updates/` page, the Atom feed and which URLs go to IndexNow.

**A full rebuild from scratch** (new parser version, lost release): run *Refresh data* with `force` and `full` checked. It re-fetches ~150,000 filings (~45 minutes on a runner) and changes nothing on the site until every check passes.

## What to watch

- **Actions tab.** A red *Refresh data* means the sources moved or the guard tripped: the site still shows the last good release. A red *Health* means the live site or a source has a problem. GitHub emails the account owner on failures; nothing else alerts.
- **Releases.** One per data change. The notes give counts; `stats.json` has the full numbers (charities, filings, latest-year mix, medians).
- **Issues labelled `right-of-reply` and `correction`.** They're linked from charity pages automatically. Corrections where our figure doesn't match the filing need a code fix (usually in `pipeline/parse990.py`); label junk `invalid` or `spam` to drop it from the site.
- **Coverage drift.** `select_filings.py` covers 501(c)(3) public charities in the current BMF whose latest Form 990 (within the last three complete tax years) reports $10M+ revenue (`CIM_MIN_REVENUE`). If coverage outgrows the page budget, the slim layout absorbs it; raise `CIM_PAGES_BUDGET_MB` (max ~800) or the revenue floor if the build ever fails on size.
- **Action versions.** GitHub now runs the Node 20 actions (`checkout@v4`, `setup-python@v5`, `upload-artifact@v4`, `deploy-pages@v4`) on Node 24 with a deprecation warning, and `ubuntu-latest` moves to Ubuntu 26. Both work today; bump the action majors when a run starts failing on them.
- **Source changes.** The Sunday self-test parses the newest filing from each source. If the IRS changes its zip naming or the data lake changes its index format, it fails first.

## Keys a human can turn later

None is needed for v1. Each adds one thing.

### 1. Custom domain (needs DNS access and a domain decision)
Candidates (ownership unconfirmed, see `LAUNCH.md`): `charityimpactmedia.com`, `effectivecharities.org`, or a subdomain of an owned domain such as `charities.systemicaltruism.org`.
1. At the DNS host: for an apex domain, four `A` records for `@` → `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153` (and `AAAA` → `2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153`, `2606:50c0:8003::153`), plus `CNAME www` → `theguysaccount.github.io`. For a subdomain: one `CNAME` → `theguysaccount.github.io`.
2. Repo → Settings → Pages → Custom domain → enter the domain → Save; tick *Enforce HTTPS* once the certificate is issued.
3. Repo → Settings → Secrets and variables → Actions → Variables → New variable `CIM_SITE_URL` = `https://<domain>` (no trailing slash). Every workflow reads it, so canonical URLs, the sitemap, share cards, IndexNow and the health check move to the domain.
4. Run *Deploy site*. IndexNow verifies the key at the new host on that deploy. A custom domain also fixes robots.txt discovery (crawlers only read robots.txt at a host root). Old `github.io` URLs redirect automatically once the domain is set in Pages.

### 2. Money slot (needs an account with a payout method)
The site shows a "Support this project" footer link and a box on charity pages when the repository variable `CIM_SUPPORT_URL` is set. GitHub Pages is for non-commercial use, so this must be a donation or sponsorship link, not a checkout or ads.
1. Create the destination: GitHub Sponsors for `theguysaccount` (github.com/sponsors → join, add bank and tax details), or an Open Collective / Stripe donation link.
2. Repo → Settings → Secrets and variables → Actions → Variables → New variable `CIM_SUPPORT_URL` = the link.
3. Run *Deploy site* (Actions → Deploy site → Run workflow). Event `support` is counted if analytics is on.
Display ads or paid features would make the site commercial: move hosting to Cloudflare Pages or similar first (the `dist/` output is plain static files).

### 3. Analytics (needs a free GoatCounter account)
Cookieless, no banner needed; skipped for visitors with Do Not Track or Global Privacy Control.
1. Create a site at goatcounter.com (code, e.g. `charityimpact`).
2. Add variable `CIM_GOATCOUNTER` = `https://charityimpact.goatcounter.com/count`; run *Deploy site*.
3. Watch the activation event `ev-scorecard_seen` (a visitor scrolled to a charity's scorecard) per charity-page view; also `ev-source_open`, `ev-share_*`, `ev-embed_copy`, `ev-compare_add`, `ev-search_open`, `ev-reply_open`, `ev-correction_open`, `ev-whofunds_open`.

### 4. Google Search Console (needs a Google account)
Bing, Yandex and the other IndexNow engines are notified automatically; Google isn't.
1. search.google.com/search-console → Add property → URL prefix `https://theguysaccount.github.io/charity-impact-media/` (or the custom domain) → choose the *HTML tag* method and copy the `content` value.
2. Add variable `CIM_GOOGLE_VERIFY` = that value; run *Deploy site* (the tag goes on the home page).
3. Click *Verify* in Search Console, then Sitemaps → submit `sitemap.xml`.

### 5. Root robots.txt (needs a second public repo)
Crawlers read only `https://theguysaccount.github.io/robots.txt`, which doesn't exist (so everything is allowed, but our `Sitemap:` line is never seen). A repo `theguysaccount/theguysaccount.github.io` with a robots.txt listing each project's sitemap fixes it for every project on the account. A custom domain (key 1) also fixes it.

### 6. Contact address for charities without GitHub accounts
Right of reply and corrections run on public GitHub issues, which need a free account. A monitored e-mail address (e.g. `replies@<domain>`) would remove that friction; add it to `pages.corrections_page` and the reply box once someone is reading it.

### 7. Scheduled narratives (a Claude routine; needs a Claude account with routines)
Guides are a pre-written backlog in `content/guides/` with live-data placeholders (`{{top_contributions:all:100}}`, `{{median:program_share}}`, ...) that refresh on every deploy. To keep adding content, schedule a monthly Claude Code routine on this repo with this prompt:

> In theguysaccount/charity-impact-media, read `content/guides/` and the latest release's `stats.json`. Write two new guides in the same format and voice (factual, no ratings or good/bad labels, Form 990 part/line references, no personal names), each answering a question donors search for (e.g. "largest animal charities", "how much do hospital CEOs make"), using placeholders for live figures. Run `python3 -m unittest discover -s tests`, then open a pull request; never push to main directly.

Review and merge the PR; the deploy publishes it.

## Local commands

```bash
python3 pipeline/sources.py check && python3 pipeline/sources.py download   # ~2.5 GB of indexes and BMF
python3 pipeline/select_filings.py
python3 pipeline/fetch_filings.py --workers 48        # ~30 min cold; resumable
python3 pipeline/build_data.py
CIM_BASE_URL=http://localhost:8765/charity-impact-media python3 pipeline/build_site.py
python3 -m unittest discover -s tests                 # CIM_LIVE=1 adds the live source self-test
```
