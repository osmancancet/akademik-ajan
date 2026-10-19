"""Citation verification against Crossref, TR Dizin and OpenAlex.

The core rule of this module: a reference is only called "verified" when a
real bibliographic record was retrieved and the fields the user supplied agree
with it. Network failures are reported as errors, never as "not found", so a
flaky connection can't be mistaken for a fabricated citation.

Source order
  DOI given:   Crossref -> OpenAlex -> TR Dizin
  title only:  Crossref; if no confident match, TR Dizin; if still none, OpenAlex.
TR Dizin (ULAKBİM's national index) covers many Turkish journals that are
missing from, or poorly represented in, the international indexes.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
import urllib.parse
from dataclasses import asdict, dataclass, field
from typing import Any

from .http import Fetcher, build_url, fetch_json

CROSSREF = "https://api.crossref.org/works"
OPENALEX = "https://api.openalex.org/works"
TRDIZIN = "https://search.trdizin.gov.tr/api/defaultSearch/publication/"
TRDIZIN_PAGE = "https://search.trdizin.gov.tr/tr/yayin/detay/{id}"

TITLE_MATCH = 0.90  # at or above: same work
TITLE_CLOSE = 0.75  # between CLOSE and MATCH: probably same work, needs a human look

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Record:
    source: str
    doi: str | None
    title: str
    authors: list[str] = field(default_factory=list)  # family names, in order
    year: int | None = None
    venue: str | None = None
    abstract: str | None = None
    alt_titles: list[str] = field(default_factory=list)  # e.g. the English title of a Turkish paper
    url: str | None = None

    def titles(self) -> list[str]:
        return [t for t in [self.title, *self.alt_titles] if t]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if d["abstract"] and len(d["abstract"]) > 1500:
            d["abstract"] = d["abstract"][:1500] + "…"
        return {k: v for k, v in d.items() if v not in (None, [])}


# --------------------------------------------------------------------------- #
# Normalisation helpers
# --------------------------------------------------------------------------- #


def normalize_doi(value: str | None) -> str | None:
    """Extract a bare, lower-cased DOI from a DOI string, URL or citation text."""
    if not value:
        return None
    match = _DOI_RE.search(urllib.parse.unquote(value))
    if not match:
        return None
    return match.group(0).rstrip(".,;:)]}").lower()


def _fold(text: str) -> str:
    """Lower-case, strip diacritics (ç→c, ğ→g, ı→i) and punctuation."""
    text = text.replace("ı", "i").replace("İ", "I")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def title_similarity(a: str, b: str) -> float:
    fa, fb = _fold(a), _fold(b)
    if not fa or not fb:
        return 0.0
    return round(difflib.SequenceMatcher(None, fa, fb).ratio(), 3)


def best_title_similarity(claimed: str, record: Record) -> float:
    return max((title_similarity(claimed, t) for t in record.titles()), default=0.0)


def family_name(author: str) -> str:
    """Best-effort family name from 'Last, First' or 'First Last'."""
    author = author.strip().strip("{}")
    if "," in author:
        return author.split(",", 1)[0].strip()
    parts = author.split()
    return parts[-1] if parts else ""


# --------------------------------------------------------------------------- #
# Source parsers
# --------------------------------------------------------------------------- #


def _crossref_year(msg: dict[str, Any]) -> int | None:
    for key in ("issued", "published-print", "published-online", "published", "created"):
        parts = (msg.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            return int(parts[0][0])
    return None


def parse_crossref(msg: dict[str, Any]) -> Record:
    titles = msg.get("title") or [""]
    venues = msg.get("container-title") or [None]
    abstract = msg.get("abstract")
    if abstract:
        abstract = re.sub(r"\s+", " ", _TAG_RE.sub(" ", abstract)).strip()
    doi = normalize_doi(msg.get("DOI"))
    return Record(
        source="crossref",
        doi=doi,
        title=titles[0] or "",
        alt_titles=[t for t in (msg.get("original-title") or []) + (msg.get("subtitle") or []) if t],
        authors=[a.get("family") or a.get("name") or "" for a in msg.get("author") or []],
        year=_crossref_year(msg),
        venue=venues[0],
        abstract=abstract or None,
        url=f"https://doi.org/{doi}" if doi else None,
    )


def _openalex_abstract(index: dict[str, list[int]] | None) -> str | None:
    if not index:
        return None
    positions = [(pos, word) for word, idxs in index.items() for pos in idxs]
    return " ".join(word for _, word in sorted(positions)) or None


def parse_openalex(work: dict[str, Any]) -> Record:
    source = ((work.get("primary_location") or {}).get("source") or {})
    return Record(
        source="openalex",
        doi=normalize_doi(work.get("doi")),
        title=work.get("display_name") or work.get("title") or "",
        authors=[
            family_name((a.get("author") or {}).get("display_name") or "")
            for a in work.get("authorships") or []
        ],
        year=work.get("publication_year"),
        venue=source.get("display_name"),
        abstract=_openalex_abstract(work.get("abstract_inverted_index")),
        url=work.get("id"),
    )


def parse_trdizin(src: dict[str, Any]) -> Record:
    """Parse one TR Dizin hit (`_source`). Each language version carries its own title."""
    versions = src.get("abstracts") or []
    titles = [v.get("title", "").strip() for v in versions]
    titles = [t for t in titles if len(t) > 2]  # TR Dizin uses "-" for missing titles
    abstract = next((v.get("abstract") for v in versions if v.get("abstract")), None)
    authors = sorted(src.get("authors") or [], key=lambda a: a.get("order") or 0)
    journal = src.get("journal") if isinstance(src.get("journal"), dict) else {}
    year = src.get("publicationYear")
    return Record(
        source="trdizin",
        doi=normalize_doi(src.get("doi")),
        title=titles[0] if titles else "",
        alt_titles=titles[1:],
        authors=[family_name(a.get("inPublicationName") or a.get("name") or "") for a in authors],
        year=int(year) if year else None,
        venue=journal.get("name"),
        abstract=abstract,
        url=TRDIZIN_PAGE.format(id=src["id"]) if src.get("id") else None,
    )


# --------------------------------------------------------------------------- #
# Source queries
# --------------------------------------------------------------------------- #


def _crossref_doi(doi: str, fetch: Fetcher) -> Record | None:
    status, data = fetch(f"{CROSSREF}/{urllib.parse.quote(doi, safe='/')}")
    if status == 200 and data and data.get("message"):
        return parse_crossref(data["message"])
    return None


def _openalex_doi(doi: str, fetch: Fetcher) -> Record | None:
    status, data = fetch(f"{OPENALEX}/https://doi.org/{urllib.parse.quote(doi, safe='/')}")
    if status == 200 and data:
        return parse_openalex(data)
    return None


def _trdizin_query(query: str, fetch: Fetcher) -> list[Record]:
    url = build_url(TRDIZIN, {"q": query, "order": "relevance-DESC", "page": 1})
    status, data = fetch(url)
    hits = ((data or {}).get("hits") or {}).get("hits") if status == 200 else None
    return [parse_trdizin(h["_source"]) for h in hits or [] if h.get("_source")]


def _trdizin_doi(doi: str, fetch: Fetcher) -> Record | None:
    return next((r for r in _trdizin_query(doi, fetch) if r.doi == doi), None)


def _crossref_search(query: str, rows: int, fetch: Fetcher) -> list[Record]:
    status, data = fetch(build_url(CROSSREF, {"query.bibliographic": query, "rows": rows}))
    items = (data or {}).get("message", {}).get("items") if status == 200 else None
    return [parse_crossref(i) for i in items or []]


def _openalex_search(title: str, rows: int, fetch: Fetcher) -> list[Record]:
    status, data = fetch(build_url(OPENALEX, {"search": title, "per-page": rows}))
    results = (data or {}).get("results") if status == 200 else None
    return [parse_openalex(r) for r in results or []]


# --------------------------------------------------------------------------- #
# Public lookups
# --------------------------------------------------------------------------- #


def lookup_doi(doi: str, fetch: Fetcher = fetch_json) -> Record | None:
    """Resolve a DOI via Crossref, then OpenAlex, then TR Dizin. None if nobody knows it."""
    bare = normalize_doi(doi)
    if not bare:
        return None
    for resolver in (_crossref_doi, _openalex_doi, _trdizin_doi):
        record = resolver(bare, fetch)
        if record is not None:
            return record
    return None


def search_works(
    title: str,
    authors: list[str] | None = None,
    year: int | None = None,
    rows: int = 5,
    fetch: Fetcher = fetch_json,
) -> list[Record]:
    """Tiered search, best candidates first.

    Crossref is queried first. TR Dizin, then OpenAlex, are only consulted when
    nothing so far matches the title confidently, which keeps request volume low.
    """
    query = " ".join([title, *(family_name(a) for a in authors or [])])
    if year:
        query += f" {year}"

    found: list[Record] = []
    seen: set[str] = set()

    def add(records: list[Record]) -> float:
        for r in records:
            key = r.doi or f"{r.source}:{_fold(r.title)}"
            if key not in seen:
                seen.add(key)
                found.append(r)
        return max((best_title_similarity(title, r) for r in found), default=0.0)

    best = add(_crossref_search(query, rows, fetch))
    if best < TITLE_MATCH:
        best = add(_trdizin_query(title, fetch)[:rows])
    if best < TITLE_MATCH:
        add(_openalex_search(title, rows, fetch))

    found.sort(key=lambda r: best_title_similarity(title, r), reverse=True)
    return found


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #


def _compare(
    record: Record, title: str | None, authors: list[str] | None, year: int | None
) -> tuple[list[dict[str, Any]], str]:
    """Compare claimed fields with a record. Returns (checks, worst_level)."""
    checks: list[dict[str, Any]] = []
    levels = {"ok": 0, "warn": 1, "fail": 2}
    worst = "ok"

    def add(name: str, level: str, detail: str) -> None:
        nonlocal worst
        checks.append({"field": name, "result": level, "detail": detail})
        if levels[level] > levels[worst]:
            worst = level

    if title:
        sim = best_title_similarity(title, record)
        level = "ok" if sim >= TITLE_MATCH else "warn" if sim >= TITLE_CLOSE else "fail"
        add("title", level, f"similarity {sim} (record: {record.title!r})")

    if authors:
        claimed = _fold(family_name(authors[0]))
        found = [_fold(a) for a in record.authors if a]
        if not found:
            add("first_author", "warn", "record lists no authors")
        elif claimed == found[0]:
            add("first_author", "ok", f"{record.authors[0]}")
        elif claimed in found:
            add("first_author", "warn", f"{authors[0]!r} is an author but not first")
        else:
            add("first_author", "fail", f"{authors[0]!r} not among {record.authors[:6]}")

    if year:
        if record.year is None:
            add("year", "warn", "record has no year")
        elif record.year == year:
            add("year", "ok", str(year))
        elif abs(record.year - year) == 1:
            add("year", "warn", f"record says {record.year} (online-first vs print?)")
        else:
            add("year", "fail", f"record says {record.year}")

    return checks, worst


def verify_reference(
    title: str | None = None,
    authors: list[str] | None = None,
    year: int | None = None,
    doi: str | None = None,
    fetch: Fetcher = fetch_json,
) -> dict[str, Any]:
    """Verify one reference.

    Statuses:
      verified        record found and every supplied field agrees
      partial_match   record found, minor disagreements (year ±1, near title)
      mismatch        DOI resolves to a different work (typical of fabricated refs)
      possible_match  no DOI; a close but not certain candidate was found
      doi_not_found   DOI resolves nowhere
      not_found       no DOI and no plausible candidate
      error           a network/service failure — NOT evidence of fabrication
    """
    if not (title or doi):
        return {"status": "error", "message": "Provide at least a title or a DOI."}

    try:
        if doi:
            bare = normalize_doi(doi)
            if not bare:
                return {"status": "error", "message": f"Could not parse a DOI from {doi!r}."}
            record = lookup_doi(bare, fetch)
            if record is None:
                return {
                    "status": "doi_not_found",
                    "doi": bare,
                    "message": "Neither Crossref, OpenAlex nor TR Dizin knows this DOI.",
                }
            checks, worst = _compare(record, title, authors, year)
            status = {"ok": "verified", "warn": "partial_match", "fail": "mismatch"}[worst]
            return {"status": status, "doi": bare, "record": record.to_dict(), "checks": checks}

        candidates = search_works(title or "", authors, year, fetch=fetch)
    except ConnectionError as exc:
        return {"status": "error", "message": str(exc)}

    if not candidates:
        return {"status": "not_found", "message": "No candidates returned."}

    # Rank by title, then let author/year break near-ties between versions of a work.
    def score(r: Record) -> tuple[float, int]:
        _, worst = _compare(r, None, authors, year)
        return best_title_similarity(title or "", r), -{"ok": 0, "warn": 1, "fail": 2}[worst]

    ranked = sorted(candidates, key=score, reverse=True)
    best = ranked[0]
    best_sim = best_title_similarity(title or "", best)
    checks, worst = _compare(best, title, authors, year)
    alternatives = [
        {"similarity": best_title_similarity(title or "", c), "source": c.source,
         "doi": c.doi, "title": c.title, "year": c.year}
        for c in ranked[1:3]
    ]
    if best_sim < TITLE_CLOSE:
        status = "not_found"
    elif worst == "ok":
        status = "verified"
    else:
        status = "possible_match"
    return {
        "status": status,
        "doi": best.doi,
        "record": best.to_dict(),
        "checks": checks,
        "alternatives": alternatives,
    }
