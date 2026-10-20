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


def test_generate_cli_runs_in_empty_dir_with_clean_flags(tmp_path, monkeypatch):
    gen = _load("generate_cli")
    monkeypatch.setattr(gen, "HERE", tmp_path)
    (tmp_path / "protocol.json").write_text((EVAL / "protocol.json").read_text(encoding="utf-8"),
                                            encoding="utf-8")
    calls = []

    def fake_runner(cmd, cwd):
        calls.append((cmd, list(Path(cwd).iterdir())))
        out = {"type": "result", "is_error": False, "result": "[]",
               "modelUsage": {"claude-haiku-5-5": {"inputTokens": 1}}}
        return 0, json.dumps(out), ""

    args = gen.parse_args(["--model", "haiku", "--repeats", "1", "--delay", "0", "--run", "t"])
    out = gen.run(args, runner=fake_runner)
    rows = [json.loads(line) for line in out.open(encoding="utf-8")]
    assert len(rows) == 12 and rows[0]["served_model"] == ["claude-haiku-5-5"]
    cmd, contents = calls[0]
    assert contents == []  # fresh empty working directory: no CLAUDE.md, no project settings
    for flag, value in (("--tools", ""), ("--setting-sources", "project"),
                        ("--system-prompt", gen.NEUTRAL_SYSTEM_PROMPT), ("--model", "haiku")):
        assert cmd[cmd.index(flag) + 1] == value
    assert "--strict-mcp-config" in cmd and "--no-session-persistence" in cmd


def test_generate_cli_skips_failures_and_resumes(tmp_path, monkeypatch):
    gen = _load("generate_cli")
    monkeypatch.setattr(gen, "HERE", tmp_path)
    (tmp_path / "protocol.json").write_text((EVAL / "protocol.json").read_text(encoding="utf-8"),
                                            encoding="utf-8")
    n = {"i": 0}

    def flaky(cmd, cwd):
        n["i"] += 1
        if n["i"] == 2:
            return 1, "", "rate limited"
        return 0, json.dumps({"type": "result", "result": "[]", "modelUsage": {}}), ""

    args = gen.parse_args(["--model", "opus", "--repeats", "1", "--delay", "0", "--run", "t"])
    out = gen.run(args, runner=flaky)
    assert sum(1 for _ in out.open()) == 11
    gen.run(args, runner=flaky)  # resume fills the gap
    assert sum(1 for _ in out.open()) == 12


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
