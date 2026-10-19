"""BibTeX parsing and batch verification."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

from .http import Fetcher, fetch_json
from .verify import family_name, verify_reference

_BRACES = re.compile(r"[{}]")


def _clean(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", _BRACES.sub("", value)).strip() or None


def parse_bibtex(text: str) -> list[dict[str, Any]]:
    """Return entries as dicts with key, type, title, authors (family names), year, doi."""
    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode  # {\"u} -> ü, {\c{C}} -> Ç
    db = bibtexparser.loads(text, parser=parser)
    entries = []
    for e in db.entries:
        raw_authors = _clean(e.get("author")) or ""
        authors = [family_name(a) for a in re.split(r"\s+and\s+", raw_authors) if a.strip()]
        year_match = re.search(r"\d{4}", e.get("year", ""))
        entries.append(
            {
                "key": e.get("ID"),
                "type": e.get("ENTRYTYPE"),
                "title": _clean(e.get("title")),
                "authors": authors,
                "year": int(year_match.group(0)) if year_match else None,
                "doi": _clean(e.get("doi")),
            }
        )
    return entries


def verify_bibtex(text: str, fetch: Fetcher = fetch_json) -> dict[str, Any]:
    """Verify every entry in a BibTeX string and summarise the outcome."""
    results = []
    for entry in parse_bibtex(text):
        result = verify_reference(
            title=entry["title"],
            authors=entry["authors"] or None,
            year=entry["year"],
            doi=entry["doi"],
            fetch=fetch,
        )
        results.append({"key": entry["key"], **result})
    summary = Counter(r["status"] for r in results)
    return {"total": len(results), "summary": dict(summary), "entries": results}
