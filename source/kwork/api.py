import logging
import mimetypes
import asyncio
import json
import random
from contextlib import ExitStack
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import aiohttp
from aiohttp import ClientResponse

from kwork.exceptions import KworkException, KworkHTTPException, KworkRetryExceeded

logger: logging.Logger = logging.getLogger(__name__)

AUTH_HEADER = "Basic bW9iaWxlX2FwaTpxRnZmUmw3dw=="
API_HOST = "https://api.kwork.ru/{}"

_REDACTED = "<redacted>"
_DEFAULT_RETRY_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


def _is_sensitive_key(key: str | Any) -> bool:
    if not isinstance(key, str):
        return False

    k = key.lower()
    if k in {"phone_last", "phonelast"}:
        return True

    # Be defensive: API methods may use variations like old_password/new_password or access_token.
    return any(part in k for part in ("password", "token", "authorization"))


def _redact_sensitive(value: str | Any, *, _depth: int = 0) -> Any:
    # Avoid pathological recursion / self-referential structures.
    if _depth >= 20:
        return "<max_depth>"

    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for k, v in value.items():
            if _is_sensitive_key(k):
                redacted[k] = _REDACTED
            else:
                redacted[k] = _redact_sensitive(v, _depth=_depth + 1)
        return redacted

    if isinstance(value, list):
        return [_redact_sensitive(v, _depth=_depth + 1) for v in value]

    if isinstance(value, tuple):
        return tuple(_redact_sensitive(v, _depth=_depth + 1) for v in value)

    return value


def _format_exception_short(err: BaseException) -> str:
    """
    Return a non-empty, low-noise description of an exception.

    Some exceptions (notably asyncio.TimeoutError) have an empty str(), which leads to
    confusing logs like "...: " with no details.
    """
    s = str(err).strip()
    if s:
        return f"{type(err).__name__}: {s}"
    # repr() is almost always informative and non-empty (e.g. TimeoutError()).
    return f"{type(err).__name__} ({err!r})"


