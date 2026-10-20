"""Render a response-to-reviewers letter and a change log from structured points.

The model drafts the content; this module only checks completeness and lays it out
the same way every time, in Markdown or LaTeX. Input shape:

{
  "title": "Manuscript title",
  "manuscript_id": "COSE-D-26-01234",          (optional)
  "round": 1,                                   (optional)
  "opening": "We thank the editor ...",         (optional)
  "reviewers": [
    {"name": "Reviewer 1",
     "points": [
       {"id": "R1.1", "comment": "verbatim reviewer text",
        "response": "our reply", "changes": "what changed (optional)",
        "location": "Section 3.2, p. 7 (optional)",
        "status": "addressed | partially_addressed | not_addressed | author_action"}
     ]}
  ]
}

`author_action` marks a point whose reply needs something only the authors can supply
(a new experiment, data, a decision); such points are listed, never silently filled.
"""

from __future__ import annotations

import re
from typing import Any

STATUSES = ("addressed", "partially_addressed", "not_addressed", "author_action")
_PLACEHOLDER = re.compile(r"\[(TODO|TBD|XX+|\.\.\.)\]|\bTODO\b", re.IGNORECASE)
_TEX = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
        "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def check(data: dict[str, Any]) -> dict[str, Any]:
    """Return problems that block a finished letter, without changing anything."""
    problems: list[str] = []
    author_action: list[str] = []
    seen: set[str] = set()
    counts = {s: 0 for s in STATUSES}
    reviewers = data.get("reviewers") or []
    if not data.get("title"):
        problems.append("missing manuscript title")
    if not reviewers:
        problems.append("no reviewers given")
    for r_i, rev in enumerate(reviewers, 1):
        name = rev.get("name") or f"Reviewer {r_i}"
        points = rev.get("points") or []
        if not points:
            problems.append(f"{name}: no points")
        for p_i, p in enumerate(points, 1):
            pid = p.get("id") or f"R{r_i}.{p_i}"
            if pid in seen:
                problems.append(f"{pid}: duplicate id")
            seen.add(pid)
            status = p.get("status", "addressed")
            if status not in STATUSES:
                problems.append(f"{pid}: unknown status {status!r}")
                continue
            counts[status] += 1
            if not (p.get("comment") or "").strip():
                problems.append(f"{pid}: reviewer comment is empty")
            response = (p.get("response") or "").strip()
            if status == "author_action":
                author_action.append(pid)
            elif not response:
                problems.append(f"{pid}: response is empty")
            if _PLACEHOLDER.search(response) or _PLACEHOLDER.search(p.get("changes") or ""):
                problems.append(f"{pid}: response or changes contain a placeholder")
    return {"ready": not problems and not author_action, "problems": problems,
            "author_action": author_action, "counts": counts, "points": len(seen)}


def _ids(data: dict[str, Any]):
    for r_i, rev in enumerate(data.get("reviewers") or [], 1):
        name = rev.get("name") or f"Reviewer {r_i}"
        for p_i, p in enumerate(rev.get("points") or [], 1):
            yield name, p.get("id") or f"R{r_i}.{p_i}", p


def _md_quote(text: str) -> str:
    return "\n".join("> " + line if line.strip() else ">" for line in text.strip().splitlines())


def render_markdown(data: dict[str, Any]) -> str:
    out: list[str] = []
    head = f"# Response to reviewers: {data.get('title', '')}".rstrip()
    out.append(head)
    meta = [x for x in (data.get("manuscript_id"),
                        f"Revision round {data['round']}" if data.get("round") else None) if x]
    if meta:
        out.append("")
        out.append(" · ".join(meta))
    if data.get("opening"):
        out += ["", data["opening"].strip()]
    current = None
    for name, pid, p in _ids(data):
        if name != current:
            out += ["", f"## {name}"]
            current = name
        out += ["", f"### {pid}", "", "**Comment.**", "", _md_quote(p.get("comment") or "")]
        if p.get("status") == "author_action":
            out += ["", "**Response.** _Pending author input._"]
            if p.get("response"):
                out += ["", p["response"].strip()]
        else:
            out += ["", f"**Response.** {(p.get('response') or '').strip()}"]
        if p.get("changes"):
            loc = f" ({p['location']})" if p.get("location") else ""
            out += ["", f"**Changes{loc}.** {p['changes'].strip()}"]
    return "\n".join(out).rstrip() + "\n"


def _tex(text: str) -> str:
    return "".join(_TEX.get(c, c) for c in text.strip())


def render_latex(data: dict[str, Any]) -> str:
    out = [r"\section*{Response to reviewers: " + _tex(data.get("title", "")) + "}"]
    meta = [x for x in (data.get("manuscript_id"),
                        f"Revision round {data['round']}" if data.get("round") else None) if x]
    if meta:
        out.append(_tex(" · ".join(meta)) + r"\par")
    if data.get("opening"):
        out.append(_tex(data["opening"]) + r"\par")
    current = None
    for name, pid, p in _ids(data):
        if name != current:
            out.append(r"\subsection*{" + _tex(name) + "}")
            current = name
        out.append(r"\paragraph{" + _tex(pid) + "}")
        out.append(r"\begin{quote}\itshape " + _tex(p.get("comment") or "") + r"\end{quote}")
        if p.get("status") == "author_action":
            out.append(r"\textbf{Response.} \emph{Pending author input.}"
                       + ((" " + _tex(p["response"])) if p.get("response") else "") + r"\par")
        else:
            out.append(r"\textbf{Response.} " + _tex(p.get("response") or "") + r"\par")
        if p.get("changes"):
            loc = f" ({_tex(p['location'])})" if p.get("location") else ""
            out.append(r"\textbf{Changes" + loc + r".} " + _tex(p["changes"]) + r"\par")
    return "\n".join(out) + "\n"


def change_log(data: dict[str, Any], width: int = 90) -> str:
    """Markdown table: one row per point, for the authors' own tracking."""
    rows = ["| # | Comment | Resolution | Location | Outcome |", "|---|---|---|---|---|"]

    def cell(text: str | None) -> str:
        text = re.sub(r"\s+", " ", (text or "").strip()).replace("|", r"\|")
        return text if len(text) <= width else text[: width - 1] + "…"

    for _, pid, p in _ids(data):
        rows.append(f"| {pid} | {cell(p.get('comment'))} | {cell(p.get('changes') or p.get('response'))} "
                    f"| {cell(p.get('location'))} | {p.get('status', 'addressed')} |")
    return "\n".join(rows) + "\n"


def render_response_letter(data: dict[str, Any], fmt: str = "markdown") -> dict[str, Any]:
    if fmt not in ("markdown", "latex"):
        raise ValueError("fmt must be 'markdown' or 'latex'")
    letter = render_markdown(data) if fmt == "markdown" else render_latex(data)
    return {"letter": letter, "change_log": change_log(data), "check": check(data)}
