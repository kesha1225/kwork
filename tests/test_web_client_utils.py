from kwork.web_client import KworkWebClient


def test_extract_draft_key_from_common_patterns() -> None:
    assert KworkWebClient._extract_draft_key('var x = {"draftKey":"abc123"};') == "abc123"
    assert KworkWebClient._extract_draft_key("<input name='draftKey' value='zz99aa' />") == "zz99aa"
    assert KworkWebClient._extract_draft_key("<div data-draft-key='k1k2k3'></div>") == "k1k2k3"
    assert KworkWebClient._extract_draft_key("nope") is None


def test_extract_csrf_user_token_from_common_patterns() -> None:
    token = "a" * 32
    assert KworkWebClient._extract_csrf_user_token(f'csrf_user_token="{token}"') == token
    assert (
        KworkWebClient._extract_csrf_user_token(f"<input name='csrftoken' value='{token}' />")
        == token
    )
    assert KworkWebClient._extract_csrf_user_token("nope") is None


def test_maybe_add_csrf_headers_adds_origin_referer_and_tokens() -> None:
    class _DummyAPI:
        pass

    class _Client(KworkWebClient):
        def _filtered_cookies(self, url: str) -> dict[str, str]:  # noqa: ARG002
            # XSRF cookie values are commonly URL-escaped.
            return {
                "XSRF-TOKEN": "a%2Bb",
                "csrf_token": "csrf1",
                "csrf_user_token": "csrf2",
            }

    wc = _Client(_DummyAPI(), base_url="https://kwork.ru/")  # type: ignore[arg-type]
    headers: dict[str, str] = {"X-Requested-With": "XMLHttpRequest"}
    wc._maybe_add_csrf_headers("https://kwork.ru/api/offer/createoffer", headers)

    assert headers["X-XSRF-TOKEN"] == "a+b"
    # Prefer csrf_token, and don't overwrite if already present.
    assert headers["X-CSRF-Token"] == "csrf1"
    assert headers["Origin"] == "https://kwork.ru"
    assert headers["Referer"] == "https://kwork.ru/"


def test_maybe_add_csrf_headers_does_not_override_existing_csrf_header() -> None:
    class _DummyAPI:
        pass

    class _Client(KworkWebClient):
        def _filtered_cookies(self, url: str) -> dict[str, str]:  # noqa: ARG002
            return {"csrf_token": "cookie-csrf"}

    wc = _Client(_DummyAPI(), base_url="https://kwork.ru/")  # type: ignore[arg-type]
    headers = {"X-Requested-With": "XMLHttpRequest", "X-CSRF-Token": "already"}
    wc._maybe_add_csrf_headers("https://kwork.ru/x", headers)
    assert headers["X-CSRF-Token"] == "already"
