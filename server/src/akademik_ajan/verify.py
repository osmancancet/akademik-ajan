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
    # Bibliographic detail used for BibTeX export and ranking; not used in verification.
    author_names: list[str] = field(default_factory=list)  # "Family, Given", in order
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    publisher: str | None = None
    kind: str | None = None  # "article", "inproceedings", "book", "chapter", "thesis", "other"
    cited_by: int | None = None
    # Every publication year the source reports (online-first, print, issued). A citation
    # may legitimately use any of them; papers can appear online years before the issue.
    years: list[int] = field(default_factory=list)

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


def _name_tokens(name: str) -> set[str]:
    return {t for t in _fold(name).split() if len(t) > 1}


def author_matches(claimed: str, record_author: str) -> bool:
    """True if a cited author name plausibly denotes a record's author.

    Sources disagree on name layout: Crossref sometimes puts the full name in
    the family field ("Nurul Hidayat"), compound surnames span several words
    ("Ribas de Pouplana"), and citations may give "Last, F." or "First Last".
    So the claimed family name may appear anywhere in the record's name, or
    the record's family name anywhere in the claimed one.
    """
    claimed_family = _fold(family_name(claimed))
    record_family = _fold(family_name(record_author))
    if not claimed_family or not record_family:
        return False
    return (
        claimed_family == record_family
        or claimed_family in _name_tokens(record_author)
        or record_family in _name_tokens(claimed)
    )


# --------------------------------------------------------------------------- #
# Source parsers
# --------------------------------------------------------------------------- #


_CROSSREF_DATES = ("issued", "published-print", "published-online", "published", "created")


def _crossref_year(msg: dict[str, Any]) -> int | None:
    years = _crossref_years(msg)
    return years[0] if years else None


