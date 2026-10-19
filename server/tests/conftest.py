"""Offline fixtures: a fake fetcher that serves canned Crossref/OpenAlex replies."""

from __future__ import annotations

from typing import Any

import pytest

# A real paper, used as the "known" record.
VASWANI = {
    "DOI": "10.48550/arXiv.1706.03762",
    "title": ["Attention Is All You Need"],
    "author": [{"family": "Vaswani"}, {"family": "Shazeer"}, {"family": "Parmar"}],
    "issued": {"date-parts": [[2017]]},
    "container-title": ["arXiv"],
    "abstract": "<jats:p>The dominant sequence transduction models...</jats:p>",
}

TURKISH = {
    "DOI": "10.1234/tr.2023.001",
    "title": ["Sosyal Mühendislik Saldırılarında İnsan Faktörü"],
    "author": [{"family": "Çetlenbik"}, {"family": "Yılmaz"}],
    "issued": {"date-parts": [[2023]]},
    "container-title": ["Bilişim Dergisi"],
}

OPENALEX_ONLY = {
    "doi": "https://doi.org/10.9999/oa.only",
    "display_name": "A Work Only OpenAlex Knows",
    "publication_year": 2021,
    "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
    "primary_location": {"source": {"display_name": "Journal of Tests"}},
    "abstract_inverted_index": {"Hello": [0], "world": [1]},
}


# A Turkish paper indexed only in TR Dizin; its first-listed title is the English one.
TRDIZIN_ONLY = {
    "id": 424242,
    "doi": "10.17341/tr.only.2019",
    "publicationYear": 2019,
    "abstracts": [
        {"language": "ENG", "title": "Human Factor in Information Security Awareness",
         "abstract": "This study examines..."},
        {"language": "TUR", "title": "Bilgi Güvenliği Farkındalığında İnsan Faktörü",
         "abstract": "Bu çalışma..."},
    ],
    "authors": [
        {"name": "Ayşe DEMİR", "inPublicationName": "Ayşe DEMİR", "order": 1},
        {"name": "Mehmet ÖZ", "inPublicationName": "Mehmet ÖZ", "order": 2},
    ],
    "journal": {"name": "Polis Bilimleri Dergisi"},
}


class FakeFetcher:
    def __init__(self, routes: dict[str, tuple[int, Any]], search: list[dict] | None = None,
                 trdizin: list[dict] | None = None, fail: bool = False):
        self.routes = routes
        self.search = search or []
        self.trdizin = trdizin or []
        self.fail = fail
        self.calls: list[str] = []

    def __call__(self, url: str) -> tuple[int, Any]:
        self.calls.append(url)
        if self.fail:
            raise ConnectionError("simulated outage")
        for prefix, reply in self.routes.items():
            if url.startswith(prefix):
                return reply
        if "api.crossref.org/works?" in url:
            return 200, {"message": {"items": self.search}}
        if url.startswith("https://search.trdizin.gov.tr/api/"):
            return 200, {"hits": {"hits": [{"_source": s} for s in self.trdizin]}}
        return 404, None

    def called(self, host: str) -> bool:
        return any(host in u for u in self.calls)


@pytest.fixture
def fetcher():
    return FakeFetcher(
        routes={
            "https://api.crossref.org/works/10.48550/arxiv.1706.03762": (200, {"message": VASWANI}),
            "https://api.crossref.org/works/10.1234/tr.2023.001": (200, {"message": TURKISH}),
            "https://api.openalex.org/works/https://doi.org/10.9999/oa.only": (200, OPENALEX_ONLY),
        },
        search=[TURKISH, VASWANI],
        trdizin=[TRDIZIN_ONLY],
    )
