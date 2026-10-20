"""Literature search across Crossref, TR Dizin and OpenAlex, plus BibTeX export.

Everything returned here comes from an API response. BibTeX entries are generated
from those records field by field; nothing is filled in from model knowledge, so a
missing volume or page range stays missing.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .http import Fetcher, build_url, fetch_json
from .verify import (
    CROSSREF,
    OPENALEX,
    Record,
    _fold,
    _trdizin_query,
    lookup_doi,
    normalize_doi,
    parse_crossref,
    parse_openalex,
)

SOURCES = ("crossref", "trdizin", "openalex")


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #


def _crossref_topic(query: str, rows: int, y0: int | None, y1: int | None,
                    fetch: Fetcher) -> list[Record]:
    filters = ["type:journal-article", "type:proceedings-article"]
    if y0:
        filters.append(f"from-pub-date:{y0}")
    if y1:
        filters.append(f"until-pub-date:{y1}")
    url = build_url(CROSSREF, {"query": query, "rows": rows, "filter": ",".join(filters)})
    status, data = fetch(url)
    items = (data or {}).get("message", {}).get("items") if status == 200 else None
    return [parse_crossref(i) for i in items or []]


def _openalex_topic(query: str, rows: int, y0: int | None, y1: int | None,
                    fetch: Fetcher) -> list[Record]:
    filters = []
    if y0:
        filters.append(f"from_publication_date:{y0}-01-01")
    if y1:
        filters.append(f"to_publication_date:{y1}-12-31")
    url = build_url(OPENALEX, {"search": query, "per-page": rows, "filter": ",".join(filters)})
    status, data = fetch(url)
    results = (data or {}).get("results") if status == 200 else None
    return [parse_openalex(r) for r in results or []]


def _trdizin_topic(query: str, rows: int, y0: int | None, y1: int | None,
                   fetch: Fetcher) -> list[Record]:
    # The endpoint returns a relevance-ranked page; the year range is applied here.
    return [
        r for r in _trdizin_query(query, fetch)
        if (y0 is None or (r.year or 0) >= y0) and (y1 is None or (r.year or 9999) <= y1)
    ][:rows]


_SEARCHERS = {"crossref": _crossref_topic, "trdizin": _trdizin_topic, "openalex": _openalex_topic}


def _key(r: Record) -> str:
    return r.doi or f"t:{_fold(r.title)}"


_STOP = {"and", "the", "for", "with", "from", "into", "ile", "bir", "ve", "veya", "icin", "olan",
         "uzerine", "uzerinde", "of", "in", "on", "to", "a", "an", "de", "da"}


def _stem(token: str) -> str:
    # Crude prefix stem: Turkish suffixes ("farkındalığı", "farkındalık") share a prefix.
    return token[:6] if len(token) > 6 else token


def relevance(query: str, rec: Record) -> float:
    """Share of query terms found in the title (weight 1) or only the abstract (weight 0.5)."""
    terms = [_stem(t) for t in _fold(query).split() if t not in _STOP and len(t) > 1]
    if not terms:
        return 0.0
    title_words = [w for t in rec.titles() for w in _fold(t).split()]
    abstract_words = _fold(rec.abstract or "").split()
    score = 0.0
    for term in terms:
        if any(w.startswith(term) for w in title_words):
            score += 1.0
        elif any(w.startswith(term) for w in abstract_words):
            score += 0.5
    return round(score / len(terms), 2)


def search_literature(
    query: str,
    from_year: int | None = None,
    to_year: int | None = None,
    per_source: int = 10,
    sources: tuple[str, ...] = SOURCES,
    fetch: Fetcher = fetch_json,
) -> dict[str, Any]:
    """Search each source, merge duplicates (same DOI or same folded title), keep provenance.

    Results interleave the sources' own relevance rankings. A source that cannot be
    reached is listed under `unreachable` instead of failing the whole search.
    """
    per_source = max(1, min(per_source, 50))
    ranked: dict[str, list[Record]] = {}
    unreachable: list[str] = []
    for name in sources:
        try:
            ranked[name] = _SEARCHERS[name](query, per_source, from_year, to_year, fetch)
        except ConnectionError:
            unreachable.append(name)
            ranked[name] = []

    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    depth = max((len(v) for v in ranked.values()), default=0)
    for i in range(depth):
        for name in sources:
            if i >= len(ranked[name]):
                continue
            rec = ranked[name][i]
            k = _key(rec)
            if k in merged:
                entry = merged[k]
                entry["found_in"].append(name)
                _fill_gaps(entry["record"], rec)
            else:
                merged[k] = {"record": rec, "found_in": [name]}
                order.append(k)

    works = []
    for pos, k in enumerate(order):
        rec = merged[k]["record"]
        d = rec.to_dict()
        d["found_in"] = merged[k]["found_in"]
        d["relevance"] = relevance(query, rec)
        works.append((d["relevance"], -pos, d))
    # Lexical relevance first; the sources' own interleaved ranking breaks ties.
    works = [d for _, _, d in sorted(works, key=lambda t: (t[0], t[1]), reverse=True)]
    return {
        "query": query,
        "year_range": [from_year, to_year],
        "counts": {name: len(ranked[name]) for name in sources},
        "unique": len(works),
        "unreachable": unreachable,
        "works": works,
    }


def _fill_gaps(target: Record, other: Record) -> None:
    """Complete empty fields of `target` from another source's record of the same work."""
    for attr in ("doi", "venue", "abstract", "volume", "issue", "pages", "publisher", "url"):
        if not getattr(target, attr) and getattr(other, attr):
            setattr(target, attr, getattr(other, attr))
    if not target.author_names and other.author_names:
        target.author_names = other.author_names
    if target.cited_by is None or (other.cited_by or 0) > target.cited_by:
        target.cited_by = other.cited_by if other.cited_by is not None else target.cited_by
    for t in other.titles():
        if t not in target.titles():
            target.alt_titles.append(t)


