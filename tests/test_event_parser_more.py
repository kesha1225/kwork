import asyncio
import json
from unittest.mock import AsyncMock

from kwork.event_parser import EventParser, _parse_event_text_payload
from kwork.schema import BaseEvent, DialogMessage, EventType, InboxMessage, Message


def test_parse_event_text_payload_supports_data_prefix() -> None:
    inner = {"event": "new_inbox", "data": {"from": 1, "inboxMessage": "hi"}}
    payload = "data:" + json.dumps(inner)
    assert _parse_event_text_payload(payload) == inner


def test_parse_event_text_payload_supports_urlencoded_and_data_prefix() -> None:
    inner = {"event": "new_inbox", "data": {"from": 1, "inboxMessage": "hi"}}
    raw = "data:%7B%22event%22%3A%22new_inbox%22%2C%22data%22%3A%7B%22from%22%3A1%2C%22inboxMessage%22%3A%22hi%22%7D%7D"
    assert _parse_event_text_payload(raw) == inner


def test_parse_raw_event_returns_none_for_non_dict_top_level_json() -> None:
    parser = EventParser(object())  # type: ignore[arg-type]
    assert parser.parse_raw_event(json.dumps([1, 2, 3])) is None


def test_should_skip_event_is_typing() -> None:
    parser = EventParser(object())  # type: ignore[arg-type]
    assert parser.should_skip_event(BaseEvent(event=EventType.IS_TYPING)) is True


def test_extract_message_notify_from_dialogs_uses_last_dialog() -> None:
    class _Client:
        get_dialogs_page = AsyncMock(
            return_value=[
                DialogMessage(user_id=9, last_message="last"),
            ]
        )

    client = _Client()
    parser = EventParser(client)  # type: ignore[arg-type]

    event = BaseEvent(event=EventType.NOTIFY, data={"new_message": True})
    msg = asyncio.run(parser.extract_message(event))

    assert isinstance(msg, Message)
    assert msg.from_id == 9
    assert msg.text == "last"


def test_extract_message_notify_from_dialog_data_fetches_dialog_messages() -> None:
    class _Client:
        get_dialog_with_user = AsyncMock(
            return_value=[
                InboxMessage(message_id=11, from_id=3, to_id=4, message="hey"),
            ]
        )

    client = _Client()
    parser = EventParser(client)  # type: ignore[arg-type]

    event = BaseEvent(
        event=EventType.NOTIFY,
        data={"new_message": True, "dialog_data": [{"login": "u1"}]},
    )
    msg = asyncio.run(parser.extract_message(event))

    assert msg is not None
    assert msg.from_id == 3
    assert msg.text == "hey"
    assert msg.to_user_id == 4
    assert msg.inbox_id == 11


def test_extract_message_popup_notify_fetches_dialog_messages() -> None:
    class _Client:
        get_dialog_with_user = AsyncMock(
            return_value=[
                InboxMessage(message_id=12, from_id=5, to_id=6, message="yo"),
            ]
        )

    client = _Client()
    parser = EventParser(client)  # type: ignore[arg-type]

    event = BaseEvent(
        event=EventType.POP_UP_NOTIFY,
        data={"pop_up_notify": {"data": {"username": "u1"}}},
    )
    msg = asyncio.run(parser.extract_message(event))

    assert msg is not None
    assert msg.from_id == 5
    assert msg.text == "yo"
