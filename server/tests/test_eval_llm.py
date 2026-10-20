"""Offline tests for the LLM-reference experiment scripts (no network, no API key)."""

import importlib.util
import json
from pathlib import Path

EVAL = Path(__file__).resolve().parents[2] / "eval" / "llm"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, EVAL / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_first_json_array_variants():
    score = _load("score")
    assert score.first_json_array('[{"title": "A"}]') == [{"title": "A"}]
    assert score.first_json_array("[]\n\nNote: I could not...") == []
    assert score.first_json_array("Intro [not json] then [1, 2]") == [1, 2]
    assert score.first_json_array("no list at all") is None


def test_classify_request():
    score = _load("score")
    assert score.classify_request("x", None, 10) == "no_json"
    assert score.classify_request("[]", [], 10) == "abstained"
    assert score.classify_request("..", [{}] * 3, 10) == "partial"
    assert score.classify_request("..", [{}] * 10, 10) == "complied"


def test_generate_sends_only_the_prompt_and_resumes(tmp_path, monkeypatch):
    gen = _load("generate")
    monkeypatch.setattr(gen, "HERE", tmp_path)
    (tmp_path / "protocol.json").write_text((EVAL / "protocol.json").read_text(encoding="utf-8"),
                                            encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    sent = []

    def fake_post(url, headers, body):
        sent.append(body)
        return {"model": "claude-test-1", "content": [{"type": "text", "text": "[]"}]}

    args = gen.parse_args(["--provider", "anthropic", "--model", "m", "--repeats", "1",
                           "--delay", "0", "--run", "t"])
    out = gen.run(args, post=fake_post)
    rows = [json.loads(line) for line in out.open(encoding="utf-8")]
    assert len(rows) == 12 and rows[0]["served_model"] == ["claude-test-1"]
    assert all("system" not in b and "tools" not in b for b in sent)
    assert all(len(b["messages"]) == 1 for b in sent)
    assert "Türkiye'de yayımlanmış" in sent[6]["messages"][0]["content"]

    gen.run(args, post=fake_post)  # second run: everything already done
    assert len(sent) == 12
