import pytest

from akademik_ajan.response import check, render_response_letter

DATA = {
    "title": "Detecting Phishing with Transformers",
    "manuscript_id": "COSE-D-26-00001",
    "round": 1,
    "opening": "We thank the reviewers for their careful reading.",
    "reviewers": [
        {"name": "Reviewer 1", "points": [
            {"id": "R1.1", "comment": "The baseline set is weak.\nAdd a 50% & $ test.",
             "response": "We added two baselines.", "changes": "New Table 4.",
             "location": "Section 5.2", "status": "addressed"},
            {"id": "R1.2", "comment": "Please run on a Turkish corpus.",
             "response": "", "status": "author_action"},
        ]},
        {"name": "Reviewer 2", "points": [
            {"comment": "Typo in Eq. 3.", "response": "Fixed.", "status": "addressed"},
        ]},
    ],
}


def test_check_reports_author_action_and_counts():
    c = check(DATA)
    assert c["ready"] is False and c["problems"] == []
    assert c["author_action"] == ["R1.2"]
    assert c["counts"]["addressed"] == 2 and c["points"] == 3


def test_check_catches_empty_and_placeholders_and_duplicates():
    bad = {"title": "T", "reviewers": [{"name": "R", "points": [
        {"id": "R1.1", "comment": "c", "response": ""},
        {"id": "R1.1", "comment": "c", "response": "We will [TODO] this."},
        {"id": "R1.3", "comment": "", "response": "ok", "status": "done"},
    ]}]}
    probs = check(bad)["problems"]
    assert "R1.1: response is empty" in probs
    assert "R1.1: duplicate id" in probs
    assert "R1.1: response or changes contain a placeholder" in probs
    assert "R1.3: unknown status 'done'" in probs


def test_markdown_letter_layout():
    out = render_response_letter(DATA)
    md = out["letter"]
    assert md.startswith("# Response to reviewers: Detecting Phishing with Transformers")
    assert "COSE-D-26-00001 · Revision round 1" in md
    assert "> The baseline set is weak.\n> Add a 50% & $ test." in md
    assert "**Changes (Section 5.2).** New Table 4." in md
    assert "### R1.2" in md and "_Pending author input._" in md
    assert "### R2.1" in md  # id generated from position
    assert out["change_log"].count("\n") == 5  # header, rule, 3 rows


def test_latex_letter_escapes_specials():
    tex = render_response_letter(DATA, fmt="latex")["letter"]
    assert r"Add a 50\% \& \$ test." in tex
    assert r"\subsection*{Reviewer 2}" in tex and r"\paragraph{R2.1}" in tex


def test_unknown_format():
    with pytest.raises(ValueError):
        render_response_letter(DATA, fmt="docx")
