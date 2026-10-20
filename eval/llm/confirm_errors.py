"""Confirm adjudicated DOI/title errors against the Crossref record of the cited DOI.

For each reference the adjudicators labelled `exists_with_errors` and that carries a DOI,
fetch what the DOI resolves to and store it next to the citation. Writes
results/run_a_error_confirmation.json, which report.py reads.

Usage:  uv run --directory server python ../eval/llm/confirm_errors.py
"""

from __future__ import annotations

import json
from pathlib import Path

from akademik_ajan.verify import lookup_doi, title_similarity

RES = Path(__file__).parent / "results"


def main() -> None:
    refs = [json.loads(line) for line in (RES / "run_a_project_context.refs.jsonl").open(encoding="utf-8")]
    labels = json.loads((RES / "run_a_adjudication_labels.json").read_text(encoding="utf-8"))
    rows = []
    for lab in labels:
        if lab["label"] != "exists_with_errors":
            continue
        ref = refs[int(lab["ref_id"][1:])]
        rec = lookup_doi(ref["doi"]) if ref.get("doi") else None
        rows.append({
            "ref_id": lab["ref_id"], "model": ref["model"], "cited_title": ref["title"],
            "cited_doi": ref["doi"], "doi_resolves_to": rec.title if rec else None,
            "title_similarity": title_similarity(ref["title"], rec.title) if rec else None,
            "confirmed": bool(rec) and title_similarity(ref["title"], rec.title) < 0.9,
            "adjudicator_wrong_fields": lab["wrong_fields"],
        })
    (RES / "run_a_error_confirmation.json").write_text(
        json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for r in rows:
        print(r["ref_id"], r["confirmed"], r["title_similarity"], "|", r["doi_resolves_to"])


if __name__ == "__main__":
    main()
