"""Minimal JSON-over-HTTPS client built on the standard library.

Kept dependency-free on purpose: fewer packages means a smaller supply-chain
surface. Every request carries a descriptive User-Agent, and a contact
address when AKADEMIK_AJAN_MAILTO is set (Crossref's "polite pool").
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from . import __version__

# A fetcher takes a full URL and returns (status_code, parsed_json_or_None).
Fetcher = Callable[[str], "tuple[int, Any]"]

TIMEOUT_SECONDS = 15


def _user_agent() -> str:
    ua = f"akademik-ajan/{__version__} (+https://github.com/osmancancet/akademik-ajan)"
    mailto = os.environ.get("AKADEMIK_AJAN_MAILTO", "").strip()
    if mailto:
        ua += f" mailto:{mailto}"
    return ua


def build_url(base: str, params: dict[str, Any] | None = None) -> str:
    if not params:
        return base
    clean = {k: v for k, v in params.items() if v is not None and v != ""}
    return f"{base}?{urllib.parse.urlencode(clean)}"


def fetch_json(url: str) -> tuple[int, Any]:
    """GET a URL and return (status, json). Non-JSON or error bodies give None."""
    req = urllib.request.Request(
        url, headers={"User-Agent": _user_agent(), "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ConnectionError(f"Network error for {url}: {exc}") from exc
    try:
        return status, json.loads(body)
    except ValueError:
        return status, None
