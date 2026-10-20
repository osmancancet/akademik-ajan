"""Run B without an API key: closed-book generation through the local Claude Code CLI.

Uses the maintainer's own Claude subscription through `claude -p`, configured to be as
close to a bare model call as the CLI allows:

  * runs in a fresh empty directory, so no project CLAUDE.md or project settings apply
  * --setting-sources project   (user-level settings, hooks and plugins are not loaded)
  * --system-prompt             replaces Claude Code's system prompt with one neutral line
  * --tools ""                  no tools at all
  * --strict-mcp-config         no MCP servers
  * --no-session-persistence    nothing is saved between requests

Each request is independent. The served model ID is read from the CLI's JSON output.
Requests already in the output file are skipped, so an interrupted run resumes.

Usage (from the repository's server/ directory):
  uv run python ../eval/llm/generate_cli.py                      # haiku, sonnet, opus x 5 repeats
  uv run python ../eval/llm/generate_cli.py --model sonnet --repeats 2
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

HERE = Path(__file__).parent
NEUTRAL_SYSTEM_PROMPT = "You are a helpful assistant."
Runner = Callable[[list[str], str], tuple[int, str, str]]


def run_process(cmd: list[str], cwd: str) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=600)
    return proc.returncode, proc.stdout, proc.stderr


def build_cmd(prompt: str, model: str) -> list[str]:
    return [
        "claude", "-p", prompt,
        "--model", model,
        "--system-prompt", NEUTRAL_SYSTEM_PROMPT,
        "--tools", "",
        "--setting-sources", "project",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--output-format", "json",
    ]


def render(protocol: dict, topic: dict) -> str:
    template = protocol["template_tr" if topic["lang"] == "tr" else "template_en"]
    return template.format(topic=topic["topic"], n=protocol["n_references_per_request"])


def parse_cli_json(stdout: str) -> tuple[str, list[str], bool]:
    """Return (reply text, served model IDs, is_error) from `claude -p --output-format json`."""
    data = json.loads(stdout)
    if isinstance(data, list):  # some versions emit a list of events; the last is the result
        data = next((d for d in reversed(data) if d.get("type") == "result"), data[-1])
    served = sorted((data.get("modelUsage") or {}).keys())
    return data.get("result") or "", served, bool(data.get("is_error"))


def run(args: argparse.Namespace, runner: Runner = run_process) -> Path:
    protocol = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
    out = HERE / "raw" / f"{args.run}.jsonl"
    out.parent.mkdir(exist_ok=True)
    done = set()
    if out.exists():
        for row in map(json.loads, out.open(encoding="utf-8")):
            done.add((row["model_alias"], row["topic_id"], row["repeat"]))

    user_md = (Path.home() / ".claude" / "CLAUDE.md").exists()
    if user_md:
        print("WARNING: ~/.claude/CLAUDE.md exists and may be loaded into every request. "
              "Rename it for the duration of the run for a clean condition; it is recorded per row.",
              file=sys.stderr)

    failures = 0
    with out.open("a", encoding="utf-8") as f:
        for model in args.model:
            for rep in range(args.repeats):
                for topic in protocol["topics"]:
                    if (model, topic["id"], rep) in done:
                        continue
                    workdir = tempfile.mkdtemp(prefix="akademik-ajan-runb-")
                    try:
                        code, stdout, stderr = runner(build_cmd(render(protocol, topic), model), workdir)
                    finally:
                        shutil.rmtree(workdir, ignore_errors=True)
                    try:
                        text, served, is_error = parse_cli_json(stdout) if code == 0 else ("", [], True)
                    except (ValueError, AttributeError, IndexError):
                        text, served, is_error = "", [], True
                    if is_error:
                        failures += 1
                        print(f"FAILED {model} {rep} {topic['id']}: {(stderr or stdout)[:300]}",
                              file=sys.stderr, flush=True)
                        if failures >= 3:
                            sys.exit("Three failures in a row; stopping. Re-run the same command to resume.")
                        continue
                    failures = 0
                    f.write(json.dumps({
                        "run": args.run, "provider": "claude-code-cli", "model_alias": model,
                        "served_model": served, "topic_id": topic["id"], "repeat": rep,
                        "system_prompt": NEUTRAL_SYSTEM_PROMPT, "user_claude_md_present": user_md,
                        "tools_used": [], "raw": text,
                    }, ensure_ascii=False) + "\n")
                    f.flush()
                    print(model, rep, topic["id"], served, len(text), flush=True)
                    time.sleep(args.delay)
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", action="append", help="repeatable; default: haiku, sonnet, opus")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--run", default="run_b_cli_subscription")
    ap.add_argument("--delay", type=float, default=2.0)
    args = ap.parse_args(argv)
    args.model = args.model or ["haiku", "sonnet", "opus"]
    return args


if __name__ == "__main__":
    if not shutil.which("claude"):
        sys.exit("Claude Code CLI not found. Install it and sign in with `claude` first.")
    print("wrote", run(parse_args()))
