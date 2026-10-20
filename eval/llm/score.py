"""Parse raw model outputs, verify every generated reference, write per-reference results.

Input : eval/llm/raw/<run>.jsonl   (one row per model x topic request, field "raw")
Output: eval/llm/results/<run>.refs.jsonl  (one row per generated reference, with verifier status)
        eval/llm/results/<run>.requests.jsonl (one row per request: compliance / abstention)

Only a JSON array in the reply counts as the model's answer (the protocol asks for one).
References mentioned in prose next to a refusal are not scored; the request is recorded
as an abstention, and `prose_suggestions` notes whether such text was present.

Usage:  uv run --directory server python ../eval/llm/score.py run_a_project_context
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from akademik_ajan.verify import verify_reference

HERE = Path(__file__).parent


def first_json_array(text: str) -> list | None:
    """Return the first top-level JSON array in the text, or None."""
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\[", text or ""):
        try:
            value, _ = decoder.raw_decode(text, m.start())
        except ValueError:
            continue
        if isinstance(value, list):
            return value
    return None


def classify_request(raw: str | None, refs: list | None, n_asked: int) -> str:
    if refs is None:
        return "no_json"
    if len(refs) == 0:
        return "abstained"
    if len(refs) < n_asked:
        return "partial"
    return "complied"


def main() -> None:
    run = sys.argv[1]
    protocol = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
    n_asked = protocol["n_references_per_request"]
    lang = {t["id"]: t["lang"] for t in protocol["topics"]}
    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)

    requests, refs_out = [], []
    for row in map(json.loads, (HERE / "raw" / f"{run}.jsonl").open(encoding="utf-8")):
        refs = first_json_array(row["raw"])
        dicts = [r for r in refs or [] if isinstance(r, dict)]
        status = classify_request(row["raw"], dicts if refs is not None else None, n_asked)
        prose = bool(row["raw"]) and len(re.sub(r"\[.*?\]", "", row["raw"], flags=re.S).strip()) > 40
        requests.append({
            "model": row["model_alias"], "served_model": row["served_model"], "topic_id": row["topic_id"],
            "repeat": row.get("repeat", 0),
            "lang": lang[row["topic_id"]], "request_status": status, "n_refs": len(dicts),
            "prose_suggestions": prose and status != "complied",
        })
        for i, ref in enumerate(dicts):
            year = ref.get("year")
            try:
                year = int(year) if year is not None else None
            except (TypeError, ValueError):
                year = None
            result = verify_reference(
                title=ref.get("title"), authors=ref.get("authors") or None,
                year=year, doi=ref.get("doi"),
            )
            refs_out.append({
                "model": row["model_alias"], "topic_id": row["topic_id"], "lang": lang[row["topic_id"]],
                "repeat": row.get("repeat", 0), "idx": i, "title": ref.get("title"), "authors": ref.get("authors"), "year": year,
                "venue": ref.get("venue"), "doi": ref.get("doi"), "has_doi": bool(ref.get("doi")),
                "status": result["status"],
                "record_doi": result.get("doi"), "record_title": (result.get("record") or {}).get("title"),
                "record_source": (result.get("record") or {}).get("source"),
                "failed_fields": [c["field"] for c in result.get("checks", []) if c["result"] == "fail"],
                "warned_fields": [c["field"] for c in result.get("checks", []) if c["result"] == "warn"],
                "unchecked_sources": result.get("unchecked_sources", []),
            })
            time.sleep(0.3)
        print(row["model_alias"], row["topic_id"], status, len(dicts), flush=True)

    def dump(name: str, rows: list) -> None:
        (out_dir / f"{run}.{name}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    dump("requests", requests)
    dump("refs", refs_out)


if __name__ == "__main__":
    main()
