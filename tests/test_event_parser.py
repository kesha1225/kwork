import json
from urllib.parse import quote_plus

from kwork.event_parser import EventParser


def test_parse_raw_event_parses_json_text() -> None:
    parser = EventParser(object())  # client not used by parse_raw_event
    inner = {"event": "new_inbox", "data": {"from": 123, "inboxMessage": "hi"}}
    raw = json.dumps({"text": json.dumps(inner)})

    event = parser.parse_raw_event(raw)

    assert event is not None
    assert event.event == "new_inbox"
    assert event.data == {"from": 123, "inboxMessage": "hi"}


def test_parse_raw_event_parses_urlencoded_text() -> None:
    parser = EventParser(object())
    inner = {"event": "new_inbox", "data": {"from": 1, "inboxMessage": "hello"}}
    raw = json.dumps({"text": quote_plus(json.dumps(inner))})

    event = parser.parse_raw_event(raw)

    assert event is not None
    assert event.event == "new_inbox"
    assert event.data == {"from": 1, "inboxMessage": "hello"}


def test_parse_raw_event_parses_dict_text_payload() -> None:
    parser = EventParser(object())
    inner = {"event": "notify", "data": {"new_message": True}}
    raw = json.dumps({"text": inner})

    event = parser.parse_raw_event(raw)

    assert event is not None
    assert event.event == "notify"
    assert event.data == {"new_message": True}


def test_parse_raw_event_skips_empty_or_non_json_text() -> None:
    parser = EventParser(object())

    assert parser.parse_raw_event(json.dumps({"text": ""})) is None
    assert parser.parse_raw_event(json.dumps({"text": "   "})) is None
    assert parser.parse_raw_event(json.dumps({"text": "ping"})) is None
