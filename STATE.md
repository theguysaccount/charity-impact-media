# STATE: 2026-10-25

**Works:**
- Live on GitHub Pages: 25,343 charity pages (where $100 went and came from, scorecard with cause medians, pay by role, programs, governance answers, contractors, up to 7 filings of history, sources), causes, states, A–Z, compare, embed widget, 13 guides, CSV, feed, sitemap. Every figure cites its filing; every page has correction and right-of-reply links.
- Data: 149,983 Form 990 filings (TY2019–TY2025) from the GivingTuesday data lake plus 8,103 straight from IRS monthly zips by HTTP range request, including the IRS's Deflate64 zip the lake couldn't read. Zero fetch failures.
- Machine loop: weekly incremental refresh with a guard, deploy with IndexNow (25,297 URLs accepted), daily live health check with reply sync, Sunday live-source self-test, keep-alive on every scheduled workflow. 34 tests.

**Origin:** idea-only (one paragraph in a 2023 brainstorm). Built from scratch; IRS ingestion approach and person-name lists reused from WHOFUNDS.

**Known gaps:**
- People are never named, so "X CEO name" searches aren't served (deliberate; roles and pay are).
- Titles naming endowed positions or facilities keep those names (they're the role's name, not the holder's).
- Right of reply needs a GitHub account; no e-mail channel yet (key 6).
- No analytics, custom domain, Search Console or support link yet: all optional keys in OPERATIONS.md.
- ~2,600 of the smallest charities get the slim page layout to stay under the 1 GB Pages limit.

**Worth reusing:** `pipeline/irszip.py` + `inflate64.py` (read any single filing from the IRS monthly zips, including Deflate64, without downloading them), `pipeline/parse990.py` (Form 990 → compact record, privacy-safe), `scripts/keepalive.sh`, the size-budget slim fallback in `build_site.py`.
