# ADR-0003: Design of the LLM-generated reference study

- Status: accepted
- Date: 2026-10-20

## Context

The synthetic evaluation (corrupted real records) measures the verifier on error types we chose. A publishable claim needs references that language models actually write, and ground truth that does not come from the verifier itself.

## Decision

**Protocol** (`eval/llm/protocol.json`): 12 topics (6 international, prompted in English; 6 Turkish-literature topics, prompted in Turkish), 10 references per request, closed book (no tools), fixed JSON output schema. The prompt asks for references as a writer would, without mentioning evaluation.

**Run A: agent context (pilot, done).** Claude Haiku, Sonnet and Opus (served as `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`) were called as Claude Code sub-agents. Their context therefore contained the Claude Code system prompt, a profile of the user, and this repository's `CLAUDE.md`, which includes the rule "bibliographic data must come from an API response, never from model memory". Several Turkish-topic refusals cite that rule. Run A is reported as an *agent-in-context* condition, not as model behaviour in isolation. No tool calls were made in any of the 36 requests (checked in the transcripts).

An attempt to remove `CLAUDE.md` temporarily to obtain a cleaner condition was blocked by the environment's safety classifier (self-modification of guardrail instructions). The file was restored unchanged and no workaround was attempted.

**Run B: clean API condition (to run).** `eval/llm/generate.py` sends only the protocol prompt as one user turn (no system prompt, no tools, temperature 1.0, 5 repeats per model × topic) through the Anthropic API or any OpenAI-compatible API. It needs the maintainer's API key and is the main experiment for a manuscript. Run A's adjudicated sample served as the development set for verifier fixes, so **Run B is the only unbiased test of the fixed verifier**.

**Ground truth.** Blind web adjudication by separate agents that see only the citation (never the verifier status, never the repository): every reference the verifier did not mark `verified`, plus a random sample of verified ones (seed 20261020), shuffled. Labels: `correct`, `exists_with_errors` (with the wrong fields), `not_found`. For Run B, a human check of the adjudicators' `not_found` and `exists_with_errors` labels is required before publication.

**Numbers.** Every figure comes from `eval/llm/analyze.py` → `numbers.json`.

## Consequences

- Run A answers "what reaches a user of an agent like this one" and documents that a project-level instruction plus model judgement produced abstention on Turkish topics. It cannot separate the two causes.
- Run A's verifier numbers after fixes are optimistic; they are reported separately from the pre-fix (v0.1.0) numbers.
