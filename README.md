# Charity Impact Media: where the money goes

**Live:** https://theguysaccount.github.io/charity-impact-media/ · **Data (CC0):** [latest release](https://github.com/theguysaccount/charity-impact-media/releases/latest) · **Screens:** [desktop and phone](docs/screens/)

Sourced spending breakdowns of every US 501(c)(3) public charity with $10 million or more in revenue (about 25,000), built from each charity's own IRS Form 990 filings and refreshed as new filings post:

- **Where $100 of spending went**: programs, management and general, fundraising (Part IX).
- **Where $100 of revenue came from**: contributions, government grants, program service revenue, investment income (Part VIII).
- **The 990 scorecard**: the same twelve measures for every charity, each next to the median for its cause. No grades.
- **Highest reported compensation**, by role, with pay from related organizations and benefits (Part VII). People are never named.
- **Programs in the charity's own words**, governance answers, the largest outside contractors, up to seven years of trends, similar charities, and private-foundation funders via [WHOFUNDS](https://theguysaccount.github.io/whofunds-open-grant-graph/).

Every figure shows its filing year and links to the filing it came from. Every page has a public correction link and a right-of-reply for the charity. There are no ratings, ads, accounts or tracking cookies.

## How it runs (no human in the loop)

| What | Where | When |
|---|---|---|
| Fetch new filings, rebuild, test, guard, publish a data release | `.github/workflows/refresh.yml` | weekly; rebuilds only when an index, the BMF or the data code changed |
| Build the site from the latest release and deploy to GitHub Pages; IndexNow | `.github/workflows/deploy.yml` | after each refresh, on site changes, when new reply issues appear |
| Live site check, reply sync; weekly live source self-test | `.github/workflows/health.yml` | daily; self-test Sundays |
| Tests | `.github/workflows/test.yml` | every push |

Each job fails safe: nothing is published unless every step passes, and the live site keeps the last good build. Scheduled workflows keep themselves enabled (`scripts/keepalive.sh`). Details, alerting and the optional keys (custom domain, support link, analytics, Search Console): [OPERATIONS.md](OPERATIONS.md).

## Layout

```
pipeline/                 Python 3.9+, standard library only (Pillow optional, for share cards)
  sources.py              fingerprint the public inputs, download them, guard a rebuild
  select_filings.py       covered charities (IRS BMF + data-lake indexes) and every Form 990 they filed since 2019
  fetch_filings.py        fetch + parse into the cache: data lake over S3, IRS-only filings by HTTP range request
  irszip.py, inflate64.py read single members of the IRS monthly zips (incl. Deflate64) without downloading them
  parse990.py             Form 990 XML -> compact record; never reads personal names
  build_data.py           pick each year's return (amended wins), compute measures, medians, ranks
  render.py, pages.py     HTML templates (charity pages; home, causes, states, A-Z, guides, method, corrections)
  build_site.py           write dist/: pages, data.json, search index, sitemap, feed, CSV, IndexNow lists
  og_cards.py             1200x630 share cards ("Of every $100 spent")
  crosslinks.py           WHOFUNDS cross-links; replies.py: right-of-reply and correction issues by EIN
  indexnow.py, healthcheck.py
content/guides/           the guide backlog, with live-data placeholders
site/static/              app.css, app.js (search, share, compare, embed, chart tooltips, opt-in analytics), favicon
tests/                    unit, privacy, content-rule and build tests; test_live.py checks the live sources
```

## Run it locally

Inputs are public and anonymous; no keys.

```bash
python3 pipeline/sources.py check && python3 pipeline/sources.py download     # indexes + BMF, ~2.5 GB
python3 pipeline/select_filings.py                                            # ~25,000 charities, ~150,000 filings
python3 pipeline/fetch_filings.py --workers 48                                # ~30 min cold, resumable
python3 pipeline/build_data.py
CIM_BASE_URL=http://localhost:8765/charity-impact-media python3 pipeline/build_site.py
mkdir -p /tmp/serve && ln -sfn "$PWD/dist" /tmp/serve/charity-impact-media && python3 -m http.server 8765 --directory /tmp/serve
```

## Test

```bash
python3 -m unittest discover -s tests -v              # parser, privacy, measures, Deflate64, guard, full site build + content rules
CIM_LIVE=1 python3 -m unittest tests.test_live -v     # parse the newest filing from each live source
node scripts/screens.mjs <site url>                   # screenshots at 1280px and a real 390px mobile viewport -> docs/screens/
```

## Content rules (enforced in code and tests)

- Figures are copied from the filing or are ratios of two lines of the same filing, with the part and line named.
- Every figure links to its filing; the test fails on any uncited dollar amount or percentage.
- No rating language and no status colors; medians are labelled as context.
- Names of people never reach the cache or the site: roles only, business contractors only.
- Every page has a correction link and a right-of-reply link.

## Sources

IRS Form 990 e-file data from the [GivingTuesday 990 Data Lake](https://990data.givingtuesday.org/) and the [IRS Form 990 series downloads](https://www.irs.gov/charities-non-profits/form-990-series-downloads); the [IRS Exempt Organizations Business Master File](https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf). Filings are public under 26 U.S.C. § 6104. Filing pages link to [ProPublica Nonprofit Explorer](https://projects.propublica.org/nonprofits/).

## Licence

CC0 1.0 for data and code. See [LICENSE](LICENSE).