def _crossref_years(msg: dict[str, Any]) -> list[int]:
    """Distinct years from Crossref's date fields, most authoritative first ("created" only as fallback)."""
    found: list[int] = []
    for key in _CROSSREF_DATES:
        if key == "created" and found:
            break
        parts = (msg.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            year = int(parts[0][0])
            if year not in found:
                found.append(year)
    return found


_KINDS = {
    # Crossref types
    "journal-article": "article", "proceedings-article": "inproceedings", "book": "book",
    "monograph": "book", "edited-book": "book", "book-chapter": "chapter", "dissertation": "thesis",
    "posted-content": "other",
    # OpenAlex types
    "article": "article", "book-chapter": "chapter",
    # TR Dizin docType values
    "PAPER": "article", "ARTICLE": "article", "PROCEEDING": "inproceedings", "BOOK": "book",
    "THESIS": "thesis", "PROJECT": "other",
}


def _split_name(full: str) -> str:
    """'Given Middle Family' -> 'Family, Given Middle' (keeps an existing comma form)."""
    full = re.sub(r"\s+", " ", (full or "").strip())
    if not full or "," in full:
        return full
    parts = full.split(" ")
    return parts[0] if len(parts) == 1 else f"{parts[-1]}, {' '.join(parts[:-1])}"


def _crossref_author(a: dict[str, Any]) -> str:
    if a.get("family"):
        return f"{a['family']}, {a['given']}" if a.get("given") else a["family"]
    return a.get("name") or ""


def parse_crossref(msg: dict[str, Any]) -> Record:
    titles = msg.get("title") or [""]
    venues = msg.get("container-title") or [None]
    abstract = msg.get("abstract")
    if abstract:
        abstract = re.sub(r"\s+", " ", _TAG_RE.sub(" ", abstract)).strip()
    doi = normalize_doi(msg.get("DOI"))
    authors = msg.get("author") or []
    return Record(
        source="crossref",
        doi=doi,
        title=titles[0] or "",
        alt_titles=[t for t in (msg.get("original-title") or []) + (msg.get("subtitle") or []) if t],
        authors=[a.get("family") or a.get("name") or "" for a in authors],
        year=_crossref_year(msg),
        venue=venues[0],
        abstract=abstract or None,
        url=f"https://doi.org/{doi}" if doi else None,
        author_names=[_crossref_author(a) for a in authors],
        volume=msg.get("volume"),
        issue=msg.get("issue"),
        pages=(msg.get("page") or "").replace("-", "--") or None,
        publisher=msg.get("publisher"),
        kind=_KINDS.get(msg.get("type") or "", "other"),
        cited_by=msg.get("is-referenced-by-count"),
        years=_crossref_years(msg),
    )


def _openalex_abstract(index: dict[str, list[int]] | None) -> str | None:
    if not index:
        return None
    positions = [(pos, word) for word, idxs in index.items() for pos in idxs]
    return " ".join(word for _, word in sorted(positions)) or None


def parse_openalex(work: dict[str, Any]) -> Record:
    source = ((work.get("primary_location") or {}).get("source") or {})
    names = [(a.get("author") or {}).get("display_name") or "" for a in work.get("authorships") or []]
    biblio = work.get("biblio") or {}
    first, last = biblio.get("first_page"), biblio.get("last_page")
    return Record(
        source="openalex",
        doi=normalize_doi(work.get("doi")),
        title=work.get("display_name") or work.get("title") or "",
        authors=[family_name(n) for n in names],
        year=work.get("publication_year"),
        venue=source.get("display_name"),
        abstract=_openalex_abstract(work.get("abstract_inverted_index")),
        url=work.get("id"),
        author_names=[_split_name(n) for n in names],
        volume=biblio.get("volume"),
        issue=biblio.get("issue"),
        pages=f"{first}--{last}" if first and last and first != last else first,
        kind=_KINDS.get(work.get("type") or "", "other"),
        cited_by=work.get("cited_by_count"),
    )


def parse_trdizin(src: dict[str, Any]) -> Record:
    """Parse one TR Dizin hit (`_source`). Each language version carries its own title."""
    versions = src.get("abstracts") or []
    titles = [v.get("title", "").strip() for v in versions]
    titles = [t for t in titles if len(t) > 2]  # TR Dizin uses "-" for missing titles
    abstract = next((v.get("abstract") for v in versions if v.get("abstract")), None)
    authors = sorted(src.get("authors") or [], key=lambda a: a.get("order") or 0)
    journal = src.get("journal") if isinstance(src.get("journal"), dict) else {}
    issue = src.get("issue") if isinstance(src.get("issue"), dict) else {}
    year = src.get("publicationYear")
    names = [a.get("inPublicationName") or a.get("name") or "" for a in authors]
    start, end = str(src.get("startPage") or ""), str(src.get("endPage") or "")
    pages = f"{start}--{end}" if start not in ("", "0") and end and end != start else (end or None)
    return Record(
        source="trdizin",
        doi=normalize_doi(src.get("doi")),
        title=titles[0] if titles else "",
        alt_titles=titles[1:],
        authors=[family_name(n) for n in names],
        year=int(year) if year else None,
        venue=journal.get("name"),
        abstract=abstract,
        url=TRDIZIN_PAGE.format(id=src["id"]) if src.get("id") else None,
        author_names=[_split_name(n) for n in names],
        volume=issue.get("volume") or None,
        issue=issue.get("number") or None,
        pages=pages if pages != "0" else None,
        kind=_KINDS.get(src.get("docType") or "", "other"),
        cited_by=src.get("orderCitationCount"),
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


DOI_RESOLVERS = {"crossref": _crossref_doi, "openalex": _openalex_doi, "trdizin": _trdizin_doi}


def _resolve_doi(
    doi: str, fetch: Fetcher, skip: tuple[str, ...] = ()
) -> tuple[list[Record], list[str]]:
    """Ask resolvers in order; stop at the first hit. Returns (hits, unreachable sources)."""
    hits: list[Record] = []
    unreachable: list[str] = []
    for name, resolver in DOI_RESOLVERS.items():
        if name in skip:
            continue
        try:
            record = resolver(doi, fetch)
        except ConnectionError:
            unreachable.append(name)
            continue
        if record is not None:
            hits.append(record)
            if not skip:  # primary lookup: first hit is enough
                break
    return hits, unreachable


def lookup_doi(doi: str, fetch: Fetcher = fetch_json) -> Record | None:
    """Resolve a DOI via Crossref, then OpenAlex, then TR Dizin. None if nobody knows it.

    Raises ConnectionError when no source knew the DOI but at least one could not
    be reached, because then "unknown DOI" would be an unproven claim.
    """
    bare = normalize_doi(doi)
    if not bare:
        return None
    hits, unreachable = _resolve_doi(bare, fetch)
    if hits:
        return hits[0]
    if unreachable:
        raise ConnectionError(f"Could not reach: {', '.join(unreachable)}")
    return None


def _search(
    title: str, authors: list[str] | None, year: int | None, rows: int, fetch: Fetcher
) -> tuple[list[Record], list[str]]:
    query = " ".join([title, *(family_name(a) for a in authors or [])])
    if year:
        query += f" {year}"

    found: list[Record] = []
    seen: dict[str, Record] = {}
    unreachable: list[str] = []

    def add(name: str, run) -> float:
        try:
            records = run()
        except ConnectionError:
            unreachable.append(name)
            records = []
        for r in records:
            key = r.doi or f"{r.source}:{_fold(r.title)}"
            if key not in seen:
                seen[key] = r
                found.append(r)
            else:
                # Same work from another source: keep its other-language titles, which
                # the first source may lack (Crossref often holds only the Turkish title).
                kept = seen[key]
                kept.alt_titles += [t for t in r.titles() if t not in kept.titles()]
                for y in r.years or ([r.year] if r.year else []):
                    if y not in kept.years:
                        kept.years.append(y)
        return max((best_title_similarity(title, r) for r in found), default=0.0)

    best = add("crossref", lambda: _crossref_search(query, rows, fetch))
    if best < TITLE_MATCH:
        best = add("trdizin", lambda: _trdizin_query(title, fetch)[:rows])
    if best < TITLE_MATCH:
        add("openalex", lambda: _openalex_search(title, rows, fetch))

    if not found and len(unreachable) == 3:
        raise ConnectionError("Crossref, TR Dizin and OpenAlex were all unreachable.")
    found.sort(key=lambda r: best_title_similarity(title, r), reverse=True)
    return found, unreachable


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
    A source that cannot be reached is skipped.
    """
    return _search(title, authors, year, rows, fetch)[0]


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
        found = [a for a in record.authors if a]
        position = next((i for i, a in enumerate(found) if author_matches(authors[0], a)), None)
        if not found:
            add("first_author", "warn", "record lists no authors")
        elif position == 0:
            add("first_author", "ok", f"{found[0]}")
        elif position is not None:
            add("first_author", "warn", f"{authors[0]!r} is an author but not first")
        else:
            add("first_author", "fail", f"{authors[0]!r} not among {found[:6]}")

    if year:
        known = record.years or ([record.year] if record.year else [])
        if not known:
            add("year", "warn", "record has no year")
        elif year in known:
            add("year", "ok", str(year))
        elif min(abs(y - year) for y in known) == 1:
            add("year", "warn", f"record says {'/'.join(map(str, known))} (online-first vs print?)")
        else:
            add("year", "fail", f"record says {'/'.join(map(str, known))}")

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
            if title and best_title_similarity(title, record) < TITLE_MATCH:
                # Bilingual journals: one source may hold only the Turkish title and
                # the citation may use the English one. Pull the other sources'
                # versions of the same DOI before calling it a mismatch.
                others, _ = _resolve_doi(bare, fetch, skip=(record.source,))
                for other in others:
                    record.alt_titles += [t for t in other.titles() if t not in record.titles()]
            checks, worst = _compare(record, title, authors, year)
            status = {"ok": "verified", "warn": "partial_match", "fail": "mismatch"}[worst]
            return {"status": status, "doi": bare, "record": record.to_dict(), "checks": checks}

        candidates, unreachable = _search(title or "", authors, year, 5, fetch)
    except ConnectionError as exc:
        return {"status": "error", "message": str(exc)}

    extra = {"unchecked_sources": unreachable} if unreachable else {}
    if not candidates:
        return {"status": "not_found", "message": "No candidates returned.", **extra}

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
        **extra,
    }
