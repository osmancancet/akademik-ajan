"""MCP server exposing the citation-verification tools over stdio."""

from __future__ import annotations

from typing import Any

import anyio
from mcp.server.mcpserver import MCPServer

from . import __version__, bibtex, literature, response, verify

mcp = MCPServer(
    name="akademik-ajan",
    version=__version__,
    instructions=(
        "Academic tools backed by Crossref, OpenAlex and TR Dizin. Only report a citation as "
        "real when verify_reference returns 'verified'. Status 'error' means the "
        "service could not be reached and says nothing about whether a source exists."
    ),
)


@mcp.tool()
async def verify_reference(
    title: str | None = None,
    authors: list[str] | None = None,
    year: int | None = None,
    doi: str | None = None,
) -> dict[str, Any]:
    """Check one reference against Crossref, TR Dizin and OpenAlex.

    Give a DOI when the citation has one; otherwise give the title (and authors
    and year if known). Returns a status (verified, partial_match, mismatch,
    possible_match, doi_not_found, not_found, error), the matched record, and
    per-field checks.
    """
    return await anyio.to_thread.run_sync(
        lambda: verify.verify_reference(title=title, authors=authors, year=year, doi=doi)
    )


@mcp.tool()
async def verify_bibtex(bibtex_text: str) -> dict[str, Any]:
    """Verify every entry of a BibTeX file's contents and summarise the results."""
    return await anyio.to_thread.run_sync(lambda: bibtex.verify_bibtex(bibtex_text))


@mcp.tool()
async def lookup_doi(doi: str) -> dict[str, Any]:
    """Return the bibliographic record (title, authors, year, venue, abstract) for a DOI."""
    record = await anyio.to_thread.run_sync(lambda: verify.lookup_doi(doi))
    if record is None:
        return {"found": False, "doi": verify.normalize_doi(doi)}
    return {"found": True, "record": record.to_dict()}


@mcp.tool()
async def search_works(
    title: str, authors: list[str] | None = None, year: int | None = None, rows: int = 5
) -> list[dict[str, Any]]:
    """Search Crossref, then TR Dizin and OpenAlex if needed, for works matching a title."""
    rows = max(1, min(rows, 20))
    records = await anyio.to_thread.run_sync(
        lambda: verify.search_works(title, authors, year, rows=rows)
    )
    return [r.to_dict() for r in records]


@mcp.tool()
async def search_literature(
    query: str,
    from_year: int | None = None,
    to_year: int | None = None,
    per_source: int = 10,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """Search Crossref, TR Dizin and OpenAlex for works on a topic.

    Returns merged, de-duplicated works (title, authors, year, venue, DOI, abstract
    when available, citation count, and which sources found each one). Use Turkish
    keywords to reach Turkish-language literature in TR Dizin.
    """
    chosen = tuple(s for s in (sources or literature.SOURCES) if s in literature.SOURCES)
    return await anyio.to_thread.run_sync(
        lambda: literature.search_literature(query, from_year, to_year, per_source,
                                             chosen or literature.SOURCES)
    )


@mcp.tool()
async def export_bibtex(dois: list[str]) -> dict[str, Any]:
    """Generate BibTeX entries for DOIs from the registry records (never from memory)."""
    return await anyio.to_thread.run_sync(lambda: literature.export_bibtex(dois))


@mcp.tool()
async def render_response_letter(data: dict[str, Any], fmt: str = "markdown") -> dict[str, Any]:
    """Lay out a response-to-reviewers letter (Markdown or LaTeX) and a change-log table.

    `data` holds the title and, per reviewer, numbered points with the verbatim comment,
    the response, the changes and their location, and a status (addressed,
    partially_addressed, not_addressed, author_action). The result includes a `check`
    listing empty responses, placeholders and points that still need the authors.
    """
    return response.render_response_letter(data, fmt)


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
