import asyncio
from unittest.mock import AsyncMock

from kwork.schema import Message


def test_fast_answer_calls_send_message() -> None:
    class _API:
        send_message = AsyncMock()

    api = _API()
    msg = Message(api=api, from_id=7, text="hi")  # type: ignore[arg-type]

    asyncio.run(msg.fast_answer("ok"))

    api.send_message.assert_awaited_once_with(7, text="ok")


def test_answer_simulation_calls_typing_then_send_message_and_sleeps() -> None:
    events: list[str] = []

    async def _sleep(_: float) -> None:
        events.append("sleep")

    class _API:
        async def set_typing(self, user_id: int) -> None:
            events.append(f"typing:{user_id}")

        async def send_message(self, user_id: int, *, text: str) -> None:
            events.append(f"send:{user_id}:{text}")

    api = _API()
    msg = Message(api=api, from_id=3, text="hi")  # type: ignore[arg-type]

    orig_sleep = asyncio.sleep
    asyncio.sleep = _sleep  # type: ignore[assignment]
    try:
        asyncio.run(msg.answer_simulation("reply"))
    finally:
        asyncio.sleep = orig_sleep  # type: ignore[assignment]

    assert events == ["sleep", "typing:3", "sleep", "send:3:reply"]
