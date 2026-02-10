import asyncio
import logging
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable
from typing import Any, NamedTuple, TypeVar

import websockets
from kwork.client import KworkClient
from kwork.event_parser import EventParser
from kwork.exceptions import KworkBotException, KworkException
from kwork.schema import Message

logger: logging.Logger = logging.getLogger(__name__)

WEBSOCKET_URI = "wss://notice.kwork.ru/ws/public/{}"
RECONNECT_DELAY = 10

_T = TypeVar("_T")


class Handler(NamedTuple):
    func: Callable[..., Any]
    text: str | None
    on_start: bool
    text_contains: str | None


class KworkBot(KworkClient):
    def __init__(
        self,
        login: str,
        password: str,
        proxy: str | None = None,
        phone_last: str | None = None,
        *,
        username_cache_max: int = 4096,
        dialog_state_cache_max: int = 8192,
    ) -> None:
        super().__init__(login, password, proxy, phone_last)
        self._handlers: list[Handler] = []
        self._event_parser = EventParser(self)

        if username_cache_max < 0:
            raise ValueError("username_cache_max must be >= 0")
        if dialog_state_cache_max < 0:
            raise ValueError("dialog_state_cache_max must be >= 0")

        self._username_cache_max = username_cache_max
        self._dialog_state_cache_max = dialog_state_cache_max

        # Bounded LRU caches to prevent unbounded memory growth in long-running bots.
        # - user_id -> username: avoids re-scanning dialogs.
        # - on_start suppression set: ensures on_start handler fires at most once per user_id in this process.
        self._user_id_to_username: OrderedDict[int, str] = OrderedDict()
        self._on_start_suppressed_user_ids: OrderedDict[int, bool] = OrderedDict()

    @staticmethod
    def _lru_get(cache: OrderedDict[int, _T], key: int) -> _T | None:
        try:
            value = cache[key]
        except KeyError:
            return None
        cache.move_to_end(key)
        return value

    @staticmethod
    def _lru_set(cache: OrderedDict[int, _T], key: int, value: _T, *, maxsize: int) -> None:
        if maxsize == 0:
            return
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > maxsize:
            cache.popitem(last=False)

    def message_handler(
        self,
        text: str | None = None,
        on_start: bool = False,
        text_contains: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """
        Декоратор для регистрации обработчика сообщений.

        text: Ответить на точное совпадение текста сообщения
        on_start: Ответить только на первое сообщение в диалоге
        text_contains: Ответить если сообщение содержит это слово
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            handler = Handler(func, text, on_start, text_contains)
            self._handlers.append(handler)
            return func

        return decorator

    async def run(self) -> None:
        if not self._handlers:
            raise KworkBotException("No handlers registered. Add at least one handler.")

        logger.info("Bot is running!")

        try:
            async for message in self._listen_messages():
                await self._process_message(message)
        except asyncio.CancelledError:
            # Don't swallow cancellation; just ensure resources are closed.
            logger.info("Bot run cancelled. Shutting down...")
            raise
        finally:
            await self.close()

    async def _listen_messages(self) -> AsyncIterator[Message]:
        logger.info("Starting message listener")

        while True:
            try:
                async for message in self._websocket_loop():
                    yield message
            except KworkException as e:
                logger.exception("Error in listener: %s. Restarting...", e)
                await asyncio.sleep(RECONNECT_DELAY)
            except Exception as e:
                # Be resilient to parsing / unexpected schema changes: keep the bot running.
                logger.exception("Unexpected error in listener: %s. Restarting...", e)
                await asyncio.sleep(RECONNECT_DELAY)

    async def _websocket_loop(self) -> AsyncIterator[Message]:
        channel = await self.get_channel()
        uri = WEBSOCKET_URI.format(channel)

        async with websockets.connect(uri) as ws:
            while True:
                message = await self._receive_message(ws)
                if message is not None:
                    yield message

    async def _receive_message(
        self,
        ws: websockets.ClientConnection,
    ) -> Message | None:
        try:
            raw_data = await ws.recv()
        except websockets.exceptions.ConnectionClosedError as e:
            logger.debug("Connection closed: %s. Reconnecting...", e)
            raise KworkException("WebSocket connection closed") from e

        raw_text = (
            raw_data.decode("utf-8", errors="replace")
            if isinstance(raw_data, (bytes, bytearray))
            else str(raw_data)
        )
        logger.debug("Received: %s", raw_text)

        event = self._event_parser.parse_raw_event(raw_text)
        if event is None or self._event_parser.should_skip_event(event):
            return None

        return await self._event_parser.extract_message(event)

    async def _process_message(self, message: Message) -> None:
        for handler in self._handlers:
            if await self._should_handle(message, handler):
                logger.debug("Dispatching to handler: %s", handler.func.__name__)
                await handler.func(message)
                break

    async def _should_handle(self, message: Message, handler: Handler) -> bool:
        if not any([handler.on_start, handler.text, handler.text_contains]):
            return True

        if handler.on_start:
            return await self._check_is_first_message(message)

        if handler.text is not None:
            return handler.text.lower() == message.text.lower()

        if handler.text_contains is not None:
            return self._text_contains_word(handler.text_contains, message.text)

        return False

    async def _check_is_first_message(self, message: Message) -> bool:
        user_id = message.from_id

        # Fast-path: avoid repeated API calls after we've already made a decision for this dialog.
        if self._lru_get(self._on_start_suppressed_user_ids, user_id) is not None:
            return False

        username = await self._get_username_for_user_id(user_id)
        if not username:
            return False

        # We only need to know whether the dialog has exactly 1 message.
        # Use paging to avoid loading the whole history.
        page_messages, paging = await self.get_dialog_with_user_page(username, page=1)
        pages = paging.get("pages")

        if isinstance(pages, int) and pages > 1:
            self._lru_set(
                self._on_start_suppressed_user_ids,
                user_id,
                True,
                maxsize=self._dialog_state_cache_max,
            )
            return False

        if pages is None:
            # Be defensive if API doesn't return paging: fall back to the full dialog fetch only when ambiguous.
            if len(page_messages) > 1:
                self._lru_set(
                    self._on_start_suppressed_user_ids,
                    user_id,
                    True,
                    maxsize=self._dialog_state_cache_max,
                )
                return False
            dialog_messages = await self.get_dialog_with_user(username)
            is_first = len(dialog_messages) == 1
        else:
            is_first = len(page_messages) == 1

        # Whether it's first or not, we must not fire on_start again for this user_id in this process.
        self._lru_set(
            self._on_start_suppressed_user_ids, user_id, True, maxsize=self._dialog_state_cache_max
        )
        return is_first

    async def _get_username_for_user_id(self, user_id: int) -> str | None:
        cached = self._lru_get(self._user_id_to_username, user_id)
        if cached is not None:
            return cached

        page = 1
        while True:
            dialogs = await self.get_dialogs_page(page=page)
            if not dialogs:
                return None

            for dialog in dialogs:
                if dialog.user_id == user_id and dialog.username:
                    self._lru_set(
                        self._user_id_to_username,
                        user_id,
                        dialog.username,
                        maxsize=self._username_cache_max,
                    )
                    return dialog.username

            page += 1

    @staticmethod
    def _text_contains_word(word: str, text: str) -> bool:
        punctuation = ".,!?;:\"'()-…"
        words = text.lower().split()
        return any(word.lower() == w.strip(punctuation) for w in words)
