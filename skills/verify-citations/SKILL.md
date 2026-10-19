---
name: verify-citations
description: Verify that every reference in a manuscript, reference list or BibTeX file is a real publication whose title, authors and year match. Use before submitting a paper, when reviewing AI-drafted text, or whenever the user asks to check, validate or audit citations or a .bib file.
---

# Verify citations

Fabricated or mangled references are the most damaging error in AI-assisted academic writing. This skill checks each reference against Crossref, TR Dizin and OpenAlex through the `akademik-ajan` MCP tools and reports what it found. It never "fixes" a reference from memory.

## Procedure

1. **Collect the references.**
   - A `.bib` file or BibTeX text → call `verify_bibtex` with the full text.
   - A reference list or in-text citations → extract each reference's DOI (if any), title, author list and year, then call `verify_reference` once per reference. Prefer the DOI when present.
2. **Read the status of each result** and act on it:

   | status | meaning | what to tell the user |
   |---|---|---|
   | `verified` | record found, all supplied fields agree | fine |
   | `partial_match` | found; small differences (year ±1, near title) | show the differing field and the record's value |
   | `mismatch` | the DOI belongs to a **different** paper | flag as a likely fabricated or corrupted reference |
   | `possible_match` | no DOI; close candidate found | show the candidate, ask the user to confirm |
   | `doi_not_found` | DOI resolves nowhere | flag; DOI is wrong or invented |
   | `not_found` | no DOI and no plausible candidate | flag; cannot confirm the work exists |
   | `error` | service unreachable | say verification could not run; **do not** call the reference fake |

3. **Claim check (when the user gives the sentence that cites the source).** Call `lookup_doi` to get the abstract and judge whether the abstract supports the claim. Say plainly when the abstract is missing or too short to judge; never infer support from the title alone.
4. **Report** as a table: key/number, status, problem, suggested correction. A suggested correction may only use values returned by the tools (e.g. the record's real year or DOI).

## Rules

- Never invent or "complete" a DOI, author, page range or year from memory.
- `error` is not evidence of fabrication.
- Non-English titles (e.g. Turkish) are compared with diacritics folded and against every language version of the record's title; a `possible_match` still needs the user's confirmation.
- Turkish sources: TR Dizin is searched automatically. Theses (YÖK Ulusal Tez Merkezi) and journals only on DergiPark cannot be checked automatically — when such a reference comes back `not_found`, say so and ask the user to confirm it manually instead of calling it fabricated.
- Respect rate limits: verify sequentially; for very long lists, verify in batches of ~50 and report progress.
