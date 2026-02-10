import asyncio
import json
from typing import Any

import pytest

from kwork.api import KworkAPI
from kwork.exceptions import KworkException, KworkHTTPException


class _FakeResp:
    def __init__(
        self,
        *,
        status: int,
        content_type: str,
        body_text: str,
    ) -> None:
        self.status = status
        self.content_type = content_type
        self._body_text = body_text

    async def text(self, *, errors: str | None = None) -> str:  # noqa: ARG002
        return self._body_text


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_handle_json_payload_raises_on_non_json_response_even_if_200() -> None:
    api = KworkAPI(login="x", password="y")
    resp = _FakeResp(status=200, content_type="text/plain", body_text="ok")

    with pytest.raises(KworkHTTPException) as ctx:
        _run(
            api._handle_json_payload(  # type: ignore[arg-type]
                resp,
                "endpoint",
                method="get",
                request_params=None,
                request_body=None,
            )
        )

    assert ctx.value.status == 200
    assert ctx.value.endpoint == "endpoint"
    assert ctx.value.response_text == "ok"


def test_handle_json_payload_raises_on_api_level_error_success_false() -> None:
    api = KworkAPI(login="x", password="y")
    resp = _FakeResp(
        status=200,
        content_type="application/json",
        body_text=json.dumps({"success": False, "error": "nope"}),
    )

    with pytest.raises(KworkException) as ctx:
        _run(
            api._handle_json_payload(  # type: ignore[arg-type]
                resp,
                "endpoint",
                method="post",
                request_params=None,
                request_body=None,
            )
        )

    assert "nope" in str(ctx.value)


def test_handle_json_payload_returns_data_on_success_true() -> None:
    api = KworkAPI(login="x", password="y")
    resp = _FakeResp(
        status=200,
        content_type="application/json",
        body_text=json.dumps({"success": True, "response": {"ok": 1}}),
    )

    out = _run(
        api._handle_json_payload(  # type: ignore[arg-type]
            resp,
            "endpoint",
            method="post",
            request_params={"a": 1},
            request_body={"b": 2},
        )
    )

    assert out["response"]["ok"] == 1
