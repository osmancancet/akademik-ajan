from akademik_ajan.bibtex import parse_bibtex, verify_bibtex

BIB = r"""
@article{vaswani2017,
  title  = {Attention Is {All} You Need},
  author = {Vaswani, Ashish and Shazeer, Noam},
  year   = {2017},
  doi    = {10.48550/arXiv.1706.03762}
}
@article{fake2020,
  title  = {Neural Phishing Detectors Are Perfect},
  author = {John Smith},
  year   = {2020},
  doi    = {10.5555/does.not.exist}
}
@inproceedings{tr2023,
  title  = {Sosyal M{\"u}hendislik Sald{\i}r{\i}lar{\i}nda {\.I}nsan Fakt{\"o}r{\"u}},
  author = {{\c{C}}etlenbik, Osman Can},
  year   = {2023}
}
"""


def test_parse_bibtex_fields():
    entries = {e["key"]: e for e in parse_bibtex(BIB)}
    assert entries["vaswani2017"]["authors"] == ["Vaswani", "Shazeer"]
    assert entries["vaswani2017"]["title"] == "Attention Is All You Need"
    assert entries["fake2020"]["authors"] == ["Smith"]
    assert entries["tr2023"]["doi"] is None
    assert entries["tr2023"]["title"] == "Sosyal Mühendislik Saldırılarında İnsan Faktörü"
    assert entries["tr2023"]["authors"] == ["Çetlenbik"]


def test_verify_bibtex_summary(fetcher):
    out = verify_bibtex(BIB, fetch=fetcher)
    by_key = {e["key"]: e["status"] for e in out["entries"]}
    assert out["total"] == 3
    assert by_key["vaswani2017"] == "verified"
    assert by_key["fake2020"] == "doi_not_found"
    assert by_key["tr2023"] == "verified"
    assert out["summary"] == {"verified": 2, "doi_not_found": 1}
