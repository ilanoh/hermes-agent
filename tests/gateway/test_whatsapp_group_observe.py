"""WhatsApp observe mode: unaddressed chatter of an allowlisted group is stored as context only."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.event import MessageEvent, MessageType
from gateway.run import _OBSERVED_CONTEXT_PROMPT_MARKERS, _build_gateway_agent_history
from plugins.platforms.whatsapp import group_observe

GROUP = "120363001234567890@g.us"
OTHER_GROUP = "120363009999999999@g.us"
BOT_IDS = ["15551230000@s.whatsapp.net", "15551230000@lid"]


class _Store:
    def __init__(self):
        self.sources, self.rows = [], []

    def get_or_create_session(self, source):
        self.sources.append(source)
        return SimpleNamespace(session_id=f"shared:{source.chat_id}")

    def append_to_transcript(self, session_id, entry):
        self.rows.append((session_id, entry))


def _adapter(observe=True, group_allow_from=(GROUP,), free_response_chats=()):
    from plugins.platforms.whatsapp.adapter import WhatsAppAdapter

    extra = {"require_mention": True, "mention_patterns": [r"\bhermes\b"], "group_policy": "allowlist",
             "group_allow_from": list(group_allow_from), "free_response_chats": list(free_response_chats),
             "observe_unmentioned_group_messages": observe}
    adapter = object.__new__(WhatsAppAdapter)
    adapter.platform = Platform.WHATSAPP
    adapter.config = PlatformConfig(enabled=True, extra=extra)
    adapter._message_handler = AsyncMock()
    adapter._dm_policy = "pairing"
    adapter._allow_from = set()
    adapter._group_policy = "allowlist"
    adapter._group_allow_from = WhatsAppAdapter._coerce_allow_list(extra["group_allow_from"])
    adapter._mention_patterns = adapter._compile_mention_patterns()
    adapter._session_store = _Store()
    return adapter


def _message(body="the export button does nothing", **overrides):
    data = {"isGroup": True, "body": body, "chatId": GROUP, "chatName": "Sales", "senderId": "33600000001@lid",
            "senderName": "Claire", "messageId": "ABC1", "mentionedIds": [], "botIds": BOT_IDS,
            "quotedParticipant": "", "hasMedia": False, "mediaType": "", "mediaUrls": []}
    data.update(overrides)
    return data


def _observe(adapter, data):
    return asyncio.run(group_observe.observe_group_message(adapter, data))


def test_unaddressed_message_is_stored_as_observed_row_on_the_shared_session():
    adapter = _adapter()

    assert adapter._should_process_message(_message()) is False
    assert _observe(adapter, _message()) is True

    (source,) = adapter._session_store.sources
    assert source.user_id is None and source.shared_session is True and source.chat_id == GROUP
    ((session_id, entry),) = adapter._session_store.rows
    assert session_id == f"shared:{GROUP}"
    assert entry["observed"] is True and entry["role"] == "user" and entry["message_id"] == "ABC1"
    assert entry["content"] == "[Claire|33600000001@lid]\nthe export button does nothing"


@pytest.mark.parametrize("adapter_kwargs, data_overrides", [
    ({"observe": False}, {}),
    ({"group_allow_from": ("*",)}, {}),
    ({}, {"chatId": OTHER_GROUP}),
    ({"free_response_chats": (GROUP,)}, {}),
    ({}, {"fromMe": True}),
    ({}, {"isGroup": False}),
])
def test_nothing_is_observed_outside_an_explicitly_allowlisted_group(adapter_kwargs, data_overrides):
    adapter = _adapter(**adapter_kwargs)

    assert _observe(adapter, _message(**data_overrides)) is False
    assert adapter._session_store.rows == []


def test_observed_voice_note_keeps_its_transcript(monkeypatch):
    adapter = _adapter()
    clip = "/cache/audio/voice_1.ogg"
    monkeypatch.setattr(adapter, "_collect_bridge_media", AsyncMock(return_value=([clip], ["audio/ogg"])))
    transcribe = AsyncMock(return_value=['[voice message transcript: "le devis ne part pas"]'])
    monkeypatch.setattr(group_observe, "transcribe_observed_clips", transcribe)

    assert _observe(adapter, _message("[ptt received]", hasMedia=True, mediaType="ptt", mediaUrls=[clip])) is True

    assert transcribe.await_args.args[0] == [clip]
    content = adapter._session_store.rows[0][1]["content"]
    assert content == '[Claire|33600000001@lid]\n[voice message transcript: "le devis ne part pas"]'


def test_observed_image_names_its_cached_path_and_how_to_open_it(monkeypatch):
    adapter = _adapter()
    image = "/cache/images/img_1.jpg"
    monkeypatch.setattr(adapter, "_collect_bridge_media", AsyncMock(return_value=([image], ["image/jpeg"])))

    assert _observe(adapter, _message("see this", hasMedia=True, mediaType="image", mediaUrls=[image])) is True

    content = adapter._session_store.rows[0][1]["content"]
    assert content.endswith(f"see this\n[image; to look at it use vision_analyze with this path as image_url: {image}]")


def test_addressed_turn_lands_on_the_shared_session_tagged_with_its_sender():
    adapter = _adapter()
    data = _message("hermes look at what Claire said", mentionedIds=[BOT_IDS[0]])
    source = adapter.build_source(chat_id=GROUP, chat_type="group", user_id="33600000002@lid", user_name="Marc")
    event = MessageEvent(text="look at what Claire said", message_type=MessageType.TEXT, source=source, raw_message=data)

    routed = group_observe.apply_attribution(adapter, event)

    assert routed.source.user_id is None and routed.source.shared_session is True
    assert routed.user_id == "33600000002@lid"
    assert routed.text == "[Marc|33600000002@lid]\nlook at what Claire said"
    assert group_observe.OBSERVED_CONTEXT_PROMPT_MARKER in routed.channel_prompt
    assert group_observe.shared_sender_suffix(routed) == ":from:33600000002@lid"


def test_turns_outside_observed_groups_are_left_untouched():
    adapter = _adapter(observe=False)
    source = adapter.build_source(chat_id=GROUP, chat_type="group", user_id="33600000002@lid", user_name="Marc")
    event = MessageEvent(text="hermes hi", message_type=MessageType.TEXT, source=source, raw_message=_message())

    assert group_observe.apply_attribution(adapter, event) is event


def test_runner_separates_observed_rows_for_whatsapp_turns():
    assert group_observe.OBSERVED_CONTEXT_PROMPT_MARKER in _OBSERVED_CONTEXT_PROMPT_MARKERS
    history = [
        {"role": "user", "content": "[Claire|1@lid]\nthe export button does nothing", "observed": True},
        {"role": "user", "content": "[Marc|2@lid]\nhermes is it a bug?"},
        {"role": "assistant", "content": "Checking."},
    ]
    prompt = group_observe.channel_prompt(_adapter(), _message())

    agent_history, observed = _build_gateway_agent_history(history, channel_prompt=prompt)

    assert observed == "[Claire|1@lid]\nthe export button does nothing"
    assert [m["role"] for m in agent_history] == ["user", "assistant"]
