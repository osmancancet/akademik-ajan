# ADR-0002: Turkish bibliographic sources

- Status: accepted
- Date: 2026-10-20

## Context

Many Turkish journal articles lack a Crossref DOI, or appear in OpenAlex with incomplete metadata. Turkish academics need those works verifiable too. Candidate sources were probed on 2026-10-20:

| Source | Finding | Decision |
|---|---|---|
| TR Dizin (ULAKBİM) | Public JSON search endpoint used by its own web frontend; returns titles per language, authors, year, journal, DOI | **Use** |
| DergiPark | `robots.txt` disallows `/search`; searches redirect to a bot-verification page. OAI-PMH exists but is for bulk harvesting, not lookup | **Do not scrape.** Revisit if an official search API appears |
| YÖK Ulusal Tez Merkezi | No API; search is form/session based | **Not supported.** Theses are reported as `not_found` with this caveat |

## Decision

- Add TR Dizin as a third resolver: DOI path Crossref → OpenAlex → TR Dizin; title path Crossref, then TR Dizin and OpenAlex **only if** no confident match yet (keeps request volume low).
- Match a claimed title against **every** language version of a record's title (TR Dizin often lists the English title first).
- The TR Dizin endpoint is undocumented. Requests are sequential, identify the tool in `User-Agent`, and are retried with back-off on 429/503. If ULAKBİM publishes terms or an official API, follow them.

## Consequences

Turkish works indexed in TR Dizin become verifiable without a DOI. Works only on DergiPark (not in TR Dizin) or theses remain unverifiable automatically; the skill tells the user to check those manually.
