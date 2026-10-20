import io
import urllib.error

import pytest

from akademik_ajan import http


class _Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _busy(url, code=429):
    return urllib.error.HTTPError(url, code, "busy", {"Retry-After": "0"}, None)


def test_retries_on_429_then_succeeds(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        if len(calls) < 3:
            raise _busy(req.full_url)
        return _Resp(b'{"ok": true}')

    monkeypatch.setattr(http.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    assert http.fetch_json("https://example.org/x") == (200, {"ok": True})
    assert len(calls) == 3


def test_persistent_429_is_an_error_not_a_miss(monkeypatch):
    def fake_urlopen(req, timeout):
        raise _busy(req.full_url, 503)

    monkeypatch.setattr(http.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    with pytest.raises(ConnectionError):
        http.fetch_json("https://example.org/x")


def test_exhausted_daily_budget_fails_fast(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(1)
        raise urllib.error.HTTPError(req.full_url, 429, "busy", {"Retry-After": "6"},
                                     io.BytesIO(b'{"message": "Insufficient budget."}'))

    monkeypatch.setattr(http.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ConnectionError, match="quota"):
        http.fetch_json("https://api.openalex.org/works?search=x")
    assert len(calls) == 1


def test_openalex_key_sent_as_header_only_to_openalex(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen[req.host] = req.get_header("Authorization")
        return _Resp(b"{}")

    monkeypatch.setenv("OPENALEX_API_KEY", "k123")
    monkeypatch.setattr(http.urllib.request, "urlopen", fake_urlopen)
    http.fetch_json("https://api.openalex.org/works/x")
    http.fetch_json("https://api.crossref.org/works/x")
    assert seen == {"api.openalex.org": "Bearer k123", "api.crossref.org": None}


def test_404_is_returned_without_retry(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(1)
        raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)

    monkeypatch.setattr(http.urllib.request, "urlopen", fake_urlopen)
    assert http.fetch_json("https://example.org/x") == (404, None)
    assert len(calls) == 1


def test_mailto_is_opt_in(monkeypatch):
    monkeypatch.delenv("AKADEMIK_AJAN_MAILTO", raising=False)
    assert "mailto" not in http._user_agent()
    monkeypatch.setenv("AKADEMIK_AJAN_MAILTO", "me@uni.edu.tr")
    assert http._user_agent().endswith("mailto:me@uni.edu.tr")
