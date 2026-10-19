# ADR-0001: Scope and principles

- Status: accepted
- Date: 2026-10-20

## Context

General agent harnesses for Claude Code (e.g. Ruflo / claude-flow) advertise hundreds of tools. Independent audits have found that most of those tools have no working backend, that a bare install adds tens of thousands of tokens per session, and that installers silently edit user-global files such as `~/.claude/CLAUDE.md`. Academic users need something narrower and trustworthy, above all protection against fabricated citations.

## Decision

1. **Only working features ship.** Planned work lives in the roadmap and `docs/STATUS.md`, never as stub tools.
2. **No global side effects.** The plugin adds one MCP server and its skills; it writes nothing outside its own directory.
3. **Pinned dependencies, minimal surface.** Runtime deps are `mcp` and `bibtexparser`, pinned exactly; HTTP uses the standard library.
4. **Real sources only.** Bibliographic facts come from Crossref/OpenAlex (later DergiPark, YÖK Tez). The model may judge, but never supplies bibliographic data from memory.
5. **Failure is explicit.** A network error is reported as `error`, distinct from `not_found`.
6. **Measured cost.** Token and latency overhead will be measured and published before v1.0.
7. **Architecture.** A Claude Code plugin (skills + few subagents) plus one MCP server for academic APIs. Conversation language with the maintainer is Turkish; code and docs are English.

## Consequences

Fewer advertised features, but each is testable. Every new module needs tests and an entry in `STATUS.md` with evidence before it is called working.
