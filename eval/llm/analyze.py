"""Compute every number of the LLM-reference study from result files.

Inputs (eval/llm/results/):
  <run>.requests.jsonl, <run>.refs.jsonl          current verifier
  <run>.v010.requests.jsonl, <run>.v010.refs.jsonl  verifier v0.1.0 (before fixes from adjudication)
  run_a_adjudication_labels.json                  blind web adjudication
  run_a_adjudication_sample.key.json              v0.1.0 status of each adjudicated reference
Outputs:
  numbers.json  (the only source for figures quoted in REPORT.md / a manuscript)
  REPORT.md

Reference IDs are positional ("A000" = first reference of the run), stable because
parsing is deterministic.

Usage:  python eval/llm/analyze.py run_a_project_context
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
RES = HERE / "results"
MODELS = ["haiku", "sonnet", "opus"]
ACCEPT = {"verified"}  # strict: anything else is shown to the user as a problem


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def main() -> None:
    run = sys.argv[1] if len(sys.argv) > 1 else "run_a_project_context"
    req = load_jsonl(RES / f"{run}.requests.jsonl")
    refs_new = load_jsonl(RES / f"{run}.refs.jsonl")
    refs_old = load_jsonl(RES / f"{run}.v010.refs.jsonl")
    assert len(refs_new) == len(refs_old), "re-scored run must parse to the same references"
    for i, (a, b) in enumerate(zip(refs_old, refs_new)):
        assert (a["title"], a["doi"]) == (b["title"], b["doi"]), f"reference {i} differs"
        a["ref_id"] = b["ref_id"] = f"A{i:03d}"
    labels = {x["ref_id"]: x for x in json.loads((RES / "run_a_adjudication_labels.json").read_text())}
    key_v010 = json.loads((RES / "run_a_adjudication_sample.key.json").read_text())

    n: dict = {"run": run}

    # 1. Request-level behaviour: did the model produce a list?
    n["requests"] = {
        f"{m}_{lang}": dict(Counter(r["request_status"] for r in req if r["model"] == m and r["lang"] == lang))
        for m in MODELS for lang in ("en", "tr")
    }
    n["served_models"] = sorted({s for r in req for s in r["served_model"]})
    n["references_total"] = len(refs_new)
    n["references_by_model_lang"] = {
        f"{m}_{lang}": sum(1 for r in refs_new if r["model"] == m and r["lang"] == lang)
        for m in MODELS for lang in ("en", "tr")
    }
    n["with_doi_share"] = round(sum(r["has_doi"] for r in refs_new) / len(refs_new), 4)

    # 2. Verifier status distributions
    for tag, refs in (("v010", refs_old), ("current", refs_new)):
        n[f"status_{tag}"] = dict(Counter(r["status"] for r in refs))
        n[f"status_{tag}_by_model"] = {m: dict(Counter(r["status"] for r in refs if r["model"] == m))
                                       for m in MODELS}

    # 3. Ground truth from blind adjudication
    sample_ids = set(labels)
    flagged_v010 = {r["ref_id"] for r in refs_old if r["status"] not in ACCEPT}
    assert flagged_v010 <= sample_ids, "every v0.1.0-flagged reference must be adjudicated"
    verified_v010 = [r["ref_id"] for r in refs_old if r["status"] in ACCEPT]
    verified_sampled = [i for i in verified_v010 if i in sample_ids]
    verified_sampled_wrong = sum(labels[i]["label"] != "correct" for i in verified_sampled)
    n["adjudication"] = {
        "sample_size": len(sample_ids),
        "design": "all v0.1.0-flagged references plus a random sample of v0.1.0-verified ones",
        "flagged_in_sample": len(flagged_v010),
        "verified_population": len(verified_v010),
        "verified_sampled": len(verified_sampled),
        "verified_sampled_wrong": verified_sampled_wrong,
        "verified_error_ci95": wilson(verified_sampled_wrong, len(verified_sampled)),
        "labels": dict(Counter(x["label"] for x in labels.values())),
    }
    errors = [i for i, x in labels.items() if x["label"] != "correct"]
    fabricated = [i for i, x in labels.items() if x["label"] == "not_found"]
    by_id = {r["ref_id"]: r for r in refs_new}
    n["errors"] = {
        "count": len(errors),
        "fabricated_count": len(fabricated),
        "wrong_fields": dict(Counter(f for i in errors for f in labels[i]["wrong_fields"])),
        "by_model": {m: sum(by_id[i]["model"] == m for i in errors) for m in MODELS},
        "rate_by_model": {
            m: {"k": sum(by_id[i]["model"] == m for i in errors),
                "n": sum(r["model"] == m for r in refs_new),
                "ci95": wilson(sum(by_id[i]["model"] == m for i in errors),
                               sum(r["model"] == m for r in refs_new))}
            for m in MODELS
        },
        "note": "unsampled v0.1.0-verified references are assumed correct; see verified_error_ci95",
    }

    # 4. Verifier accuracy against adjudication (references treated as correct when
    #    adjudicated correct or verified-but-not-sampled).
    def truth(i: str) -> bool:
        return labels[i]["label"] == "correct" if i in labels else True

    for tag, refs in (("v010", refs_old), ("current", refs_new)):
        tp = sum(1 for r in refs if not truth(r["ref_id"]) and r["status"] not in ACCEPT)
        fn = sum(1 for r in refs if not truth(r["ref_id"]) and r["status"] in ACCEPT)
        fp = sum(1 for r in refs if truth(r["ref_id"]) and r["status"] not in ACCEPT)
        tn = sum(1 for r in refs if truth(r["ref_id"]) and r["status"] in ACCEPT)
        mism = [r for r in refs if r["status"] == "mismatch"]
        mism_ok = sum(not truth(r["ref_id"]) for r in mism)
        fp_ids = [r["ref_id"] for r in refs if truth(r["ref_id"]) and r["status"] not in ACCEPT]
        n[f"verifier_{tag}"] = {
            "tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "recall": round(tp / (tp + fn), 4) if tp + fn else None,
            "recall_ci95": wilson(tp, tp + fn),
            "false_alarm_rate": round(fp / (fp + tn), 4) if fp + tn else None,
            "false_alarm_ci95": wilson(fp, fp + tn),
            "mismatch_flags": len(mism), "mismatch_true_errors": mism_ok,
            "false_alarms_by_status": dict(Counter(r["status"] for r in refs if r["ref_id"] in fp_ids)),
            "false_alarms_without_doi": sum(1 for r in refs if r["ref_id"] in fp_ids and not r["has_doi"]),
            "false_alarms_openalex_unchecked": sum(1 for r in refs if r["ref_id"] in fp_ids
                                                   and "openalex" in r.get("unchecked_sources", [])),
        }

    (HERE / "numbers.json").write_text(json.dumps(n, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(n, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