class KworkAPI:
    def __init__(
        self,
        login: str,
        password: str,
        proxy: str | None = None,
        phone_last: str | None = None,
        api_host: str = API_HOST,
        *,
        timeout: aiohttp.ClientTimeout | float | None = 30.0,
        retry_max_attempts: int = 1,
        retry_backoff_base: float = 0.5,
        retry_backoff_max: float = 8.0,
        retry_jitter: float = 0.1,
        retry_statuses: set[int] | frozenset[int] | None = None,
        relogin_on_auth_error: bool = False,
    ) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._proxy = proxy
        self._api_host = api_host
        self._login = login
        self._password = password
        self._phone_last = phone_last
        self._token: str | None = None
        self._timeout = self._normalize_timeout(timeout)

        if retry_max_attempts < 1:
            raise ValueError("retry_max_attempts must be >= 1")
        if retry_backoff_base < 0:
            raise ValueError("retry_backoff_base must be >= 0")
        if retry_backoff_max < 0:
            raise ValueError("retry_backoff_max must be >= 0")
        if retry_jitter < 0:
            raise ValueError("retry_jitter must be >= 0")

        self._retry_max_attempts = retry_max_attempts
        self._retry_backoff_base = retry_backoff_base
        self._retry_backoff_max = retry_backoff_max
        self._retry_jitter = retry_jitter
        self._retry_statuses: frozenset[int] = (
            frozenset(retry_statuses) if retry_statuses is not None else _DEFAULT_RETRY_STATUSES
        )
        self._relogin_on_auth_error = relogin_on_auth_error

    @staticmethod
    def _normalize_timeout(
        timeout: aiohttp.ClientTimeout | float | None,
    ) -> aiohttp.ClientTimeout | None:
        if timeout is None:
            return None
        if isinstance(timeout, aiohttp.ClientTimeout):
            return timeout
        return aiohttp.ClientTimeout(total=float(timeout))

    @staticmethod
    def _create_connector(proxy: str | None) -> aiohttp.BaseConnector | None:
        if proxy is None:
            return None

        try:
            from aiohttp_socks import ProxyConnector  # pyright: ignore[reportMissingImports]
        except ImportError as err:
            msg = (
                "Proxy support requires optional dependency aiohttp-socks. "
                'Install with: pip install "kwork[proxy]" (recommended) '
                "or pip install aiohttp-socks"
            )
            raise ImportError(msg) from err

        return ProxyConnector.from_url(proxy)

    def _create_session(self) -> aiohttp.ClientSession:
        connector = self._create_connector(self._proxy)
        # When we pass our own connector we want the session to own and close it.
        # This prevents a closed connector instance being accidentally reused after session.close().
        if connector is None:
            return aiohttp.ClientSession(timeout=self._timeout)
        return aiohttp.ClientSession(
            connector=connector,
            connector_owner=True,
            timeout=self._timeout,
        )

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = self._create_session()
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def get_token(self) -> str:
        if self._token is not None:
            return self._token

        body: dict[str, str] = {
            "login": self._login,
            "password": self._password,
        }
        if self._phone_last is not None:
            body["phone_last"] = self._phone_last

        response = await self.request_with_body("signIn", body=body)
        token: str = response["response"]["token"]
        self._token = token
        return token

    async def request(
        self,
        method: str,
        endpoint: str,
        use_token: bool = False,
        _headers: dict[str, str] | None = None,
        _cookies: dict[str, str] | None = None,
        *,
        retry: bool | None = None,
        timeout: aiohttp.ClientTimeout | float | None = None,
        max_attempts: int | None = None,
        **params: Any,
    ) -> dict[str, Any]:
        filtered = {k: v for k, v in params.items() if v is not None}

        if use_token:
            filtered["token"] = await self.get_token()

        headers = {"Authorization": AUTH_HEADER}
        if _headers:
            headers.update(_headers)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Request %s /%s params=%s headers=%s cookies=%s",
                method.upper(),
                endpoint,
                _redact_sensitive(filtered),
                list((_headers or {}).keys()),
                list((_cookies or {}).keys()),
            )

        return await self._request_json(
            method=method,
            endpoint=endpoint,
            headers=headers,
            params=filtered,
            data=None,
            cookies=_cookies,
            retry=retry,
            timeout=timeout,
            max_attempts=max_attempts,
            use_token=use_token,
        )

    async def _read_response_body(self, resp: ClientResponse) -> tuple[str, dict[str, Any] | None]:
        # Read the full body as text so we can include it in exceptions.
        text = await resp.text(errors="replace")
        if resp.content_type != "application/json":
            return text, None
        try:
            parsed: Any = json.loads(text)
        except json.JSONDecodeError:
            return text, None
        return text, parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _truncate(text: str, *, limit: int = 2048) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "...<truncated>"

    def _should_retry_status(self, status: int) -> bool:
        return status in self._retry_statuses

    def _compute_backoff(self, retry_n: int) -> float:
        # retry_n starts at 1 for the first retry after the first failure.
        delay = self._retry_backoff_base * (2 ** (retry_n - 1))
        delay = min(delay, self._retry_backoff_max)
        if delay <= 0:
            return 0.0
        if self._retry_jitter <= 0:
            return delay
        return delay + random.uniform(0.0, delay * self._retry_jitter)

    @staticmethod
    def _parse_retry_after_seconds(resp: ClientResponse) -> float | None:
        value = resp.headers.get("Retry-After")
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            pass
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(0.0, (dt - now).total_seconds())

    async def _handle_json_payload(
        self,
        resp: ClientResponse,
        endpoint: str,
        *,
        method: str,
        request_params: dict[str, Any] | None,
        request_body: Any | None,
    ) -> dict[str, Any]:
        body_text, data = await self._read_response_body(resp)

        if resp.status < 200 or resp.status >= 300:
            msg = (
                f"HTTP {resp.status} for {method.upper()} /{endpoint}: {self._truncate(body_text)}"
            )
            raise KworkHTTPException(
                msg,
                status=resp.status,
                method=method.upper(),
                endpoint=endpoint,
                response_text=body_text,
                response_json=data,
                request_params=_redact_sensitive(request_params) if request_params else None,
                request_body=_redact_sensitive(request_body)
                if isinstance(request_body, dict)
                else None,
            )

        if data is None:
            raise KworkHTTPException(
                f"Non-JSON response from /{endpoint}: {self._truncate(body_text)}",
                status=resp.status,
                method=method.upper(),
                endpoint=endpoint,
                response_text=body_text,
                request_params=_redact_sensitive(request_params) if request_params else None,
            )

        if not data.get("success"):
            # This is an API-level error (often still HTTP 200).
            raise KworkException(data.get("error", "Unknown API error"))

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Response /%s: %s", endpoint, _redact_sensitive(data))
        return data

    async def _request_json(
        self,
        *,
        method: str,
        endpoint: str,
        headers: dict[str, str],
        params: dict[str, Any] | None,
        data: Any,
        cookies: dict[str, str] | None,
        retry: bool | None,
        timeout: aiohttp.ClientTimeout | float | None,
        max_attempts: int | None,
        use_token: bool,
    ) -> dict[str, Any]:
        effective_timeout = self._normalize_timeout(timeout) if timeout is not None else None
        attempts_limit = max_attempts if max_attempts is not None else self._retry_max_attempts
        if attempts_limit < 1:
            raise ValueError("max_attempts must be >= 1")

        enable_retry = retry if retry is not None else attempts_limit > 1
        attempts = 0
        auth_reset_done = False

        while True:
            attempts += 1
            try:
                req_kwargs: dict[str, Any] = {
                    "method": method,
                    "url": self._api_host.format(endpoint),
                    "headers": headers,
                    "params": params,
                    "data": data,
                    "cookies": cookies,
                }
                if effective_timeout is not None:
                    req_kwargs["timeout"] = effective_timeout

                async with self.session.request(**req_kwargs) as resp:
                    if (
                        resp.status in {401, 403}
                        and use_token
                        and self._relogin_on_auth_error
                        and not auth_reset_done
                        and enable_retry
                        and attempts < attempts_limit
                    ):
                        auth_reset_done = True
                        self._token = None
                        body_text, _ = await self._read_response_body(resp)
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(
                                "Auth error HTTP %s for /%s, resetting token and retrying. body=%s",
                                resp.status,
                                endpoint,
                                self._truncate(body_text),
                            )
                        delay = self._compute_backoff(attempts)
                        if delay > 0:
                            await asyncio.sleep(delay)
                        continue

                    try:
                        return await self._handle_json_payload(
                            resp,
                            endpoint,
                            method=method,
                            request_params=params,
                            request_body=data,
                        )
                    except KworkHTTPException as e:
                        if (
                            enable_retry
                            and e.status is not None
                            and self._should_retry_status(e.status)
                            and attempts < attempts_limit
                        ):
                            retry_after = (
                                self._parse_retry_after_seconds(resp) if e.status == 429 else None
                            )
                            delay = self._compute_backoff(attempts)
                            if retry_after is not None:
                                delay = min(max(delay, retry_after), self._retry_backoff_max)
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug(
                                    "Retrying %s /%s after HTTP %s (attempt %s/%s, sleep %.2fs)",
                                    method.upper(),
                                    endpoint,
                                    e.status,
                                    attempts + 1,
                                    attempts_limit,
                                    delay,
                                )
                            if delay > 0:
                                await asyncio.sleep(delay)
                            continue
                        raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if not enable_retry or attempts >= attempts_limit:
                    err_desc = _format_exception_short(e)
                    raise KworkRetryExceeded(
                        f"Request {method.upper()} /{endpoint} failed after {attempts} attempts: {err_desc}",
                        attempts=attempts,
                        last_error=e,
                    ) from e

                delay = self._compute_backoff(attempts)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "Retrying %s /%s after network error %s (attempt %s/%s, sleep %.2fs)",
                        method.upper(),
                        endpoint,
                        type(e).__name__,
                        attempts + 1,
                        attempts_limit,
                        delay,
                    )
                if delay > 0:
                    await asyncio.sleep(delay)
                continue

    async def request_with_body(
        self,
        endpoint: str,
        use_token: bool = False,
        _headers: dict[str, str] | None = None,
        _cookies: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        *,
        retry: bool | None = None,
        timeout: aiohttp.ClientTimeout | float | None = None,
        max_attempts: int | None = None,
        **params: Any,
    ) -> dict[str, Any]:
        filtered_params = {k: v for k, v in params.items() if v is not None}

        if use_token:
            filtered_params["token"] = await self.get_token()

        headers = {"Authorization": AUTH_HEADER}
        if _headers:
            headers.update(_headers)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Request POST /%s params=%s body=%s",
                endpoint,
                _redact_sensitive(filtered_params),
                _redact_sensitive(body),
            )

        return await self._request_json(
            method="post",
            endpoint=endpoint,
            headers=headers,
            params=filtered_params,
            data=body,
            cookies=_cookies,
            retry=retry,
            timeout=timeout,
            max_attempts=max_attempts,
            use_token=use_token,
        )

    async def request_multipart(
        self,
        endpoint: str,
        use_token: bool = False,
        _headers: dict[str, str] | None = None,
        _cookies: dict[str, str] | None = None,
        fields: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        *,
        # Retries for multipart are risky (possible duplicate uploads / non-idempotent side effects).
        # Default here is conservative: no retries unless the caller explicitly opts in.
        retry: bool | None = None,
        timeout: aiohttp.ClientTimeout | float | None = None,
        max_attempts: int | None = None,
        **params: Any,
    ) -> dict[str, Any]:
        """
        POST multipart/form-data request.

        `fields` - regular form fields.
        `files` - mapping of field name to:
          - path-like (`str`/`Path`)
          - `bytes`
          - file-like object opened in binary mode
          - tuple `(filename, data_or_fileobj[, content_type])`
        """
        filtered_params = {k: v for k, v in params.items() if v is not None}

        if use_token:
            filtered_params["token"] = await self.get_token()

        headers = {"Authorization": AUTH_HEADER}
        if _headers:
            headers.update(_headers)

        effective_timeout = self._normalize_timeout(timeout) if timeout is not None else None
        attempts_limit = max_attempts if max_attempts is not None else 1
        if attempts_limit < 1:
            raise ValueError("max_attempts must be >= 1")
        enable_retry = retry if retry is not None else attempts_limit > 1

        attempts = 0
        while True:
            attempts += 1

            form = aiohttp.FormData()
            if fields:
                for k, v in fields.items():
                    if v is None:
                        continue
                    if isinstance(v, bool):
                        v = int(v)
                    form.add_field(k, v)

            stack = ExitStack()
            try:
                if files:
                    for field, spec in files.items():
                        if spec is None:
                            continue

                        filename = None
                        content_type = None
                        value = spec

                        if isinstance(spec, tuple) and 2 <= len(spec) <= 3:
                            filename = spec[0]
                            value = spec[1]
                            content_type = spec[2] if len(spec) == 3 else None
                        elif isinstance(spec, (str, Path)):
                            path = Path(spec)
                            filename = path.name
                            content_type = (
                                mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                            )
                            value = stack.enter_context(path.open("rb"))
                        elif isinstance(spec, bytes):
                            filename = field
                            content_type = "application/octet-stream"
                            value = spec
                        else:
                            # File-like objects are not safe to retry because they may have been consumed.
                            if enable_retry and attempts_limit > 1:
                                raise ValueError(
                                    "Retry for multipart requests requires file specs as paths/bytes/tuples, "
                                    "not file-like objects."
                                )
                            filename = getattr(spec, "name", field)
                            content_type = "application/octet-stream"
                            value = spec

                        kwargs: dict[str, Any] = {}
                        if filename is not None:
                            kwargs["filename"] = filename
                        if content_type is not None:
                            kwargs["content_type"] = content_type

                        form.add_field(field, value, **kwargs)

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "Request POST(multipart) /%s params=%s fields=%s files=%s headers=%s cookies=%s",
                        endpoint,
                        _redact_sensitive(filtered_params),
                        list((fields or {}).keys()),
                        list((files or {}).keys()),
                        list((_headers or {}).keys()),
                        list((_cookies or {}).keys()),
                    )

                async with self.session.post(
                    url=self._api_host.format(endpoint),
                    headers=headers,
                    params=filtered_params,
                    data=form,
                    cookies=_cookies,
                    **({"timeout": effective_timeout} if effective_timeout is not None else {}),
                ) as resp:
                    try:
                        return await self._handle_json_payload(
                            resp,
                            endpoint,
                            method="post",
                            request_params=filtered_params,
                            request_body=None,
                        )
                    except KworkHTTPException as e:
                        if (
                            enable_retry
                            and e.status is not None
                            and self._should_retry_status(e.status)
                            and attempts < attempts_limit
                        ):
                            retry_after = (
                                self._parse_retry_after_seconds(resp) if e.status == 429 else None
                            )
                            delay = self._compute_backoff(attempts)
                            if retry_after is not None:
                                delay = min(max(delay, retry_after), self._retry_backoff_max)
                            if delay > 0:
                                await asyncio.sleep(delay)
                            continue
                        raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if not enable_retry or attempts >= attempts_limit:
                    raise KworkRetryExceeded(
                        f"Request POST /{endpoint} failed after {attempts} attempts: {_format_exception_short(e)}",
                        attempts=attempts,
                        last_error=e,
                    ) from e
                delay = self._compute_backoff(attempts)
                if delay > 0:
                    await asyncio.sleep(delay)
                continue
            finally:
                stack.close()
