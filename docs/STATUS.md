# Status

Single source of truth for what works. Anything not listed as **working** does not exist yet.

_Last updated: 2026-10-20 · v0.1.0_

| Component | State | Evidence |
|---|---|---|
| `verify_reference` (DOI path) | working | unit tests; live check: real DOI → `verified`, invented DOI → `doi_not_found`, real DOI + wrong title → `mismatch` |
| `verify_reference` (title search) | working | unit tests; live check: "Deep learning", LeCun, 2015 → `verified` (10.1038/nature14539) |
| `verify_bibtex` | working | unit tests incl. LaTeX-escaped Turkish titles/authors |
| `lookup_doi`, `search_works` | working | unit tests |
| OpenAlex fallback | working | unit tests (live path not yet exercised) |
| `verify-citations` skill | working | manual review; not yet evaluated end-to-end |
| Claim ↔ abstract support check | partial | done by the model from `lookup_doi` abstracts; no automated eval yet |
| Literature review module | planned | — |
| Reviewer-response module | planned | — |
| Journal compliance module | planned | — |
| TR↔EN terminology module | planned | — |

## Known limitations

- Title similarity uses `difflib`; very short or generic titles ("Introduction") can produce false `possible_match`.
- Crossref's year can differ from the print year by one; reported as `partial_match`, not failure.
- Works without a DOI that are absent from both Crossref and OpenAlex (some Turkish journals, theses in YÖK Tez) come back `not_found`. A DergiPark / YÖK Tez source is a candidate for v0.2.

## Not yet measured

- Token/latency overhead of the plugin in a Claude Code session.
- Detection rate on a labelled set of real vs. fabricated references.
