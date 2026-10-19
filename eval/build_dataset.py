"""Build a labelled set of real and fabricated references from live sources.

Real references are sampled from Crossref (international) and TR Dizin (Turkish).
Fabricated references are derived from real ones by the corruptions that
LLM-hallucinated citations typically show. The output is frozen to
eval/data/refs.jsonl so every evaluation run uses the same cases.

Usage:  uv run --directory server python ../eval/build_dataset.py [--seed 7]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

from akademik_ajan.http import build_url, fetch_json
from akademik_ajan.verify import CROSSREF, Record, _trdizin_query, parse_crossref

OUT = Path(__file__).parent / "data" / "refs.jsonl"
TR_TOPICS = [
    "siber güvenlik", "yapay zeka", "hemşirelik", "öğretmen adayları", "tarım ekonomisi",
    "deprem", "turizm", "muhasebe", "veri madenciliği", "sosyal medya",
]


def usable(r: Record) -> bool:
    return bool(r.doi and r.title and len(r.title) > 15 and r.authors and r.authors[0] and r.year)


def sample_crossref(n: int) -> list[Record]:
    out: list[Record] = []
    while len(out) < n:
        url = build_url(CROSSREF, {"sample": 20, "filter": "type:journal-article"})
        status, data = fetch_json(url)
        if status != 200:
            sys.exit(f"Crossref sample failed: {status}")
        out += [r for r in map(parse_crossref, data["message"]["items"]) if usable(r)]
        time.sleep(3)
    return out[:n]


def sample_trdizin(n: int, rng: random.Random) -> list[Record]:
    out: list[Record] = []
    for topic in TR_TOPICS:
        hits = [r for r in _trdizin_query(topic, fetch_json) if usable(r)]
        rng.shuffle(hits)
        out += hits[:3]
        time.sleep(1)
    rng.shuffle(out)
    return out[:n]


def as_case(r: Record, label: str, kind: str, **override) -> dict:
    case = {
        "label": label, "kind": kind, "origin": r.source,
        "title": r.title, "authors": r.authors[:3], "year": r.year, "doi": r.doi,
    }
    case.update(override)
    return case


def fabricate(reals: list[Record], rng: random.Random) -> list[dict]:
    fakes = []
    for i, r in enumerate(reals):
        other = reals[(i + 1) % len(reals)]
        prefix = r.doi.split("/", 1)[0]
        kind = ["invented_doi", "borrowed_doi", "fake_title", "wrong_year", "invented_work"][i % 5]
        if kind == "invented_doi":
            fakes.append(as_case(r, "fake", kind, doi=f"{prefix}/ak.{rng.randrange(10**6, 10**7)}"))
        elif kind == "borrowed_doi":  # real metadata, someone else's DOI
            fakes.append(as_case(r, "fake", kind, doi=other.doi))
        elif kind == "fake_title":  # plausible title glued onto a real DOI
            fakes.append(as_case(r, "fake", kind, title=other.title))
        elif kind == "wrong_year":
            fakes.append(as_case(r, "fake", kind, year=r.year - rng.choice([3, 4, 5])))
        else:  # title stitched from two real titles, no DOI, made-up author
            a, b = r.title.split(), other.title.split()
            title = " ".join(a[: len(a) // 2] + b[len(b) // 2 :])
            fakes.append(as_case(r, "fake", kind, title=title, doi=None,
                                 authors=[rng.choice(["Yılmaz", "Smith", "Kaya", "Müller"])]))
    return fakes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--crossref", type=int, default=40)
    ap.add_argument("--trdizin", type=int, default=20)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    reals = sample_crossref(args.crossref) + sample_trdizin(args.trdizin, rng)
    cases = []
    for i, r in enumerate(reals):
        cases.append(as_case(r, "real", "with_doi"))
        if i % 2 == 0:  # half of the real works are also tested without their DOI
            cases.append(as_case(r, "real", "title_only", doi=None))
    cases += fabricate(reals, rng)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"wrote {len(cases)} cases to {OUT}")


if __name__ == "__main__":
    main()
