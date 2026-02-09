from __future__ import annotations

import json
import logging
import secrets
import string
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import aiohttp
from yarl import URL

from kwork.api import KworkAPI
from kwork.exceptions import KworkException

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
        if not isinstance(token_resp, dict):
            raise RuntimeError(f"Unexpected getWebAuthToken response type: {type(token_resp)!r}")

        payload_raw = token_resp.get("response")
        payload: dict[str, Any] = payload_raw if isinstance(payload_raw, dict) else {}
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

        # Some login-by-token flows may use HTML/JS redirects rather than HTTP redirects.
        # Ensure we actually touch the target page to populate any additional cookies (e.g. XSRF-TOKEN).
        if url_to_redirect:
            target_url = urljoin(self._base_url, url_to_redirect.lstrip("/"))
            async with self._api.session.get(
                target_url,
                headers=headers or None,
                allow_redirects=allow_redirects,
                timeout=effective_timeout,
            ) as resp2:
                await resp2.read()
                final_url = str(resp2.url)
                status = resp2.status

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Web login via token completed: status=%s final_url=%s", status, final_url)

        return WebLoginResult(
            token=payload.get("token"),
            expires_at=payload.get("expires_at"),
            login_url=login_url,
            url_to_redirect=payload.get("url_to_redirect"),
            final_url=final_url,
            status=status,
        )

    def _filtered_cookies(self, url: str) -> dict[str, str]:
        # `filter_cookies` returns SimpleCookie; turn into a plain dict.
        cookies = self._api.session.cookie_jar.filter_cookies(URL(url))
        out: dict[str, str] = {}
        for name, morsel in cookies.items():
            out[name] = morsel.value
        return out

    def _maybe_add_csrf_headers(self, url: str, headers: dict[str, str]) -> None:
        """
        Best-effort CSRF header injection for common patterns (XSRF-TOKEN cookie).
        Safe even if unused by the server.
        """
        cookies = self._filtered_cookies(url)

        # Common patterns:
        # - Laravel/axios: cookie "XSRF-TOKEN" + header "X-XSRF-TOKEN"
        # - Some setups: cookie "csrf_token" + header "X-CSRF-Token"
        if "X-XSRF-TOKEN" not in headers and "XSRF-TOKEN" in cookies:
            headers["X-XSRF-TOKEN"] = unquote(cookies["XSRF-TOKEN"])
        if "X-CSRF-Token" not in headers and "csrf_token" in cookies:
            headers["X-CSRF-Token"] = cookies["csrf_token"]
        # Kwork appears to use csrf_user_token cookie for some XHR flows.
        if "X-CSRF-Token" not in headers and "csrf_user_token" in cookies:
            headers["X-CSRF-Token"] = cookies["csrf_user_token"]

        # XHR requests often require Origin/Referer; add defaults if missing.
        if "Origin" not in headers:
            parsed = urlparse(url)
            headers["Origin"] = f"{parsed.scheme}://{parsed.netloc}"
        if "Referer" not in headers:
            headers["Referer"] = self._base_url

    def _build_xhr_headers(
        self,
        *,
        user_agent: str | None = None,
        accept: str | None = None,
        referer: str | None = None,
    ) -> dict[str, str]:
        headers: dict[str, str] = {"X-Requested-With": "XMLHttpRequest"}
        if accept:
            headers["Accept"] = accept
        if user_agent:
            headers["User-Agent"] = user_agent
        if referer:
            headers["Referer"] = referer
        return headers

    @staticmethod
    def _gen_draft_key(length: int = 8) -> str:
        alphabet = string.ascii_lowercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def _extract_draft_key(html: str) -> str | None:
        # Best-effort: draftKey may be embedded in HTML/JS.
        patterns = [
            r'draftKey["\']?\s*[:=]\s*["\']([a-z0-9]{6,64})["\']',
            r'name=["\']draftKey["\']\s+value=["\']([a-z0-9]{6,64})["\']',
            r'data-draft-key=["\']([a-z0-9]{6,64})["\']',
        ]
        for pat in patterns:
            m = re.search(pat, html, flags=re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _extract_csrf_user_token(html: str) -> str | None:
        patterns = [
            r'csrf_user_token["\']?\s*[:=]\s*["\']([a-f0-9]{16,128})["\']',
            r'name=["\']csrftoken["\']\s+value=["\']([a-f0-9]{16,128})["\']',
        ]
        for pat in patterns:
            m = re.search(pat, html, flags=re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    async def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: dict[str, Any] | None = None,
        data: Any = None,
        json_data: Any | None = None,
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

        hdrs = dict(headers or {})
        if "X-Requested-With" in hdrs:
            self._maybe_add_csrf_headers(url, hdrs)

        effective_timeout = self._api._normalize_timeout(timeout) if timeout is not None else None  # type: ignore[attr-defined]
        req_kwargs: dict[str, Any] = {
            "method": method.upper(),
            "url": url,
            "params": params,
            "data": data,
            "json": json_data,
            "headers": hdrs or None,
            "allow_redirects": allow_redirects,
        }
        if json_data is not None:
            # Avoid ambiguity in aiohttp when both are supplied.
            req_kwargs.pop("data", None)
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

    async def quick_faq_init(
        self,
        *,
        referer: str,
        user_agent: str | None = None,
        page: str = "new_offer",
    ) -> dict[str, Any]:
        headers = self._build_xhr_headers(
            user_agent=user_agent,
            accept="application/json, text/plain, */*",
            referer=referer,
        )
        headers["Content-Type"] = "application/json"
        resp = await self.request(
            "POST",
            "quick-faq/init",
            headers=headers,
            json_data={"page": page},
        )
        self._raise_on_web_error(resp, where="quick-faq/init")
        return resp

    async def create_offer_draft(
        self,
        *,
        project_id: int,
        csrftoken: str,
        draft_key: str,
        message: str = "",
        referer: str,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        headers = self._build_xhr_headers(
            user_agent=user_agent,
            accept="*/*",
            referer=referer,
        )
        form = aiohttp.FormData(default_to_multipart=True)
        form.add_field("csrftoken", csrftoken)
        form.add_field("projectId", str(project_id))
        form.add_field("message", message)
        form.add_field("draftKey", draft_key)
        resp = await self.request("POST", "wants/create_offer_draft", headers=headers, data=form)
        self._raise_on_web_error(resp, where="wants/create_offer_draft")
        return resp

    async def check_is_template(
        self,
        *,
        want_id: int,
        description: str,
        referer: str,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        headers = self._build_xhr_headers(
            user_agent=user_agent,
            accept="application/json, text/plain, */*",
            referer=referer,
        )
        headers["Content-Type"] = "application/json"
        resp = await self.request(
            "POST",
            "projects/check_is_template",
            headers=headers,
            json_data={"description": description, "wantid": want_id},
        )
        self._raise_on_web_error(resp, where="projects/check_is_template")
        return resp

    async def open_new_offer_page(
        self,
        *,
        project_id: int,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if user_agent:
            headers["User-Agent"] = user_agent
        resp = await self.request("GET", f"new_offer?project={project_id}", headers=headers or None)
        if resp.get("status") not in {200, 302}:
            raise KworkException(f"Failed to open /new_offer page: HTTP {resp.get('status')}")
        return resp

    @staticmethod
    def _raise_on_web_error(resp: dict[str, Any], *, where: str) -> None:
        j = resp.get("json")
        if isinstance(j, dict) and j.get("success") is False:
            msg = j.get("message") or j.get("error") or j.get("response") or "Web API error"
            raise KworkException(f"{where}: {msg}")

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
        raise_on_error: bool = True,
        referer: str | None = None,
    ) -> dict[str, Any]:
        """
        Create an exchange offer for a want/project via the web endpoint.

        Mirrors the observed WebView XHR:
        POST https://kwork.ru/api/offer/createoffer?... (params in query string)

        Prerequisite: call `login_via_mobile_web_auth_token(...)` first to establish web cookies.
        """
        headers = self._build_xhr_headers(
            user_agent=user_agent,
            accept="application/json, text/plain, */*",
            referer=referer,
        )
        if extra_headers:
            headers.update(extra_headers)

        form = aiohttp.FormData(default_to_multipart=True)
        form.add_field("wantId", str(want_id))
        form.add_field("offerType", offer_type)
        form.add_field("description", description)
        form.add_field("kwork_duration", str(kwork_duration))
        form.add_field("kwork_price", str(kwork_price))
        form.add_field("kwork_name", kwork_name)

        # Keep also for query string compatibility (some codepaths might read from query).
        query_params: dict[str, Any] = {
            "wantId": want_id,
            "offerType": offer_type,
        }

        resp = await self.request(
            "POST",
            "api/offer/createoffer",
            params=query_params,
            data=form,
            headers=headers,
        )

        if raise_on_error:
            self._raise_on_web_error(resp, where="api/offer/createoffer")

        return resp

    async def submit_exchange_offer(
        self,
        *,
        project_id: int,
        offer_type: str = "custom",
        description: str,
        kwork_duration: int,
        kwork_price: int,
        kwork_name: str,
        user_agent: str | None = None,
        raise_on_error: bool = True,
    ) -> dict[str, Any]:
        """
        High-level helper that replicates the browser flow for /new_offer.

        Observed steps (approx):
        - POST /quick-faq/init
        - POST /wants/create_offer_draft (multipart, includes csrftoken + draftKey)
        - POST /projects/check_is_template
        - POST /api/offer/createoffer (multipart)
        """
        referer = urljoin(self._base_url, f"new_offer?project={project_id}")

        page = await self.open_new_offer_page(project_id=project_id, user_agent=user_agent)
        html = page.get("text") or ""

        # Prefer cookie; fallback to HTML parsing.
        cookies = self._filtered_cookies(self._base_url)
        csrftoken = cookies.get("csrf_user_token") or self._extract_csrf_user_token(html or "")
        if not csrftoken:
            raise RuntimeError("csrf_user_token cookie not found; cannot continue web offer flow")

        draft_key = self._extract_draft_key(html or "") or self._gen_draft_key()

        await self.quick_faq_init(referer=referer, user_agent=user_agent, page="new_offer")
        await self.create_offer_draft(
            project_id=project_id,
            csrftoken=csrftoken,
            draft_key=draft_key,
            referer=referer,
            user_agent=user_agent,
        )
        await self.check_is_template(
            want_id=project_id,
            description=description,
            referer=referer,
            user_agent=user_agent,
        )
        return await self.create_exchange_offer(
            want_id=project_id,
            offer_type=offer_type,
            description=description,
            kwork_duration=kwork_duration,
            kwork_price=kwork_price,
            kwork_name=kwork_name,
            user_agent=user_agent,
            referer=referer,
            raise_on_error=raise_on_error,
        )
