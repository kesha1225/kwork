import asyncio
import inspect
from unittest.mock import AsyncMock

from kwork.api import KworkAPI
from kwork.client import KworkClient
from kwork.schema import DialogMessage, InboxMessage


def test_client_mro_uses_real_request_implementation() -> None:
    # Regression guard for the MRO comment in kwork/client.py.
    assert KworkClient.request is KworkAPI.request
    assert KworkClient.request_with_body is KworkAPI.request_with_body
    assert KworkClient.request_multipart is KworkAPI.request_multipart

    # Also ensure the resolved implementation isn't a "..."-style stub.
    src = inspect.getsource(KworkClient.request)
    assert "return await self._request_json" in src


def test_get_all_dialogs_paginates_until_empty() -> None:
    client = KworkClient(login="x", password="y")
    client.get_dialogs_page = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            [DialogMessage(user_id=1), DialogMessage(user_id=2)],
            [DialogMessage(user_id=3)],
            [],
        ]
    )

    out = asyncio.run(client.get_all_dialogs())
    assert [d.user_id for d in out] == [1, 2, 3]


def test_get_dialog_with_user_paginates_until_pages_exhausted() -> None:
    client = KworkClient(login="x", password="y")
    client.get_dialog_with_user_page = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            ([InboxMessage(message_id=1)], {"pages": 2}),
            ([InboxMessage(message_id=2)], {"pages": 2}),
        ]
    )

    out = asyncio.run(client.get_dialog_with_user("u"))
    assert [m.message_id for m in out] == [1, 2]
    assert client.get_dialog_with_user_page.await_count == 2  # type: ignore[union-attr]