# --------------------------------------------------------------------------- #
# BibTeX
# --------------------------------------------------------------------------- #

_TEX_SPECIAL = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_"}
_BIB_TYPE = {"article": "article", "inproceedings": "inproceedings", "book": "book",
             "chapter": "incollection", "thesis": "phdthesis"}


def _tex(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("{", "").replace("}", "")
    return "".join(_TEX_SPECIAL.get(c, c) for c in text)


def _ascii(text: str) -> str:
    text = text.replace("ı", "i").replace("İ", "I")
    text = unicodedata.normalize("NFKD", text)
    return re.sub(r"[^A-Za-z0-9]", "", "".join(c for c in text if not unicodedata.combining(c)))


def cite_key(rec: Record, taken: set[str]) -> str:
    family = rec.authors[0] if rec.authors else "anon"
    word = next((w for w in re.findall(r"\w+", rec.title) if len(w) > 3), "work")
    base = (_ascii(family).lower() or "anon") + str(rec.year or "nd") + _ascii(word).lower()
    key, n = base, 0
    while key in taken:
        n += 1
        key = f"{base}{chr(ord('a') + n - 1)}" if n <= 26 else f"{base}{n}"
    taken.add(key)
    return key


def to_bibtex(rec: Record, key: str) -> str:
    entry = _BIB_TYPE.get(rec.kind or "", "misc")
    fields: list[tuple[str, str | None]] = [
        ("author", " and ".join(_tex(a) for a in (rec.author_names or rec.authors) if a) or None),
        ("title", "{" + _tex(rec.title) + "}" if rec.title else None),  # {{...}} keeps capitals
    ]
    venue = _tex(rec.venue) if rec.venue else None
    if entry == "article":
        fields.append(("journal", venue))
    elif entry in ("inproceedings", "incollection"):
        fields.append(("booktitle", venue))
    elif entry == "misc" and venue:
        fields.append(("howpublished", venue))
    fields += [
        ("year", str(rec.year) if rec.year else None),
        ("volume", _tex(str(rec.volume)) if rec.volume else None),
        ("number", _tex(str(rec.issue)) if rec.issue else None),
        ("pages", _tex(str(rec.pages)) if rec.pages else None),
        ("publisher", _tex(rec.publisher) if rec.publisher and entry == "book" else None),
        ("doi", rec.doi),
        ("url", rec.url if not rec.doi and rec.url else None),
    ]
    body = ",\n".join(f"  {name} = {{{value}}}" for name, value in fields if value)
    return f"@{entry}{{{key},\n{body}\n}}"


def export_bibtex(dois: list[str], fetch: Fetcher = fetch_json) -> dict[str, Any]:
    """Build BibTeX for a list of DOIs, each resolved through the verifier's sources."""
    entries, missing, unreachable = [], [], []
    taken: set[str] = set()
    seen: set[str] = set()
    for raw in dois:
        doi = normalize_doi(raw)
        if not doi or doi in seen:
            if not doi:
                missing.append(raw)
            continue
        seen.add(doi)
        try:
            rec = lookup_doi(doi, fetch)
        except ConnectionError:
            unreachable.append(doi)
            continue
        if rec is None:
            missing.append(doi)
            continue
        entries.append(to_bibtex(rec, cite_key(rec, taken)))
    return {
        "bibtex": "\n\n".join(entries) + ("\n" if entries else ""),
        "count": len(entries),
        "not_found": missing,
        "unreachable": unreachable,
    }
