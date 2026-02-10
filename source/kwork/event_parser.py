import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote_plus

from pydantic import ValidationError

from kwork.schema import BaseEvent, EventType, Message, Notify

if TYPE_CHECKING:
    from kwork.client import KworkClient

logger: logging.Logger = logging.getLogger(__name__)


def _load_json_object(text: str) -> dict[str, Any] | None:
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_event_text_payload(text: Any) -> dict[str, Any] | None:
    """
    Websocket payload includes a top-level JSON with a "text" field.

    In practice, "text" can be:
    - a JSON string, e.g. '{"event":"new_inbox","data":{...}}'
    - URL-encoded JSON, e.g. '%7B%22event%22%3A...%7D'
    - empty / non-JSON frames (pings, etc.)
    """
    if isinstance(text, dict):
        return text
    if not isinstance(text, str):
        return None

    s = text.strip()
    if not s:
        return None

    # Some transports prefix payloads with "data:" (SSE-like).
    if s.startswith("data:"):
        s = s[5:].strip()
        if not s:
            return None

    parsed = _load_json_object(s)
    if parsed is not None:
        return parsed

    # If the payload is URL-encoded JSON, decode it and try again.
    if "%" in s or "+" in s:
        decoded = unquote_plus(s).strip()
        if decoded.startswith("data:"):
            decoded = decoded[5:].strip()
        if not decoded:
            return None
        parsed = _load_json_object(decoded)
        if parsed is not None:
            return parsed

    return None


@dataclass
class ParsedMessage:
    from_id: int
    text: str
    to_user_id: int | None = None
    inbox_id: int | None = None
    title: str | None = None
    last_message: dict[str, Any] | None = None


class EventParser:
    def __init__(self, client: "KworkClient") -> None:
        self._client = client

    def parse_raw_event(self, raw_data: str) -> BaseEvent | None:
        try:
            json_event: Any = json.loads(raw_data)
            if not isinstance(json_event, dict):
                return None

            event_data = _parse_event_text_payload(json_event.get("text"))
            if event_data is None:
                return None

            return BaseEvent(**event_data)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, ValidationError) as e:
            logger.warning("Failed to parse event: %s", e)
            return None

    def should_skip_event(self, event: BaseEvent) -> bool:
        return event.event in (EventType.IS_TYPING,)

    async def extract_message(self, event: BaseEvent) -> Message | None:
        if event.data is None:
            return None

        parsed = await self._parse_event_to_message(event)
        if parsed is None:
            return None

        return Message(
            api=self._client,
            from_id=parsed.from_id,
            text=parsed.text,
            to_user_id=parsed.to_user_id,
            inbox_id=parsed.inbox_id,
            title=parsed.title,
            last_message=parsed.last_message,
        )

    async def _parse_event_to_message(self, event: BaseEvent) -> ParsedMessage | None:
        if event.event == EventType.NEW_MESSAGE:
            return self._parse_new_message(event)

        if event.event == EventType.NOTIFY:
            return await self._parse_notify(event)

        if event.event == EventType.POP_UP_NOTIFY:
            return await self._parse_popup_notify(event)

        return None

    def _parse_new_message(self, event: BaseEvent) -> ParsedMessage | None:
        data = event.data
        if data is None:
            return None

        from_raw = data.get("from")
        text = data.get("inboxMessage")
        if not isinstance(text, str):
            return None

        if isinstance(from_raw, int):
            from_id = from_raw
        else:
            if from_raw is None:
                return None
            try:
                from_id = int(from_raw)
            except (TypeError, ValueError):
                return None

        return ParsedMessage(
            from_id=from_id,
            text=text,
            to_user_id=data.get("to_user_id"),
            inbox_id=data.get("inbox_id"),
            title=data.get("title"),
            last_message=data.get("lastMessage"),
        )

    async def _parse_notify(self, event: BaseEvent) -> ParsedMessage | None:
        data = event.data
        if data is None or data.get(Notify.NEW_MESSAGE) is None:
            return None

        if data.get("dialog_data") is None:
            return await self._parse_notify_from_dialogs()

        return await self._parse_notify_from_dialog_data(data)

    async def _parse_notify_from_dialogs(self) -> ParsedMessage | None:
        dialogs = await self._client.get_dialogs_page(page=1)
        if not dialogs:
            return None

        last_dialog = dialogs[0]
        if last_dialog.user_id is None or last_dialog.last_message is None:
            return None

        return ParsedMessage(
            from_id=last_dialog.user_id,
            text=last_dialog.last_message,
        )

    async def _parse_notify_from_dialog_data(
        self,
        data: dict[str, Any],
    ) -> ParsedMessage | None:
        dialog_data = data.get("dialog_data")
        if not dialog_data or not isinstance(dialog_data, list):
            return None

        login = dialog_data[0].get("login")
        if not login:
            return None

        messages = await self._client.get_dialog_with_user(login)

        if not messages:
            return None

        msg = messages[0]
        if msg.from_id is None or msg.message is None:
            return None

        return ParsedMessage(
            from_id=msg.from_id,
            text=msg.message,
            to_user_id=msg.to_id,
            inbox_id=msg.message_id,
        )

    async def _parse_popup_notify(self, event: BaseEvent) -> ParsedMessage | None:
        data = event.data
        if data is None:
            return None

        pop_up_notify = data.get("pop_up_notify")
        if not pop_up_notify or not isinstance(pop_up_notify, dict):
            return None

        notify_data = pop_up_notify.get("data")
        if not notify_data or not isinstance(notify_data, dict):
            return None

        username = notify_data.get("username")
        if not username:
            return None

        messages = await self._client.get_dialog_with_user(username)

        if not messages:
            return None

        msg = messages[0]
        if msg.from_id is None or msg.message is None:
            return None

        return ParsedMessage(
            from_id=msg.from_id,
            text=msg.message,
            to_user_id=msg.to_id,
            inbox_id=msg.message_id,
        )
