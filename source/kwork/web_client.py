from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp

from kwork.api import KworkAPI

logger = logging.getLogger(__name__)


DEFAULT_WEB_BASE_URL = "https://kwork.ru/"


@dataclass(frozen=True, slots=True)
class WebLoginResult:
    token: str | None
    expires_at: int | None
    login_url: str
    url_to_redirect: str | None
    final_url: str | None
    status: int | None


class KworkWebClient:
    """
    Minimal web client that reuses the authenticated mobile API session.

    How the official app works (per decompiled sources):
    1) Call mobile API: POST /getWebAuthToken (api.kwork.ru) to get a one-time web login URL.
    2) Open that URL in WebView (kwork.ru/login-by-token?...), which sets web cookies.

    This class implements the same flow using aiohttp.
    """

    def __init__(self, api: KworkAPI, *, base_url: str = DEFAULT_WEB_BASE_URL) -> None:
        self._api = api
        self._base_url = (base_url.rstrip("/") + "/") if base_url else DEFAULT_WEB_BASE_URL

    @property
    def base_url(self) -> str:
        return self._base_url

    async def login_via_mobile_web_auth_token(
        self,
        *,
        url_to_redirect: str | None = "/",
        user_agent: str | None = None,
        allow_redirects: bool = True,
        max_redirects: int = 10,
        timeout: aiohttp.ClientTimeout | float | None = None,
    ) -> WebLoginResult:
        """
        Establish a web session (kwork.ru cookies) using the official mobile API flow.

        Notes:
        - url_to_redirect must be a relative URL that starts with "/".
        - This method does not perform any action on the web site besides "login-by-token".
        """
        if url_to_redirect is not None and not url_to_redirect.startswith("/"):
            raise ValueError("url_to_redirect must be a relative URL starting with '/'")

        token_resp = await self._api.request(
            "post",
            "getWebAuthToken",
            use_token=True,
            url_to_redirect=url_to_redirect,
        )
        payload: dict[str, Any] = token_resp.get("response") or {}
        login_url = payload.get("url")
        if not isinstance(login_url, str) or not login_url:
            raise RuntimeError(f"Unexpected getWebAuthToken response: {token_resp!r}")

        parsed = urlparse(login_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"Unexpected login_url scheme: {login_url}")
        if not parsed.netloc.endswith("kwork.ru"):
            # Be defensive: prevent following an unexpected host.
            raise ValueError(f"Unexpected login_url host: {login_url}")

        headers: dict[str, str] = {}
        if user_agent:
            headers["User-Agent"] = user_agent

        effective_timeout = self._api._normalize_timeout(timeout) if timeout is not None else None  # type: ignore[attr-defined]
        req_kwargs: dict[str, Any] = {
            "method": "GET",
            "url": login_url,
            "headers": headers or None,
            "allow_redirects": allow_redirects,
            "max_redirects": max_redirects,
        }
        if effective_timeout is not None:
            req_kwargs["timeout"] = effective_timeout

        async with self._api.session.request(**req_kwargs) as resp:
            # Consume body so aiohttp stores cookies from redirects/responses.
            await resp.read()
            final_url = str(resp.url)
            status = resp.status

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Web login via token completed: status=%s final_url=%s", status, final_url
            )

        return WebLoginResult(
            token=payload.get("token"),
            expires_at=payload.get("expires_at"),
            login_url=login_url,
            url_to_redirect=payload.get("url_to_redirect"),
            final_url=final_url,
            status=status,
        )

    async def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: dict[str, Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
        allow_redirects: bool = True,
        timeout: aiohttp.ClientTimeout | float | None = None,
    ) -> dict[str, Any]:
        """
        Make a request to kwork.ru using the current aiohttp cookie jar.

        Returns a dict with:
        - status: int
        - url: final URL
        - headers: response headers (stringified)
        - text: response body (decoded)
        - json: parsed JSON if response looks like JSON, else None
        """
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            url = path_or_url
        else:
            url = urljoin(self._base_url, path_or_url.lstrip("/"))

        effective_timeout = self._api._normalize_timeout(timeout) if timeout is not None else None  # type: ignore[attr-defined]
        req_kwargs: dict[str, Any] = {
            "method": method.upper(),
            "url": url,
            "params": params,
            "data": data,
            "headers": headers,
            "allow_redirects": allow_redirects,
        }
        if effective_timeout is not None:
            req_kwargs["timeout"] = effective_timeout

        async with self._api.session.request(**req_kwargs) as resp:
            text = await resp.text(errors="replace")
            content_type = resp.headers.get("Content-Type", "")
            parsed_json: Any | None = None
            if "application/json" in content_type or content_type.endswith("+json"):
                try:
                    parsed_json = json.loads(text)
                except json.JSONDecodeError:
                    parsed_json = None

            return {
                "status": resp.status,
                "url": str(resp.url),
                "headers": {k: v for k, v in resp.headers.items()},
                "text": text,
                "json": parsed_json,
            }

    async def create_exchange_offer(
        self,
        *,
        want_id: int,
        offer_type: str = "custom",
        description: str,
        kwork_duration: int,
        kwork_price: int,
        kwork_name: str,
        user_agent: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Create an exchange offer for a want/project via the web endpoint.

        Mirrors the observed WebView XHR:
        POST https://kwork.ru/api/offer/createoffer?... (params in query string)

        Prerequisite: call `login_via_mobile_web_auth_token(...)` first to establish web cookies.
        """
        headers: dict[str, str] = {
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        }
        if user_agent:
            headers["User-Agent"] = user_agent
        if extra_headers:
            headers.update(extra_headers)

        params: dict[str, Any] = {
            "wantId": want_id,
            "offerType": offer_type,
            "description": description,
            "kwork_duration": kwork_duration,
            "kwork_price": kwork_price,
            "kwork_name": kwork_name,
        }
        # This endpoint lives on kwork.ru, not api.kwork.ru.
        return await self.request("POST", "api/offer/createoffer", params=params, headers=headers)
