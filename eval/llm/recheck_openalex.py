"""Re-verify run A's strict false alarms while OpenAlex is reachable.

Selects references that adjudicators labelled `correct` (or verified-and-not-sampled)
but that the current verifier did not mark `verified`, runs the verifier again, and
records whether OpenAlex could be consulted. Writes results/run_a_openalex_recheck.jsonl.

Usage:  uv run --directory server python ../eval/llm/recheck_openalex.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from akademik_ajan.verify import verify_reference

RES = Path(__file__).parent / "results"


def main() -> None:
    refs = [json.loads(line) for line in (RES / "run_a_project_context.refs.jsonl").open(encoding="utf-8")]
    labels = {x["ref_id"]: x for x in json.loads((RES / "run_a_adjudication_labels.json").read_text())}
    rows = []
    for i, r in enumerate(refs):
        rid = f"A{i:03d}"
        correct = labels[rid]["label"] == "correct" if rid in labels else True
        if not correct or r["status"] == "verified":
            continue
        out = verify_reference(title=r["title"], authors=r["authors"] or None, year=r["year"], doi=r["doi"])
        rows.append({
            "ref_id": rid, "before": r["status"], "after": out["status"], "has_doi": r["has_doi"],
            "after_source": (out.get("record") or {}).get("source"),
            "openalex_unchecked": "openalex" in out.get("unchecked_sources", []),
        })
        print(rid, r["status"], "->", out["status"], rows[-1]["after_source"],
              "UNCHECKED" if rows[-1]["openalex_unchecked"] else "", flush=True)
        time.sleep(0.5)
    (RES / "run_a_openalex_recheck.jsonl").write_text(
        "".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")


if __name__ == "__main__":
    main()
