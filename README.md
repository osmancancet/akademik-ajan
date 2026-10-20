# akademik-ajan

An academic agent toolkit for [Claude Code](https://claude.com/claude-code), built around one rule: **nothing reaches a manuscript unless it was checked against a real source.**

> Status: **v0.2.0 — early.** Only what is listed as *working* in [docs/STATUS.md](docs/STATUS.md) works. No stubs, no placeholder tools.

## What works today

**Citation verification** (`verify-citations` skill + MCP server)

- Checks a DOI, or a title/author/year, against **Crossref**, **TR Dizin** (Turkish national index) and **OpenAlex**.
- Matches Turkish and English titles of the same bilingual article, and tolerant author-name layouts ("Last, F.", compound surnames).
- Catches the classic fabricated reference: a plausible title attached to a real DOI that belongs to another paper (`mismatch`).
- Verifies a whole `.bib` file in one call, including LaTeX-escaped Turkish characters.
- Distinguishes "the service was unreachable" (`error`) from "this work does not exist" (`not_found`).

| Tool | Purpose |
|---|---|
| `verify_reference` | Verify one reference; returns status, matched record and per-field checks |
| `verify_bibtex` | Verify every entry of a BibTeX text |
| `lookup_doi` | Fetch the record (incl. abstract when available) for a DOI |
| `search_works` | Bibliographic search by title/authors/year |

**Literature review** (`literature-review` skill)

- Searches Crossref, TR Dizin and OpenAlex at once, merges duplicates, records which source found each work, and ranks by a relevance score that copes with Turkish suffixes.
- Exports BibTeX built only from registry fields; a missing page range stays missing.
- The skill runs several query variants, screens on abstracts and returns a `.bib`, a review table and a search log (hits per source, exclusions with reasons).

| Tool | Purpose |
|---|---|
| `search_literature` | Topic search with year range; merged, de-duplicated works with provenance and relevance |
| `export_bibtex` | BibTeX entries for a list of DOIs |

## Install

Requires [uv](https://docs.astral.sh/uv/) and Python ≥ 3.11.

Inside Claude Code:

```
/plugin marketplace add osmancancet/akademik-ajan
/plugin install akademik-ajan@akademik-ajan
```

The plugin writes nothing to your global settings. It adds one MCP server and two skills.

Optional environment variables:

| Variable | Effect |
|---|---|
| `AKADEMIK_AJAN_MAILTO` | Your e-mail; puts Crossref requests in its faster "polite pool" |
| `OPENALEX_API_KEY` | Free OpenAlex key. Without it OpenAlex shares a small daily budget per IP address; when that runs out the verifier still works with Crossref and TR Dizin and reports OpenAlex under `unchecked_sources` |

## Develop

```bash
cd server
uv sync --extra dev
uv run pytest
```

Tests run offline against canned API responses.

## Research

`eval/llm/` holds a study of references written by language models: the fixed prompt protocol, raw model outputs, blind web adjudication and the scripts that produce every number ([report](eval/llm/REPORT.md), [design](docs/adr/0003-llm-reference-study.md)).

## Design principles

See [docs/adr/0001-scope-and-principles.md](docs/adr/0001-scope-and-principles.md). In short: few features that genuinely work, pinned dependencies, no global side effects, measured token cost, and real sources only.

## Roadmap

1. ✅ Citation verifier — live eval on an unseen set: 99% of real references accepted, 100% of synthetic fabrications caught ([details](docs/STATUS.md#live-evaluation-2026-10-20))
2. ✅ Literature review: search → BibTeX → review table
3. Reviewer-response assistant
4. Journal compliance check (APA/IEEE, word limits, structure)
5. Turkish ↔ English academic terminology consistency

## License

MIT © Osman Can Çetlenbik
