# Changelog

## 0.2.0 — 2026-10-20

### Added
- **Reviewer response module.** `render_response_letter` tool (Markdown or LaTeX letter, change log, completeness check with an author to-do list) and `reviewer-response` skill.
- **Literature review module.** `search_literature` (Crossref, TR Dizin, OpenAlex; merged, de-duplicated, with provenance and a lexical relevance score that handles Turkish suffixes) and `export_bibtex` (BibTeX built field by field from registry records). New `literature-review` skill.
- **TR Dizin** as a verification source (DOI and title search; bilingual titles matched).
- **LLM reference study** (`eval/llm/`): fixed protocol, raw outputs, scorer, blind web adjudication, `analyze.py` producing `numbers.json`, and `generate.py` for the clean API condition.
- Optional `OPENALEX_API_KEY`; OpenAlex quota exhaustion fails fast and is reported as `unchecked_sources`.

### Fixed
- A citation that uses the print year of an article published online years earlier is no longer a `mismatch` (all reported years are accepted). Found by blind adjudication.
- Author matching tolerates full names in family fields and compound surnames.
- An unreachable fallback source no longer turns a result into `error`; an unknown DOI with an unreachable source is `error`, not `doi_not_found`.
- 429/503 responses are retried with back-off.

## 0.1.0 — 2026-10-20

- Citation verifier (`verify_reference`, `verify_bibtex`, `lookup_doi`, `search_works`) over Crossref and OpenAlex, `verify-citations` skill, offline tests, synthetic evaluation.
