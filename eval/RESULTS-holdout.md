# Evaluation results: holdout set

_akademik-ajan 0.2.0 · run 2026-10-20 · 150 cases · errors excluded: 0_

| Metric | All | Crossref sample | TR Dizin sample |
|---|---|---|---|
| Real references accepted | 90/90 (100%) | 60/60 (100%) | 30/30 (100%) |
| Fabricated references caught | 60/60 (100%) | 40/40 (100%) | 20/20 (100%) |

## By case type

| label | kind | origin | n | statuses |
|---|---|---|---|---|
| fake | borrowed_doi | crossref | 8 | mismatch: 8 |
| fake | borrowed_doi | trdizin | 4 | mismatch: 4 |
| fake | fake_title | crossref | 8 | mismatch: 8 |
| fake | fake_title | trdizin | 4 | mismatch: 4 |
| fake | invented_doi | crossref | 8 | doi_not_found: 8 |
| fake | invented_doi | trdizin | 4 | doi_not_found: 4 |
| fake | invented_work | crossref | 8 | not_found: 7, possible_match: 1 |
| fake | invented_work | trdizin | 4 | not_found: 4 |
| fake | wrong_year | crossref | 8 | mismatch: 8 |
| fake | wrong_year | trdizin | 4 | mismatch: 4 |
| real | title_only | crossref | 20 | verified: 20 |
| real | title_only | trdizin | 10 | verified: 10 |
| real | with_doi | crossref | 40 | verified: 40 |
| real | with_doi | trdizin | 20 | verified: 18, partial_match: 2 |

Fabricated cases are synthetic corruptions of real records (see `build_dataset.py`), not citations produced by a language model. They model the common failure types but are not a substitute for an evaluation on real LLM output.
