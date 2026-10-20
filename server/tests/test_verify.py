from akademik_ajan.verify import (
    lookup_doi,
    normalize_doi,
    title_similarity,
    verify_reference,
)

from conftest import FakeFetcher


def test_normalize_doi_variants():
    assert normalize_doi("https://doi.org/10.1000/ABC.123") == "10.1000/abc.123"
    assert normalize_doi("doi:10.1000/xyz.") == "10.1000/xyz"
    assert normalize_doi("See (10.1000/q1).") == "10.1000/q1"
    assert normalize_doi("https://doi.org/10.1000%2Fenc") == "10.1000/enc"
    assert normalize_doi("no doi here") is None


def test_title_similarity_ignores_case_and_turkish_diacritics():
    assert title_similarity("Sosyal Mühendislik", "sosyal muhendislik") == 1.0
    assert title_similarity("İnsan Faktörü", "insan faktoru") == 1.0
    assert title_similarity("Attention Is All You Need", "Graph Neural Networks") < 0.5


def test_doi_with_matching_fields_is_verified(fetcher):
    r = verify_reference(title="Attention is all you need", authors=["Ashish Vaswani"],
                         year=2017, doi="10.48550/arXiv.1706.03762", fetch=fetcher)
    assert r["status"] == "verified"
    assert r["record"]["authors"][0] == "Vaswani"
    assert "<jats" not in r["record"]["abstract"]


def test_doi_pointing_to_other_paper_is_mismatch(fetcher):
    # Classic fabricated citation: plausible title glued onto a real DOI.
    r = verify_reference(title="Deep Learning for Phishing Detection", authors=["Smith, J."],
                         year=2017, doi="10.48550/arXiv.1706.03762", fetch=fetcher)
    assert r["status"] == "mismatch"
    failed = {c["field"] for c in r["checks"] if c["result"] == "fail"}
    assert failed == {"title", "first_author"}


def test_year_off_by_one_is_partial(fetcher):
    r = verify_reference(title="Attention Is All You Need", year=2018,
                         doi="10.48550/arXiv.1706.03762", fetch=fetcher)
    assert r["status"] == "partial_match"


def test_print_year_years_after_online_first_is_accepted():
    # Found by blind adjudication: online 2016, print issue 2018, cited as 2018.
    msg = {"DOI": "10.1177/0093650215627483", "title": ["Suspicion, cognition, and automaticity model"],
           "author": [{"family": "Vishwanath"}], "issued": {"date-parts": [[2016, 2, 12]]},
           "published-online": {"date-parts": [[2016, 2, 12]]},
           "published-print": {"date-parts": [[2018, 7]]}}
    f = FakeFetcher({"https://api.crossref.org/works/10.1177/0093650215627483": (200, {"message": msg})})
    r = verify_reference(title="Suspicion, cognition, and automaticity model", authors=["Vishwanath, A."],
                         year=2018, doi="10.1177/0093650215627483", fetch=f)
    assert r["status"] == "verified"
    r = verify_reference(title="Suspicion, cognition, and automaticity model", year=2021,
                         doi="10.1177/0093650215627483", fetch=f)
    assert r["status"] == "mismatch"


def test_unknown_doi(fetcher):
    r = verify_reference(title="Anything", doi="10.5555/does.not.exist", fetch=fetcher)
    assert r["status"] == "doi_not_found"


def test_openalex_fallback(fetcher):
    rec = lookup_doi("10.9999/oa.only", fetch=fetcher)
    assert rec is not None and rec.source == "openalex"
    assert rec.authors == ["Lovelace"] and rec.abstract == "Hello world"


def test_title_search_finds_turkish_work(fetcher):
    r = verify_reference(title="Sosyal mühendislik saldırılarında insan faktörü",
                         authors=["Elif Nur Çalışkan"], year=2023, fetch=fetcher)
    assert r["status"] == "verified"
    assert r["doi"] == "10.1234/tr.2023.001"


def test_title_search_with_no_plausible_candidate(fetcher):
    r = verify_reference(title="Quantum blockchain for medieval poetry", fetch=fetcher)
    assert r["status"] == "not_found"
    # every tier was consulted before giving up
    assert fetcher.called("trdizin.gov.tr") and fetcher.called("openalex.org")


def test_confident_crossref_match_skips_other_sources(fetcher):
    verify_reference(title="Attention is all you need", authors=["Vaswani"], fetch=fetcher)
    assert not fetcher.called("trdizin.gov.tr")
    assert not fetcher.called("openalex.org")


