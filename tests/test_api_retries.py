import asyncio
import json
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from kwork.api import KworkAPI
from kwork.exceptions import KworkHTTPException, KworkRetryExceeded


class _FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        content_type: str = "application/json",
        headers: dict[str, str] | None = None,
        body: str | None = None,
    ) -> None:
        self.status = status
        self.content_type = content_type
        self.headers = headers or {}
        self._body = body if body is not None else json.dumps({"success": True, "response": {}})

    async def text(self, *, errors: str | None = None) -> str:  # noqa: ARG002
        return self._body


class _FakeRequestCtx:
    def __init__(self, outcome: _FakeResponse | BaseException) -> None:
        self._outcome = outcome

    async def __aenter__(self) -> _FakeResponse:
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False


class _FakeSession:
    def __init__(self, outcomes: list[_FakeResponse | BaseException]) -> None:
        self.closed = False
        self._outcomes = outcomes
        self.calls: int = 0

    def request(self, **kwargs):  # noqa: ANN001
        self.calls += 1
        if not self._outcomes:
            raise AssertionError(f"Unexpected request call. kwargs={kwargs!r}")
        return _FakeRequestCtx(self._outcomes.pop(0))

    def post(self, **kwargs):  # noqa: ANN001
        return self.request(**kwargs)


def test_non_2xx_raises_http_exception_with_body() -> None:
    async def _run() -> None:
        api = KworkAPI(login="x", password="y", retry_max_attempts=1)
        api._session = _FakeSession(  # type: ignore[assignment]
            [
                _FakeResponse(
                    status=500,
                    body="oops",
                    content_type="text/plain",
                )
            ]
        )

        with pytest.raises(KworkHTTPException) as ctx:
            await api.request("get", "ping", retry=False)

        assert ctx.value.status == 500
        assert ctx.value.endpoint == "ping"
        assert "oops" in str(ctx.value)

    asyncio.run(_run())


def test_retries_on_5xx_then_succeeds() -> None:
    async def _run() -> None:
        api = KworkAPI(
            login="x",
            password="y",
            retry_max_attempts=3,
            retry_backoff_base=0.0,
            retry_jitter=0.0,
        )
        api._session = _FakeSession(  # type: ignore[assignment]
            [
                _FakeResponse(status=500, body="fail", content_type="text/plain"),
                _FakeResponse(status=502, body="fail2", content_type="text/plain"),
                _FakeResponse(
                    status=200, body=json.dumps({"success": True, "response": {"ok": 1}})
                ),
            ]
        )

        data = await api.request("post", "actor")
        assert data["response"]["ok"] == 1
        assert api.session.calls == 3  # type: ignore[union-attr]

    asyncio.run(_run())


def test_retries_on_429_uses_retry_after() -> None:
    async def _run() -> None:
        api = KworkAPI(
            login="x",
            password="y",
            retry_max_attempts=2,
            retry_backoff_base=0.0,
            retry_backoff_max=10.0,
            retry_jitter=0.0,
        )
        api._session = _FakeSession(  # type: ignore[assignment]
            [
                _FakeResponse(
                    status=429,
                    headers={"Retry-After": "1"},
                    body=json.dumps({"error": "rate limit"}),
                    content_type="application/json",
                ),
                _FakeResponse(
                    status=200, body=json.dumps({"success": True, "response": {"ok": 1}})
                ),
            ]
        )

        with patch.object(asyncio, "sleep", new=AsyncMock()) as sleep:
            data = await api.request("post", "actor")
            assert data["response"]["ok"] == 1
            sleep.assert_awaited()
            # Should sleep at least Retry-After seconds (1.0 here).
            assert float(sleep.await_args.args[0]) >= 1.0

    asyncio.run(_run())


def test_network_errors_raise_retry_exceeded() -> None:
    async def _run() -> None:
        api = KworkAPI(
            login="x",
            password="y",
            retry_max_attempts=2,
            retry_backoff_base=0.0,
            retry_jitter=0.0,
        )
        api._session = _FakeSession(  # type: ignore[assignment]
            [
                asyncio.TimeoutError(),
                aiohttp.ClientConnectionError("nope"),
            ]
        )

        with pytest.raises(KworkRetryExceeded) as ctx:
            await api.request("get", "ping")

        assert ctx.value.attempts == 2
        assert ctx.value.last_error is not None
        # Error message should contain the final exception type even if its str() is empty.
        assert "ClientConnectionError" in str(ctx.value)

    asyncio.run(_run())


def test_timeout_error_message_is_informative() -> None:
    async def _run() -> None:
        api = KworkAPI(
            login="x",
            password="y",
            retry_max_attempts=1,
        )
        api._session = _FakeSession(  # type: ignore[assignment]
            [
                asyncio.TimeoutError(),
            ]
        )

        with pytest.raises(KworkRetryExceeded) as ctx:
            await api.request("get", "ping", retry=False)

        assert "TimeoutError" in str(ctx.value)

    asyncio.run(_run())
