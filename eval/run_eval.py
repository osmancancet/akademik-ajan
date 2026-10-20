"""Run the verifier on eval/data/<name>.jsonl and report detection rates.

A real reference counts as accepted when the status is `verified` or
`partial_match`. A fabricated one counts as caught when the status is anything
except those two. `error` results are excluded from both rates and reported.

Usage:  uv run --directory server python ../eval/run_eval.py [dev|holdout]
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from akademik_ajan import __version__
from akademik_ajan.verify import verify_reference

HERE = Path(__file__).parent
ACCEPT = {"verified", "partial_match"}


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "dev"
    cases = [json.loads(line) for line in (HERE / "data" / f"{name}.jsonl").open(encoding="utf-8")]
    rows = []
    for c in cases:
        r = verify_reference(title=c["title"], authors=c["authors"], year=c["year"], doi=c["doi"])
        rows.append({**c, "status": r["status"], "found_source": (r.get("record") or {}).get("source")})
        time.sleep(0.3)  # stay polite to the public APIs

    (HERE / "data" / f"{name}.results.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")

    groups: dict[tuple[str, str, str], Counter] = defaultdict(Counter)
    for x in rows:
        groups[(x["label"], x["kind"], x["origin"])][x["status"]] += 1

    def rate(label: str, pred, origin: str | None = None) -> str:
        sel = [x for x in rows if x["label"] == label and x["status"] != "error"
               and (origin is None or x["origin"] == origin)]
        hit = sum(pred(x["status"]) for x in sel)
        return f"{hit}/{len(sel)} ({100 * hit / len(sel):.0f}%)" if sel else "n/a"

    accepted = lambda s: s in ACCEPT  # noqa: E731
    caught = lambda s: s not in ACCEPT  # noqa: E731
    lines = [
        f"# Evaluation results: {name} set",
        "",
        f"_akademik-ajan {__version__} · run {date.today().isoformat()} · {len(rows)} cases · "
        f"errors excluded: {sum(x['status'] == 'error' for x in rows)}_",
        "",
        "| Metric | All | Crossref sample | TR Dizin sample |",
        "|---|---|---|---|",
        f"| Real references accepted | {rate('real', accepted)} | {rate('real', accepted, 'crossref')} "
        f"| {rate('real', accepted, 'trdizin')} |",
        f"| Fabricated references caught | {rate('fake', caught)} | {rate('fake', caught, 'crossref')} "
        f"| {rate('fake', caught, 'trdizin')} |",
        "",
        "## By case type",
        "",
        "| label | kind | origin | n | statuses |",
        "|---|---|---|---|---|",
    ]
    for (label, kind, origin), cnt in sorted(groups.items()):
        statuses = ", ".join(f"{k}: {v}" for k, v in cnt.most_common())
        lines.append(f"| {label} | {kind} | {origin} | {sum(cnt.values())} | {statuses} |")
    lines += [
        "",
        "Fabricated cases are synthetic corruptions of real records (see `build_dataset.py`), "
        "not citations produced by a language model. They model the common failure types but "
        "are not a substitute for an evaluation on real LLM output.",
    ]
    (HERE / f"RESULTS-{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