def test_trdizin_finds_turkish_paper_by_its_turkish_title(fetcher):
    # TR Dizin lists the English title first; the Turkish one must still match.
    r = verify_reference(title="Bilgi güvenliği farkındalığında insan faktörü",
                         authors=["Demir, Ayşe"], year=2019, fetch=fetcher)
    assert r["status"] == "verified"
    assert r["record"]["source"] == "trdizin"
    assert r["record"]["url"].endswith("/424242")


def test_author_name_layouts():
    from akademik_ajan.verify import author_matches
    assert author_matches("Nurul Hidayat", "Nurul Hidayat")      # full name in family field
    assert author_matches("Hidayat, N.", "Nurul Hidayat")
    assert author_matches("Lluís Ribas de Pouplana", "Ribas de Pouplana")
    assert author_matches("Elif Nur ÇALIŞKAN", "Çalışkan")
    assert not author_matches("Smith, J.", "Smithson")
    assert not author_matches("Kaya", "Yılmaz")


def test_bilingual_title_resolved_via_second_source():
    # Crossref holds only the Turkish title; the citation uses the English one,
    # which TR Dizin knows for the same DOI.
    crossref = {"DOI": "10.5505/jems.2019.85057",
                "title": ["Deniz Siber Güvenlik Bilincinin Öncülleri ve Sonuçları"],
                "author": [{"family": "Bolat"}], "issued": {"date-parts": [[2019]]}}
    trdizin = {"id": 1, "doi": "10.5505/jems.2019.85057", "publicationYear": 2019,
               "abstracts": [{"title": "Deniz Siber Güvenlik Bilincinin Öncülleri ve Sonuçları"},
                             {"title": "Antecedents and Outcomes of Maritime Cyber Security Awareness"}],
               "authors": [{"name": "Pelin BOLAT", "order": 1}]}
    f = FakeFetcher({"https://api.crossref.org/works/10.5505/jems.2019.85057": (200, {"message": crossref})},
                    trdizin=[trdizin])
    r = verify_reference(title="Antecedents and outcomes of maritime cyber security awareness",
                         authors=["Bolat, P."], year=2019, doi="10.5505/jems.2019.85057", fetch=f)
    assert r["status"] == "verified"


def test_title_search_merges_other_language_title_from_duplicate():
    # Regression (holdout, v0.2.0): Crossref returns only the Turkish title, TR Dizin the
    # same DOI with both titles; the citation uses the English title.
    crossref = {"DOI": "10.18016/ksutarimdoga.vi.499918",
                "title": ["Süt Sığırcılığı İşletmelerinin Memnuniyet ve Sürdürülebilirliğine Etki Eden Faktörler"],
                "author": [{"family": "Bakır"}], "issued": {"date-parts": [[2019]]}}
    trdizin = {"id": 9, "doi": "10.18016/ksutarimdoga.vi.499918", "publicationYear": 2019,
               "abstracts": [{"title": "Süt Sığırcılığı İşletmelerinin Memnuniyet ve Sürdürülebilirliğine Etki Eden Faktörler"},
                             {"title": "The Factors Affecting the Satisfaction and Sustainability of the Dairy Cattle Farms"}],
               "authors": [{"name": "Gökhan BAKIR", "order": 1}]}
    f = FakeFetcher({}, search=[crossref], trdizin=[trdizin])
    r = verify_reference(title="The factors affecting the satisfaction and sustainability of the dairy cattle farms",
                         authors=["BAKIR"], year=2019, fetch=f)
    assert r["status"] == "verified"


def test_unreachable_fallback_does_not_sink_the_result(fetcher):
    def flaky(url):
        if "openalex.org" in url:
            raise ConnectionError("budget exhausted")
        return fetcher(url)
    r = verify_reference(title="Quantum blockchain for medieval poetry", fetch=flaky)
    assert r["status"] == "not_found"
    assert r["unchecked_sources"] == ["openalex"]


def test_unknown_doi_with_unreachable_source_is_error_not_fabrication(fetcher):
    def flaky(url):
        if "trdizin.gov.tr" in url:
            raise ConnectionError("down")
        return fetcher(url)
    r = verify_reference(title="X", doi="10.5555/nobody.knows", fetch=flaky)
    assert r["status"] == "error"


def test_doi_known_only_to_trdizin(fetcher):
    rec = lookup_doi("https://doi.org/10.17341/TR.ONLY.2019", fetch=fetcher)
    assert rec is not None and rec.source == "trdizin"
    assert rec.authors == ["DEMİR", "ÖZ"]
    assert rec.venue == "Polis Bilimleri Dergisi"


def test_network_failure_is_error_not_not_found():
    r = verify_reference(title="X", doi="10.1000/x", fetch=FakeFetcher({}, fail=True))
    assert r["status"] == "error"


def test_requires_title_or_doi(fetcher):
    assert verify_reference(fetch=fetcher)["status"] == "error"
