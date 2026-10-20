from akademik_ajan.literature import cite_key, export_bibtex, search_literature, to_bibtex
from akademik_ajan.verify import Record, parse_crossref

from conftest import TRDIZIN_ONLY, TURKISH, VASWANI, FakeFetcher

TR_DUP = {  # TR Dizin's copy of the Crossref TURKISH record (same DOI), plus an English title
    "id": 7, "doi": "10.1234/tr.2023.001", "publicationYear": 2023, "docType": "PAPER",
    "abstracts": [{"title": "Sosyal Mühendislik Saldırılarında İnsan Faktörü", "abstract": "Özet."},
                  {"title": "The Human Factor in Social Engineering Attacks"}],
    "authors": [{"name": "Elif Nur ÇALIŞKAN", "order": 1}],
    "journal": {"name": "Bilişim Dergisi"}, "issue": {"volume": "5", "number": "2"},
    "startPage": "10", "endPage": "24", "orderCitationCount": 3,
}
OLD_TR = {**TRDIZIN_ONLY, "id": 8, "doi": None, "publicationYear": 2009}


def test_search_merges_duplicates_and_keeps_provenance():
    f = FakeFetcher({}, search=[TURKISH, VASWANI], trdizin=[TR_DUP, TRDIZIN_ONLY])
    out = search_literature("sosyal mühendislik", fetch=f)
    assert out["counts"] == {"crossref": 2, "trdizin": 2, "openalex": 0}
    assert out["unique"] == 3
    first = out["works"][0]
    assert first["doi"] == "10.1234/tr.2023.001"
    assert first["found_in"] == ["crossref", "trdizin"]
    # gaps filled from TR Dizin: abstract, volume and the English title
    assert first["abstract"] == "Özet." and first["volume"] == "5"
    assert "The Human Factor in Social Engineering Attacks" in first["alt_titles"]


def test_relevance_handles_turkish_suffixes_and_ranks():
    from akademik_ajan.literature import relevance
    on_topic = Record(source="x", doi=None, title="Öğrencilerin Siber Güvenlik Farkındalığı")
    off_topic = Record(source="x", doi=None, title="Bilinçli Farkındalık ve Sosyal Hizmet")
    q = "siber güvenlik farkındalık"
    assert relevance(q, on_topic) == 1.0
    assert relevance(q, off_topic) == round(1 / 3, 2)
    abstract_only = Record(source="x", doi=None, title="Bir inceleme",
                           abstract="Siber güvenlik farkındalığı ölçülmüştür.")
    assert relevance(q, abstract_only) == 0.5


def test_search_orders_by_relevance():
    off = {**TURKISH, "DOI": "10.1234/off", "title": ["Bilinçli Farkındalık Uygulamaları"]}
    on = {**TURKISH, "DOI": "10.1234/on", "title": ["Sosyal Mühendislik Farkındalığı"]}
    f = FakeFetcher({}, search=[off, on], trdizin=[])
    out = search_literature("sosyal mühendislik farkındalık", fetch=f)
    assert [w["doi"] for w in out["works"]] == ["10.1234/on", "10.1234/off"]


def test_year_range_applies_to_trdizin_and_is_sent_to_crossref():
    f = FakeFetcher({}, search=[], trdizin=[TRDIZIN_ONLY, OLD_TR])
    out = search_literature("bilgi güvenliği", from_year=2015, to_year=2024, fetch=f)
    assert [w["year"] for w in out["works"]] == [2019]
    crossref_url = next(u for u in f.calls if "api.crossref.org" in u)
    assert "from-pub-date%3A2015" in crossref_url and "until-pub-date%3A2024" in crossref_url


def test_unreachable_source_is_reported_not_fatal():
    base = FakeFetcher({}, search=[VASWANI])

    def flaky(url):
        if "trdizin" in url:
            raise ConnectionError("down")
        return base(url)

    out = search_literature("attention", sources=("crossref", "trdizin"), fetch=flaky)
    assert out["unreachable"] == ["trdizin"] and out["unique"] == 1


def test_bibtex_entry_from_crossref_record():
    msg = {**VASWANI, "type": "journal-article", "volume": "30", "page": "5998-6008",
           "author": [{"family": "Vaswani", "given": "Ashish"}, {"family": "Shazeer", "given": "Noam"}],
           "title": ["Attention Is All You Need: R&D at 100%"]}
    rec = parse_crossref(msg)
    bib = to_bibtex(rec, cite_key(rec, set()))
    assert bib.startswith("@article{vaswani2017attention,")
    assert "author = {Vaswani, Ashish and Shazeer, Noam}" in bib
    assert r"title = {{Attention Is All You Need: R\&D at 100\%}}" in bib
    assert "pages = {5998--6008}" in bib and "doi = {10.48550/arxiv.1706.03762}" in bib
    assert "journal = {arXiv}" in bib


def test_bibtex_keeps_turkish_characters_and_unique_keys():
    rec = Record(source="trdizin", doi=None, title="İnsan Faktörü ve Güvenlik", authors=["Çalışkan"],
                 author_names=["ÇALIŞKAN, Elif Nur"], year=2023, venue="Bilişim Dergisi",
                 kind="article", url="https://search.trdizin.gov.tr/tr/yayin/detay/7")
    taken: set[str] = set()
    k1, k2 = cite_key(rec, taken), cite_key(rec, taken)
    assert (k1, k2) == ("caliskan2023insan", "caliskan2023insana")
    bib = to_bibtex(rec, k1)
    assert "author = {ÇALIŞKAN, Elif Nur}" in bib and "{{İnsan Faktörü ve Güvenlik}}" in bib
    assert "url = {https://search.trdizin.gov.tr/tr/yayin/detay/7}" in bib  # no DOI -> URL


def test_export_bibtex_reports_unknown_and_deduplicates(fetcher):
    out = export_bibtex(["10.48550/arXiv.1706.03762", "https://doi.org/10.48550/ARXIV.1706.03762",
                         "10.5555/nope", "not a doi"], fetch=fetcher)
    assert out["count"] == 1
    assert out["not_found"] == ["10.5555/nope", "not a doi"]
    assert out["bibtex"].count("@") == 1
