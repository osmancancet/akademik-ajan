# Contributing

Thanks for helping. The project has one rule that shapes every change: **a feature ships only when it works end to end and has evidence.**

## Before you open a pull request

1. Read [`docs/adr/0001-scope-and-principles.md`](docs/adr/0001-scope-and-principles.md).
2. Run the offline tests:
   ```bash
   cd server
   uv sync --extra dev
   uv run pytest
   ```
   Tests must not touch the network; add canned responses to `server/tests/conftest.py`.
3. If your change alters what works, update [`docs/STATUS.md`](docs/STATUS.md) with the evidence (test names, evaluation numbers).
4. Pin any new dependency exactly and explain why the standard library is not enough.

## Adding a bibliographic source

Open an issue first. A source is accepted when it has a public API (or explicitly allows automated access), its terms and `robots.txt` permit the use, and it adds coverage the existing sources lack. Record the decision as a new ADR in `docs/adr/`.

## Reporting a wrong verdict

The most useful bug report is a citation the verifier got wrong. Please include the citation exactly as written, the status returned, and a link that shows the correct record.
