# akademik-ajan — notes for Claude

Read `docs/adr/0001-scope-and-principles.md` before changing scope.

- Code, comments and docs: English. Talk to the maintainer (Osman Can) in Turkish.
- Never add a tool that does not work end-to-end. Update `docs/STATUS.md` with evidence for every change in what works.
- Never write outside the repo or touch user-global config.
- Pin new dependencies exactly; prefer the standard library.
- Bibliographic data must come from an API response, never from model memory.
- Tests: `cd server && uv run pytest` (offline, canned responses in `tests/conftest.py`).
- Record notable decisions as `docs/adr/NNNN-title.md`.
