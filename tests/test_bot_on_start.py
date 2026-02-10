from unittest.mock import AsyncMock

import asyncio

from kwork.bot import KworkBot
from kwork.schema import DialogMessage, InboxMessage, Message


def test_on_start_matches_dialog_by_sender_user_id() -> None:
    async def _run() -> None:
        bot = KworkBot(login="x", password="y")

        bot.get_dialogs_page = AsyncMock(  # type: ignore[method-assign]
            return_value=[
                DialogMessage(user_id=111, username="u111"),
                DialogMessage(user_id=222, username="u222"),
            ]
        )
        bot.get_dialog_with_user_page = AsyncMock(  # type: ignore[method-assign]
            return_value=(
                [InboxMessage(message_id=1, from_id=222, message="hi")],
                {"pages": 1},
            )
        )
        bot.get_dialog_with_user = AsyncMock()  # type: ignore[method-assign]

        msg = Message(api=bot, from_id=222, text="hi")
        assert await bot._check_is_first_message(msg)

        bot.get_dialog_with_user_page.assert_awaited_with("u222", page=1)
        assert bot.get_dialogs_page.await_count == 1

        # Must not fire again for the same dialog in the same process.
        assert not await bot._check_is_first_message(msg)
        assert bot.get_dialogs_page.await_count == 1
        assert bot.get_dialog_with_user_page.await_count == 1

    asyncio.run(_run())


def test_on_start_caches_username_lookup() -> None:
    async def _run() -> None:
        bot = KworkBot(login="x", password="y")

        bot.get_dialogs_page = AsyncMock(  # type: ignore[method-assign]
            return_value=[DialogMessage(user_id=1, username="u1")]
        )
        bot.get_dialog_with_user_page = AsyncMock(  # type: ignore[method-assign]
            return_value=([InboxMessage(message_id=1, from_id=1, message="first")], {"pages": 1})
        )

        msg = Message(api=bot, from_id=1, text="first")
        assert await bot._check_is_first_message(msg)
        assert bot.get_dialogs_page.await_count == 1

        # Same sender again should not trigger a dialogs scan.
        msg2 = Message(api=bot, from_id=1, text="second")
        assert not await bot._check_is_first_message(msg2)
        assert bot.get_dialogs_page.await_count == 1

    asyncio.run(_run())


def test_on_start_marks_not_first_when_multiple_pages() -> None:
    async def _run() -> None:
        bot = KworkBot(login="x", password="y")

        bot.get_dialogs_page = AsyncMock(  # type: ignore[method-assign]
            return_value=[DialogMessage(user_id=5, username="u5")]
        )
        bot.get_dialog_with_user_page = AsyncMock(  # type: ignore[method-assign]
            return_value=([InboxMessage(message_id=10, from_id=5, message="latest")], {"pages": 2})
        )

        msg = Message(api=bot, from_id=5, text="latest")
        assert not await bot._check_is_first_message(msg)

        # Subsequent checks should short-circuit.
        assert not await bot._check_is_first_message(msg)
        assert bot.get_dialogs_page.await_count == 1
        assert bot.get_dialog_with_user_page.await_count == 1

    asyncio.run(_run())


def test_on_start_falls_back_when_paging_missing() -> None:
    async def _run() -> None:
        bot = KworkBot(login="x", password="y")

        bot.get_dialogs_page = AsyncMock(  # type: ignore[method-assign]
            return_value=[DialogMessage(user_id=9, username="u9")]
        )
        bot.get_dialog_with_user_page = AsyncMock(  # type: ignore[method-assign]
            return_value=([InboxMessage(message_id=1, from_id=9, message="only")], {})
        )
        bot.get_dialog_with_user = AsyncMock(  # type: ignore[method-assign]
            return_value=[InboxMessage(message_id=1, from_id=9, message="only")]
        )

        msg = Message(api=bot, from_id=9, text="only")
        assert await bot._check_is_first_message(msg)
        bot.get_dialog_with_user.assert_awaited_once()

    asyncio.run(_run())
