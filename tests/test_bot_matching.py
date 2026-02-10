import asyncio

from kwork.bot import Handler, KworkBot
from kwork.schema import Message


def test_text_contains_word_strips_punctuation_and_is_case_insensitive() -> None:
    assert KworkBot._text_contains_word("hello", "Hello, world!") is True
    assert KworkBot._text_contains_word("hello", "(hello)") is True
    assert KworkBot._text_contains_word("hello", "shellow") is False


def test_should_handle_matches_exact_text_case_insensitive() -> None:
    bot = KworkBot(login="x", password="y")
    msg = Message(api=bot, from_id=1, text="HeLLo")

    handler = Handler(func=lambda *_: None, text="hello", on_start=False, text_contains=None)
    assert asyncio.run(bot._should_handle(msg, handler)) is True


def test_should_handle_matches_word_contains() -> None:
    bot = KworkBot(login="x", password="y")
    msg = Message(api=bot, from_id=1, text="Ping, please.")

    handler = Handler(func=lambda *_: None, text=None, on_start=False, text_contains="ping")
    assert asyncio.run(bot._should_handle(msg, handler)) is True
