---
name: reviewer-response
description: Turn journal reviewer comments into a point-by-point response letter and a change log. Use when the user shares reviews, a decision letter (major/minor revision), or asks to answer reviewers, draft a rebuttal or a response to reviewers, in Turkish or English.
---

# Reviewer response

Produces a response-to-reviewers letter whose every point is traceable to a reviewer comment and to a change in the manuscript. The `render_response_letter` tool lays out the letter and checks it; the drafting is yours.

## Procedure

1. **Collect** the decision letter and every review, plus the manuscript if available (read it before drafting so responses can point to real sections).
2. **Split into points.** Number them `R<reviewer>.<n>` (editor: `E.<n>`). Quote each comment verbatim; split a comment only when it asks for two separate things. Never paraphrase inside the quote.
3. **Classify** each point for the user: major or minor, and its kind (clarification, new analysis or experiment, citation request, scope disagreement, language). Show this table before drafting when there are more than ~10 points, so the user can decide which to accept or decline.
4. **Draft** each response:
   - Thank once in the opening, not in every point.
   - State what changed and where (section, figure, table, line or page). If the manuscript is available, quote the revised sentence.
   - When declining, give the scientific reason and, where possible, a partial accommodation (a limitation sentence, an added discussion).
   - A point that needs something only the authors can supply (new experiment, data, decision) gets `status: "author_action"` and a note of what is needed. Never write a result that has not been produced.
5. **Citation requests.** Find candidates with `search_literature`, show them, and verify the chosen ones with `verify_reference` before adding them. Never add a reference from memory.
6. **Render** with `render_response_letter` (Markdown, or LaTeX for a LaTeX submission). Fix every item in `check.problems`. Report `check.author_action` to the user as their to-do list.
7. **Deliver** the letter, the change log, and the author to-do list. Offer to apply the agreed text changes to the manuscript.

## Style

- Courteous and direct; no defensive language, no excessive apology.
- Responses state facts that can be checked in the revised manuscript.
- Match the language of the reviews unless the user asks otherwise.
