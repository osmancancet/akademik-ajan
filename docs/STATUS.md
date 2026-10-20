# Status

Single source of truth for what works. Anything not listed as **working** does not exist yet.

_Last updated: 2026-10-20 · v0.2.0_

| Component | State | Evidence |
|---|---|---|
| `verify_reference` (DOI path) | working | unit tests; live eval below |
| `verify_reference` (title search) | working | unit tests; live eval below |
| `verify_bibtex` | working | unit tests incl. LaTeX-escaped Turkish titles/authors |
| `lookup_doi`, `search_works` | working | unit tests |
| TR Dizin source (DOI + title, bilingual titles) | working | unit tests; live eval (TR Dizin sample) |
| OpenAlex fallback | working, needs key for heavy use | unit tests; keyless budget is per-IP and small (see README) |
| Rate-limit handling (429/503, quota) | working | unit tests |
| `verify-citations` skill | working | manual review; not yet evaluated end-to-end inside Claude Code |
| Claim ↔ abstract support check | partial | done by the model from `lookup_doi` abstracts; no automated eval yet |
| `search_literature` (Crossref + TR Dizin + OpenAlex, merge, relevance) | working | unit tests (`test_literature.py`); live smoke test 2026-10-20 |
| `export_bibtex` | working | unit tests incl. LaTeX escaping, Turkish characters, unique keys; live smoke test |
| `literature-review` skill | working | manual review; not yet evaluated end-to-end inside Claude Code |
| Verifier on LLM-written references | measured (pilot) | [`eval/llm/REPORT.md`](../eval/llm/REPORT.md): blind web adjudication of run A |
| `render_response_letter` (Markdown/LaTeX letter, change log, completeness check) | working | unit tests (`test_response.py`); MCP call test |
| `reviewer-response` skill | working | manual review; not yet evaluated end-to-end inside Claude Code |
| Journal compliance module | planned | — |
| TR↔EN terminology module | planned | — |

## Live evaluation (2026-10-20)

Two disjoint sets of 150 cases each: 90 real references (60 sampled from Crossref, 30 from TR Dizin; each tested with DOI, half also without) and 60 fabricated ones (invented DOI, borrowed DOI, fake title on a real DOI, wrong year, stitched-together work). The **dev** set was used to find and fix bugs; the **holdout** set (different seed, different TR Dizin topics) was built afterwards and never used for tuning.

| | dev | holdout |
|---|---|---|
| Real references accepted | 86/90 (96%) | **89/90 (99%)** |
| Fabricated references caught | 60/60 (100%) | **60/60 (100%)** |
| Service errors | 0 | 0 |

Re-run with v0.2.0 (2026-10-20): holdout 90/90 real accepted, 60/60 fabricated caught, 0 errors. A first v0.2.0 run gave 88/90 and exposed a bug (a TR Dizin duplicate carrying the English title was dropped), which was fixed. Because that fix came from a holdout case, the holdout set is no longer fully unseen; the 90/90 figure is optimistic.

"Caught" includes `possible_match` (one holdout case), which asks the user to confirm rather than accepting. Details: [`eval/RESULTS-dev.md`](../eval/RESULTS-dev.md), [`eval/RESULTS-holdout.md`](../eval/RESULTS-holdout.md). Reproduce with `eval/build_dataset.py` and `eval/run_eval.py`.

**Caveat:** fabricated cases are synthetic corruptions of real records, not citations written by a language model. An evaluation on real LLM-generated reference lists is the next step before claiming real-world detection rates.

### Remaining misses on real references

- Title-only search for some TR Dizin works returns `not_found` (3 of 20 across both sets) — short or generic Turkish titles where the search ranks other works higher.
- One dev case: a TR Dizin record whose Crossref and TR Dizin titles differ beyond the similarity threshold.

## LLM-written references (run A pilot)

See [`eval/llm/REPORT.md`](../eval/llm/REPORT.md), generated from `eval/llm/numbers.json`. In short: under the strict rule the verifier flagged every reference the adjudicators found wrong, and its main weakness is false alarms on conference papers cited without a DOI when OpenAlex is unavailable. Run B (clean API condition) is pending.

## Known limitations

- Without `OPENALEX_API_KEY`, conference papers without a DOI (NeurIPS, ICLR, USENIX) are often `not_found` or `possible_match`: the main source of false alarms in the LLM study.
- Literature search relevance is lexical; Crossref's candidate pool for multi-word Turkish queries can be noisy, so the skill runs several query variants and screens abstracts.
- Title similarity uses `difflib`; very short or generic titles ("Introduction") can produce false `possible_match`.
- Crossref's year can differ from the print year by one; reported as `partial_match`, not failure.
- Works only on DergiPark (not in TR Dizin) and theses (YÖK Tez) cannot be checked automatically — see ADR-0002.

## Not yet measured

- Token/latency overhead of the plugin in a Claude Code session.
- Detection rate on LLM-generated reference lists in the clean API condition (run B); run A is a pilot in agent context.
