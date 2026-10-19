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


class FakeFetcher:
    def __init__(self, routes: dict[str, tuple[int, Any]], search: list[dict] | None = None,
                 fail: bool = False):
        self.routes = routes
        self.search = search or []
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
        return 404, None


@pytest.fixture
def fetcher():
    return FakeFetcher(
        routes={
            "https://api.crossref.org/works/10.48550/arxiv.1706.03762": (200, {"message": VASWANI}),
            "https://api.crossref.org/works/10.1234/tr.2023.001": (200, {"message": TURKISH}),
            "https://api.openalex.org/works/https://doi.org/10.9999/oa.only": (200, OPENALEX_ONLY),
        },
        search=[TURKISH, VASWANI],
    )
