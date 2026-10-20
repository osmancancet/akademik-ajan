"""Minimal JSON-over-HTTPS client built on the standard library.

Kept dependency-free on purpose: fewer packages means a smaller supply-chain
surface. Every request carries a descriptive User-Agent, and a contact
address when AKADEMIK_AJAN_MAILTO is set (Crossref's "polite pool").
OpenAlex requests carry OPENALEX_API_KEY as a bearer token when it is set;
without a key OpenAlex shares a small daily budget per IP address.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from . import __version__

# A fetcher takes a full URL and returns (status_code, parsed_json_or_None).
Fetcher = Callable[[str], "tuple[int, Any]"]

TIMEOUT_SECONDS = 15
RETRIES = 3
MAX_BACKOFF_SECONDS = 20.0


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


def _retry_delay(exc: urllib.error.HTTPError, attempt: int) -> float:
    header = exc.headers.get("Retry-After") if exc.headers else None
    try:
        return min(float(header), MAX_BACKOFF_SECONDS) if header else 2.0 * (attempt + 1)
    except ValueError:
        return 2.0 * (attempt + 1)


def fetch_json(url: str) -> tuple[int, Any]:
    """GET a URL and return (status, json). Non-JSON or error bodies give None.

    429 and 503 responses are retried (honouring Retry-After); if the service is
    still refusing afterwards a ConnectionError is raised, so rate limiting is
    reported as an error rather than as "not found".
    """
    headers = {"User-Agent": _user_agent(), "Accept": "application/json"}
    openalex_key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if openalex_key and urllib.parse.urlsplit(url).hostname == "api.openalex.org":
        headers["Authorization"] = f"Bearer {openalex_key}"  # header, never the URL
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                body = resp.read()
                status = resp.status
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 503):
                return exc.code, None
            body = exc.read(2048).decode("utf-8", "replace") if exc.fp else ""
            if "budget" in body.lower():  # OpenAlex daily quota: retrying cannot help
                raise ConnectionError(f"Daily quota exhausted for {url}") from exc
            if attempt == RETRIES:
                raise ConnectionError(f"Service busy ({exc.code}) for {url}") from exc
            time.sleep(_retry_delay(exc, attempt))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ConnectionError(f"Network error for {url}: {exc}") from exc
    try:
        return status, json.loads(body)
    except ValueError:
        return status, None
