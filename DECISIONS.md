# DECISIONS

Each entry: the decision, why, and what would change it. Newest at the bottom.

### D1. Media and data product first; no ratings, no consulting
The idea note mixes a media outlet, a ratings product and a consultancy. v1 is the media/data product only: sourced breakdowns of what charities report. No scores, grades or "good/bad" labels anywhere, and no consulting (the build prompt cuts it, and consulting for charities we cover would be a conflict of interest).
*Would change if* an audience exists and Jack wants a paid research or advisory line; it would need a separate brand and a published conflict policy.

### D2. The "scorecard" is a consistent fact sheet, not a score
The machine loop asks for "one published scorecard". It's twelve measures computed the same way for every charity (program/management/fundraising shares, fundraising cost per $1, revenue shares, highest compensation and its share of expenses, people over $100k, net assets in months, independent board share), each shown with the category median. The median is context; the copy says so on every page, and colors are categorical, never red/green.

### D3. Coverage: 501(c)(3) public charities with $10M+ revenue on their latest Form 990
That is ~25,000 organizations: every charity most donors look up by name, plus the hospitals and universities people search for executive pay. The latest filing must be within the last three complete tax years and the EIN must be in the current IRS BMF. Form 990-EZ/990-N filers and private foundations aren't covered (WHOFUNDS covers foundations).
*Would change if* search data shows demand below $10M: lower `CIM_MIN_REVENUE`; the slim layout keeps the site within Pages' 1 GB.

### D4. Sources: GivingTuesday data lake for bulk, IRS monthly zips for freshness
The data lake serves each filing as its own S3 object, which makes a 150,000-filing backfill a 30-minute job. Its index lags the IRS by months: the 2026-08-25 build had none of the IRS's August and September 2026 batches and only half of May. Filings the lake lacks are read straight out of the IRS's monthly zips with HTTP range requests (central directory, then one member), so the weekly job is current to the IRS's latest release without downloading multi-GB zips. Both are anonymous and keyless.

### D5. One filing per charity per tax year, latest return wins
An amended return supersedes the original. Across the two sources, the parsed return with the later `ReturnTs` wins, so an IRS-only amendment replaces a data-lake original. Trend tables show which years were amended.

### D6. People are never named
Form 990 Part VII names officers and their pay; that's public record, but the build prompt rules out publishing personal data. Pages list compensation by role ("President & CEO"), and the parser never reads `PersonNm`, the principal officer, the books-in-care-of contact or phone numbers. Titles are scrubbed of embedded names (Census given-name and surname lists, from WHOFUNDS), and contractors are listed only when they are businesses whose names can't be a person ("Jane Doe Consulting LLC" is left out). Every page links the filing, where anyone can read the names. Tests assert that names in fixture filings never reach the output. Titles that name an endowed position or a facility ("Peter Jay Sharp Chief Curator", "President, Moses Cone Hospital") stay as filed: they're the role's official name, not the holder's.

### D7. Every figure cites its filing
Figures link to the page's source list entry for their filing year (`#f2024`), which links the filing on ProPublica Nonprofit Explorer and, for data-lake filings, the raw IRS XML. The trend table cites per row (each row starts with its filing link). A test strips citations from each figure section and fails if any dollar amount or percentage is left uncited.

### D8. Static site on GitHub Pages, built by Actions, Python standard library only
No server, no database, no third-party keys. ~25,000 static charity pages (full HTML, crawlable) plus a per-charity `data.json` for compare and the embed widget, client-side search over one JSON index, and sitemaps. Locally only Python 3.9 exists, so the whole pipeline and the site build are stdlib Python; Pillow is used only in CI for share cards and is optional.

### D9. Fit the 1 GB Pages limit by degrading the long tail, not by failing
Full pages average ~29 KB. If the HTML would exceed 700 MB, the build re-renders the smallest charities' pages in a slim layout (no trend chart, contractors, similar list or FAQ; scorecard, sources and right of reply stay) until it fits. Share cards (~18 KB each) are made for the 3,000 charities with the most contributions; the rest use the site card.

### D10. Right of reply and corrections are public GitHub issues
Issue forms (`correction.yml`, `reply.yml`) are prefilled from each page. A daily job maps issues to EINs and links them from the page without copying their text, so we never republish unvetted claims; `invalid`/`spam` labels remove a link. It requires a GitHub account, which is acceptable friction for v1 (a monitored e-mail address is a key in OPERATIONS.md).

### D11. Display names come from the latest filing; DBA names are searchable
The filer name on the most recent return (smart-cased when all caps) is the display name; the `DoingBusinessAsName` is shown as "also known as" and indexed for search. URLs use the EIN (`/charity/530196605/`), which never changes when a name does, and matches WHOFUNDS's `/org/<ein>/`.

### D12. Distribution is machine-only
Sitemap with real `lastmod` dates, IndexNow on every deploy (changed URLs only), JSON-LD (NGO, BreadcrumbList, Article, Dataset, WebSite SearchAction), per-charity Open Graph cards, an Atom feed of new filings, an embeddable widget and a share bar on every page, cross-links to WHOFUNDS, a CC0 CSV, and a discoverable repo (description, topics). No posting or outreach.

### D13. Home page features operating charities
The "where $100 went at the charities that raise the most" list leaves out cause T (grantmakers) and donor-advised fund sponsors that mostly pass money through as grants: Fidelity Charitable and its peers top every contributions ranking but aren't what a donor means by "a charity". They're covered and explained in the DAF guide.

### D14. Brand: "Charity Impact Media"
The venture's own name, used until Jack picks a domain. "EffectiveCharities" was the alternative but implies a judgment of effectiveness, which the no-ratings rule rules out.

### D15. Narratives: deterministic summaries now, a guide backlog, a routine later
Each page's "In brief" paragraph is generated from the data (no adjectives about quality). Thirteen guides are pre-written in `content/guides/` with live-data placeholders that refresh every deploy. Recurring AI-written content can't run in Actions (no API key), so OPERATIONS.md specifies a monthly Claude routine that opens PRs with new guides.
