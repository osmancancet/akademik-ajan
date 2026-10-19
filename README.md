# akademik-ajan

An academic agent toolkit for [Claude Code](https://claude.com/claude-code), built around one rule: **nothing reaches a manuscript unless it was checked against a real source.**

> Status: **v0.1.0 — early.** Only what is listed as *working* in [docs/STATUS.md](docs/STATUS.md) works. No stubs, no placeholder tools.

## What works today

**Citation verification** (`verify-citations` skill + MCP server)

- Checks a DOI, or a title/author/year, against **Crossref**, falling back to **OpenAlex**.
- Catches the classic fabricated reference: a plausible title attached to a real DOI that belongs to another paper (`mismatch`).
- Verifies a whole `.bib` file in one call, including LaTeX-escaped Turkish characters.
- Distinguishes "the service was unreachable" (`error`) from "this work does not exist" (`not_found`).

| Tool | Purpose |
|---|---|
| `verify_reference` | Verify one reference; returns status, matched record and per-field checks |
| `verify_bibtex` | Verify every entry of a BibTeX text |
| `lookup_doi` | Fetch the record (incl. abstract when available) for a DOI |
| `search_works` | Bibliographic search by title/authors/year |

## Install

Requires [uv](https://docs.astral.sh/uv/) and Python ≥ 3.11.

Inside Claude Code:

```
/plugin marketplace add osmancancet/akademik-ajan
/plugin install akademik-ajan@akademik-ajan
```

The plugin writes nothing to your global settings. It adds one MCP server and one skill.

Optional: set `AKADEMIK_AJAN_MAILTO=you@university.edu` so requests use Crossref's polite pool.

## Develop

```bash
cd server
uv sync --extra dev
uv run pytest
```

Tests run offline against canned API responses.

## Design principles

See [docs/adr/0001-scope-and-principles.md](docs/adr/0001-scope-and-principles.md). In short: few features that genuinely work, pinned dependencies, no global side effects, measured token cost, and real sources only.

## Roadmap

1. ✅ Citation verifier
2. Literature review: search → BibTeX → review table
3. Reviewer-response assistant
4. Journal compliance check (APA/IEEE, word limits, structure)
5. Turkish ↔ English academic terminology consistency

## License

MIT © Osman Can Çetlenbik
