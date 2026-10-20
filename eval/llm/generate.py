"""Closed-book reference generation through provider APIs (clean condition, run B).

Each request sends only the protocol prompt as a single user turn: no system prompt,
no tools, fixed sampling settings. Every reply is stored verbatim with the model ID the
provider reports, so the raw file can be scored with score.py.

Providers
  anthropic : https://api.anthropic.com/v1/messages     (key: ANTHROPIC_API_KEY)
  openai    : any OpenAI-compatible /chat/completions    (key: OPENAI_API_KEY,
              base URL: --base-url, e.g. https://api.openai.com/v1 or an OpenRouter URL)

Examples
  uv run --directory server python ../eval/llm/generate.py --provider anthropic \
      --model claude-haiku-5-5 --model claude-sonnet-5-5 --model claude-opus-5-5 --repeats 5
  uv run --directory server python ../eval/llm/generate.py --provider openai \
      --base-url https://api.openai.com/v1 --model <model-id> --repeats 5

Requests already present in the output file are skipped, so an interrupted run resumes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).parent
Transport = Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]]


def http_post(url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={**headers, "content-type": "application/json"}
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 529) and attempt < 4:
                time.sleep(min(60, 5 * 2**attempt))
                continue
            raise RuntimeError(f"{exc.code}: {exc.read(500).decode('utf-8', 'replace')}") from exc
    raise RuntimeError("unreachable")


def render(protocol: dict[str, Any], topic: dict[str, str]) -> str:
    template = protocol["template_tr" if topic["lang"] == "tr" else "template_en"]
    return template.format(topic=topic["topic"], n=protocol["n_references_per_request"])


def call_anthropic(model: str, prompt: str, temperature: float, post: Transport) -> tuple[str, str]:
    data = post(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
        {"model": model, "max_tokens": 4096, "temperature": temperature,
         "messages": [{"role": "user", "content": prompt}]},
    )
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    return text, data.get("model", model)


def call_openai(model: str, prompt: str, temperature: float, post: Transport,
                base_url: str) -> tuple[str, str]:
    data = post(
        f"{base_url.rstrip('/')}/chat/completions",
        {"authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        {"model": model, "temperature": temperature, "max_tokens": 4096,
         "messages": [{"role": "user", "content": prompt}]},
    )
    return data["choices"][0]["message"]["content"] or "", data.get("model", model)


def run(args: argparse.Namespace, post: Transport = http_post) -> Path:
    protocol = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
    out = HERE / "raw" / f"{args.run}.jsonl"
    out.parent.mkdir(exist_ok=True)
    done = set()
    if out.exists():
        for row in map(json.loads, out.open(encoding="utf-8")):
            done.add((row["model_alias"], row["topic_id"], row["repeat"]))

    with out.open("a", encoding="utf-8") as f:
        for model in args.model:
            for rep in range(args.repeats):
                for topic in protocol["topics"]:
                    key = (model, topic["id"], rep)
                    if key in done:
                        continue
                    prompt = render(protocol, topic)
                    if args.provider == "anthropic":
                        text, served = call_anthropic(model, prompt, args.temperature, post)
                    else:
                        text, served = call_openai(model, prompt, args.temperature, post, args.base_url)
                    f.write(json.dumps({
                        "run": args.run, "provider": args.provider, "model_alias": model,
                        "served_model": [served], "topic_id": topic["id"], "repeat": rep,
                        "temperature": args.temperature, "tools_used": [], "raw": text,
                    }, ensure_ascii=False) + "\n")
                    f.flush()
                    print(model, rep, topic["id"], len(text), flush=True)
                    time.sleep(args.delay)
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", choices=["anthropic", "openai"], required=True)
    ap.add_argument("--model", action="append", required=True, help="repeatable")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--base-url", default="https://api.openai.com/v1")
    ap.add_argument("--run", default="run_b_api_clean")
    ap.add_argument("--delay", type=float, default=1.0)
    return ap.parse_args(argv)


if __name__ == "__main__":
    a = parse_args()
    key = "ANTHROPIC_API_KEY" if a.provider == "anthropic" else "OPENAI_API_KEY"
    if not os.environ.get(key):
        sys.exit(f"Set {key} first.")
    print("wrote", run(a))
