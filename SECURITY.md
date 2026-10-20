# Security policy

## Reporting

Please report vulnerabilities privately through GitHub's "Report a vulnerability" (Security tab) rather than a public issue. Expect an acknowledgement within a week.

## Scope and design

- The MCP server makes outbound HTTPS GET requests to `api.crossref.org`, `api.openalex.org` and `search.trdizin.gov.tr` only. It does not open listening sockets; it talks to Claude Code over stdio.
- `OPENALEX_API_KEY` is sent only to `api.openalex.org`, as an `Authorization` header, never in a URL.
- The plugin writes nothing outside its own directory and does not modify user-global configuration.
- Text returned by bibliographic APIs (titles, abstracts) is untrusted data. The skills tell the model to treat it as content to report, not as instructions.
- Runtime dependencies are pinned exactly (`server/pyproject.toml`, `server/uv.lock`).
