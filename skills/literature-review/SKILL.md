---
name: literature-review
description: Find, screen and organise literature on a research topic using Crossref, TR Dizin and OpenAlex, then produce a BibTeX file and a review table. Use when the user asks for related work, a literature search or review, sources on a topic, a reading list, or a .bib file for a topic, in Turkish or English.
---

# Literature review

Builds a literature set from bibliographic registries through the `akademik-ajan` MCP tools. Every work in the output comes from a tool response. Never add a work from memory, and never fill a missing field (pages, volume, DOI) yourself.

## Procedure

1. **Agree on scope in one line** if the user did not give it: topic, year range, languages (Turkish literature needs Turkish keywords), and the rough size wanted (default 15-25 works).
2. **Search with several query variants.** Registry ranking is lexical and noisy, so call `search_literature` 3-5 times:
   - the core English phrasing and one synonym phrasing;
   - for Turkish literature, the Turkish phrasing and a variant with a different suffix form (e.g. "siber güvenlik farkındalığı" and "siber güvenlik farkındalık");
   - narrower method or population terms when the topic is broad.
   Pass the year range to every call. Keep each call's `counts` and `unreachable` for the report.
3. **Merge** the results by DOI (or title when there is no DOI). Discard works with `relevance` below 0.5 unless their abstract is clearly on topic.
4. **Screen** each remaining work on its title and abstract against the scope. Record one reason per exclusion (off topic, wrong population, not peer reviewed, outside years). When a work has no abstract, keep it as "screen manually" rather than guessing.
5. **Export BibTeX** with `export_bibtex` for the included works that have DOIs. For included works without a DOI (typical for TR Dizin), write the entry from the search record fields only, with its TR Dizin `url`.
6. **Deliver**
   - `references.bib`
   - a review table (CSV or Markdown): key, year, authors, title, venue, method/data (from the abstract only), main finding (from the abstract only, or "abstract unavailable"), sources it was found in, citation count
   - a short search log: queries, year range, date, hits per source, duplicates removed, excluded with reasons, included. This is the PRISMA-style record a reviewer may ask for.

## Rules

- Summaries of method and findings come from the abstract returned by the tool. If the abstract does not say it, write "not stated in abstract".
- Citation counts differ by source and date; report them as "as of <date>, <source>".
- If a source is `unreachable`, say which one and that the set may be incomplete. Suggest setting `OPENALEX_API_KEY` when OpenAlex is the one missing.
- Before the user cites anything, offer to run the `verify-citations` skill on the final .bib.
