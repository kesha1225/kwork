import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import aiohttp
import pytest

from kwork.api import (
    KworkAPI,
    _format_exception_short,
    _is_sensitive_key,
    _redact_sensitive,
)


def test_is_sensitive_key_detects_common_secret_fields() -> None:
    assert _is_sensitive_key("password")
    assert _is_sensitive_key("new_password")
    assert _is_sensitive_key("access_token")
    assert _is_sensitive_key("Authorization")
    assert _is_sensitive_key("phone_last")
    assert _is_sensitive_key("phoneLast")

    assert not _is_sensitive_key("username")
    assert not _is_sensitive_key(123)


def test_redact_sensitive_redacts_nested_structures() -> None:
    data = {
        "password": "secret",
        "nested": {
            "token": "abc",
            "ok": 1,
            "items": [
                {"authorization": "Bearer x"},
                ("keep", {"phone_last": "0000"}),
            ],
        },
    }

    redacted = _redact_sensitive(data)

    assert redacted["password"] == "<redacted>"
    assert redacted["nested"]["token"] == "<redacted>"
    assert redacted["nested"]["ok"] == 1
    assert redacted["nested"]["items"][0]["authorization"] == "<redacted>"
    assert redacted["nested"]["items"][1][0] == "keep"
    assert redacted["nested"]["items"][1][1]["phone_last"] == "<redacted>"


def test_format_exception_short_is_informative_for_timeout_error() -> None:
    err = asyncio.TimeoutError()
    s = _format_exception_short(err)
    assert "TimeoutError" in s
    assert s.strip() != "TimeoutError:"


def test_truncate_keeps_short_strings() -> None:
    api = KworkAPI(login="x", password="y")
    assert api._truncate("hi", limit=10) == "hi"


def test_truncate_adds_suffix_when_long() -> None:
    api = KworkAPI(login="x", password="y")
    out = api._truncate("a" * 20, limit=5)
    assert out.startswith("a" * 5)
    assert out.endswith("...<truncated>")


def test_normalize_timeout_accepts_float_and_none() -> None:
    assert KworkAPI._normalize_timeout(None) is None
    t = KworkAPI._normalize_timeout(1.25)
    assert isinstance(t, aiohttp.ClientTimeout)
    assert t.total == 1.25


def test_compute_backoff_respects_max_and_no_jitter(monkeypatch: pytest.MonkeyPatch) -> None:
    api = KworkAPI(
        login="x",
        password="y",
        retry_backoff_base=1.0,
        retry_backoff_max=3.0,
        retry_jitter=0.0,
    )
    # No jitter: deterministic.
    assert api._compute_backoff(1) == 1.0
    assert api._compute_backoff(2) == 2.0
    assert api._compute_backoff(3) == 3.0
    assert api._compute_backoff(4) == 3.0


def test_parse_retry_after_seconds_numeric() -> None:
    class _Resp:
        headers = {"Retry-After": "2.5"}

    assert KworkAPI._parse_retry_after_seconds(_Resp()) == 2.5  # type: ignore[arg-type]


def test_parse_retry_after_seconds_http_date_future_is_positive() -> None:
    class _Resp:
        headers: dict[str, str]

        def __init__(self, value: str) -> None:
            self.headers = {"Retry-After": value}

    value = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=5), usegmt=True)
    out = KworkAPI._parse_retry_after_seconds(_Resp(value))  # type: ignore[arg-type]
    assert out is not None
    # Allow some scheduling / runtime skew.
    assert 0.0 < out <= 6.0


def test_parse_retry_after_seconds_http_date_past_is_zero() -> None:
    class _Resp:
        headers: dict[str, str]

        def __init__(self, value: str) -> None:
            self.headers = {"Retry-After": value}

    value = format_datetime(datetime(2000, 1, 1, tzinfo=timezone.utc), usegmt=True)
    assert KworkAPI._parse_retry_after_seconds(_Resp(value)) == 0.0  # type: ignore[arg-type]
