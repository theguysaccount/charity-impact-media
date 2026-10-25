# LAUNCH

Launch URL: **https://theguysaccount.github.io/charity-impact-media/** (live, no DNS needed). This venture runs in machine-driven mode: nothing below waits on a human, and nothing is posted, sent or bought. Items marked **[key]** are optional and listed with exact steps in `OPERATIONS.md`.

## Production domain: three candidates [key]

| # | Domain | Status (WHOIS, 2026-10-25) | Why / why not |
|---|---|---|---|
| 1 | **parency.org** | Registered at Namecheap 2026-08-20; per the WHOFUNDS notes it's Jack's and unassigned | "Parency" reads as transparency, which is the product. Free. WHOFUNDS also listed it as a possible redirect, so Jack picks which venture gets it. |
| 2 | **charities.systemicaltruism.org** | Parent registered at Namecheap 2026-08-28, Jack's | One CNAME, no cost, and it answers the open question of running this under Systemic Altruism. Weaker as a standalone brand. |
| 3 | **charityimpactmedia.com** (new) | Unregistered | The venture's own name, ~$11/yr. Needs Jack's OK to spend. `effectivecharities.com/.org` are also unregistered, but "effective" implies a rating (DECISIONS D14). |

`charityimpactmedia.com` and `effectivecharities.com`, mentioned in the old notes, are not registered by anyone, so Jack doesn't own them.

## Production deploy steps (after a domain is chosen) [key]

1. DNS at Namecheap (Advanced DNS):
   - Apex (`parency.org` or `charityimpactmedia.com`): `A @ 185.199.108.153`, `A @ 185.199.109.153`, `A @ 185.199.110.153`, `A @ 185.199.111.153`; `AAAA @ 2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153`, `2606:50c0:8003::153`; `CNAME www theguysaccount.github.io.`
   - Subdomain (`charities.systemicaltruism.org`): `CNAME charities theguysaccount.github.io.`
2. GitHub → repo Settings → Pages → Custom domain → the domain → Save → *Enforce HTTPS* when offered.
3. Repo variable `CIM_SITE_URL` = `https://<domain>` → run *Deploy site*. Canonical URLs, sitemap, share cards and IndexNow move to the domain; `github.io` URLs redirect.
4. Redirect domains (e.g. `parency.org` if `charityimpactmedia.com` wins): Namecheap → Domain → Redirect Domain → 301 to the production domain.
5. Verify: `curl -sI https://<domain>/charity/530196605/` → 200; the page's canonical link uses the domain; `https://<domain>/robots.txt` lists the sitemap.

## The first 1,000 users: machine channels only

Who: donors researching a specific charity before giving (peak: GivingTuesday Dec 1 and Dec 15–31), journalists and researchers who need a sourced figure, charity staff checking their own page.

**Search.** ~25,000 charity pages, each titled "X: where the money goes (FY2025 Form 990)" and answering the queries donors type, in plain sentences with a source link:
- `<charity> CEO salary`, `<charity> president salary`, `how much does <charity> CEO make`
- `where does <charity> money go`, `<charity> overhead`, `<charity> program expense ratio`, `<charity> how much goes to charity`
- `is <charity> legit`, `is <charity> a 501c3`, `<charity> EIN`, `<charity> 990`
- `<charity> revenue`, `<charity> net assets`
- Roundups: `largest charities in <state>`, `largest <cause> charities`, `charities that raise the most`, `how to read a form 990`, `givingtuesday charity checklist`

**Discovery plumbing (all automated).** Sitemap with real last-modified dates; IndexNow submissions of changed URLs after every deploy (Bing, Yandex, Seznam, Naver; Bing feeds ChatGPT search and Copilot); JSON-LD (NGO with EIN, BreadcrumbList, Article, Dataset, WebSite search); Atom feed of new filings; clean HTML that AI answer engines can quote with a citation.

**Loops built into every page.** Share bar (native share, copy, X, LinkedIn, Facebook, e-mail) with a prefilled "Of every $100 X spent, $Y went to programs" line and a per-charity share card; an embed snippet (an iframe card for bloggers, local news and the charity itself); compare links; a public right-of-reply that gives charities a reason to visit and link to their page.

**Cross-links.** Every covered charity that received private-foundation grants (~17,900) links to its WHOFUNDS page. WHOFUNDS doesn't link back yet: that's a change for the WHOFUNDS session (see the hand-over notes), which would put links on thousands of already-indexed pages.

**GitHub.** Public repo with a description, topics (charity, nonprofit, form-990, irs, open-data, givingtuesday ...) and CC0 data releases that data people find and cite.

## 14-day machine calendar (D1 = first deploy, 2026-10-25)

| Day | What runs | Check |
|---|---|---|
| D1 | First deploy; IndexNow gets all ~25,000 charity URLs plus roundups | Health run green; IndexNow 200/202 in the deploy log |
| D1–D14, daily 08:29 UTC | Health: live checks, reply/correction sync | Actions tab green |
| D2 | Monday refresh: new IRS/data-lake filings fetched, pages for those charities updated, changed URLs to IndexNow | New release, `/updates/` lists the filings |
| D7 | Sunday self-test parses the newest filing from each source | Green |
| D9 | Monday refresh | As D2 |
| D14 | Sunday self-test | Green |
| ~D20–37 | GivingTuesday window (Dec 1): the GivingTuesday checklist and "largest charities" guides are the entry points | Search impressions in Bing (and Google once key 4 is set) |

What a human could add (not required): the domain (above), Search Console (key 4), analytics to measure activation (key 3), and a support link (key 2).
