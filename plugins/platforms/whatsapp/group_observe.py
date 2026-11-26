"""WhatsApp observe mode: keep unaddressed group chatter as context, dispatch only when addressed.

Opt-in per adapter with ``extra.observe_unmentioned_group_messages`` (or the scoped
``WHATSAPP_OBSERVE_UNMENTIONED_GROUP_MESSAGES``). Observed context is shared at chat scope, so it
only applies to groups named explicitly in ``group_allow_from`` under ``group_policy: allowlist``.
An observed message is appended to the chat's shared session as an ``observed`` user row; a turn
that addresses the bot lands on that same session, tagged with its sender, and the runner hands
the observed rows to the model as a context-only block (``OBSERVED_CONTEXT_PROMPT_MARKER``).
"""

from __future__ import annotations

import dataclasses
import logging
import os
import time
from typing import Any, Optional

from gateway.platforms.event import MessageEvent, MessageType
from gateway.platforms.helpers import tag_safe_display_name, transcribe_observed_clips

logger = logging.getLogger(__name__)

OBSERVED_CONTEXT_PROMPT_MARKER = "observed WhatsApp group context"

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_MEDIA_HINT = {
    MessageType.PHOTO: "image; to look at it use vision_analyze with this path as image_url",
    MessageType.VIDEO: "video; open it with your file tools",
    MessageType.DOCUMENT: "document; read it with your file tools",
}


def observe_enabled(adapter: Any) -> bool:
    """``extra.observe_unmentioned_group_messages`` (bool or truthy string), else the scoped env flag."""
    from gateway.platforms.whatsapp_common import _get_wsecret
    configured = adapter.config.extra.get("observe_unmentioned_group_messages")
    if configured is None:
        configured = _get_wsecret("WHATSAPP_OBSERVE_UNMENTIONED_GROUP_MESSAGES", default="false") or "false"
    if isinstance(configured, str):
        return configured.strip().lower() in _TRUTHY
    return bool(configured)


def is_observed_chat(adapter: Any, chat_id: str) -> bool:
    """A group named explicitly in the allowlist (never through ``*``), outside free-response chats."""
    if not chat_id or not observe_enabled(adapter) or adapter._group_policy != "allowlist":
        return False
    named = {str(entry).strip() for entry in adapter._group_allow_from or () if str(entry).strip() != "*"}
    return chat_id in named and chat_id not in adapter._whatsapp_free_response_chats()


def shared_source(source):
    """The sender-less, chat-scoped source every member's observed and addressed messages share."""
    return dataclasses.replace(source, user_id=None, user_name=None, user_id_alt=None, shared_session=True)


def attributed_text(source, text: str) -> str:
    user_id = source.user_id or "unknown"
    return f"[{tag_safe_display_name(source.user_name or user_id)}|{user_id}]\n{text or ''}"


def channel_prompt(adapter: Any, data: dict[str, Any]) -> str:
    bot_ids = sorted(adapter._bot_ids_from_message(data)) or ["unknown"]
    return (
        "You are handling a WhatsApp group chat message.\n"
        f"- Your identity in this group: {', '.join(bot_ids)}\n"
        f"- {OBSERVED_CONTEXT_PROMPT_MARKER} may be provided in a separate context-only block before the "
        "current message; it is not necessarily addressed to you.\n"
        "- Each message starts with [sender name|sender id]. Treat only the current new message as a request "
        "directed at you, and use observed context only when the current message asks for it.")


def apply_attribution(adapter: Any, event: MessageEvent) -> MessageEvent:
    """Move an addressed turn in an observed group onto the chat's shared session.

    Text turns get the shared source plus a ``[name|id]`` tag, and the trusted sender stays on
    ``event.user_id`` for the live-turn actor. Commands keep their source so slash access checks
    see the sender, flagged ``shared_session`` so they key the same session.
    """
    data = event.raw_message if isinstance(event.raw_message, dict) else {}
    if not data.get("isGroup") or not is_observed_chat(adapter, str(data.get("chatId") or "")):
        return event
    prompt = channel_prompt(adapter, data)
    prompt = f"{event.channel_prompt}\n\n{prompt}" if event.channel_prompt else prompt
    if event.message_type == MessageType.COMMAND:
        return dataclasses.replace(
            event, source=dataclasses.replace(event.source, shared_session=True), channel_prompt=prompt)
    return dataclasses.replace(
        event, text=attributed_text(event.source, event.text), user_id=event.source.user_id,
        source=shared_source(event.source), channel_prompt=prompt)


def shared_sender_suffix(event: MessageEvent) -> str:
    """Batch-key suffix naming the sender: two members writing inside one batch window stay two turns."""
    actor = event.user_id or event.source.user_id
    return f":from:{actor}" if actor else ""


async def _media_notes(adapter: Any, data: dict[str, Any], source) -> list[str]:
    """One text note per attachment: a voice note is transcribed, other files are named with how to open them."""
    msg_type = adapter._classify_bridge_message(data)
    if msg_type == MessageType.TEXT:
        return []
    paths, _types = await adapter._collect_bridge_media(data, msg_type)
    paths = [p for p in paths if isinstance(p, str) and os.path.isabs(p)]
    if msg_type in (MessageType.VOICE, MessageType.AUDIO):
        return await transcribe_observed_clips(paths, adapter=adapter, source=source)
    hint = _MEDIA_HINT.get(msg_type, "file; open it with your file tools")
    return [f"[{hint}: {path}]" for path in paths]


def _observed_body(adapter: Any, data: dict[str, Any]) -> str:
    body = adapter._clean_bot_mention_text(str(data.get("body") or ""), data)
    return "" if body.strip().lower() in ("[ptt received]", "[image received]", "[video received]") else body


async def observe_group_message(adapter: Any, data: dict[str, Any]) -> bool:
    """Append an unaddressed message of an observed group to the chat's shared session. True when stored."""
    chat_id = str(data.get("chatId") or "")
    store = getattr(adapter, "_session_store", None)
    if not store or not data.get("isGroup") or data.get("fromMe") or not is_observed_chat(adapter, chat_id):
        return False
    source = adapter.build_source(
        chat_id=chat_id, chat_name=data.get("chatName"), chat_type="group", user_id=data.get("senderId"),
        user_name=data.get("senderName"), message_id=data.get("messageId"))
    try:
        notes = await _media_notes(adapter, data, source)
        text = "\n".join(part for part in (_observed_body(adapter, data), *notes) if part.strip())
        if not text:
            return False
        session = store.get_or_create_session(shared_source(source))
        entry: dict[str, Any] = {
            "role": "user", "content": attributed_text(source, text), "timestamp": time.time(), "observed": True}
        message_id: Optional[str] = data.get("messageId")
        if message_id:
            entry["message_id"] = str(message_id)
        store.append_to_transcript(session.session_id, entry)
    except Exception as exc:  # health: allow BLE001 -- observing is best effort and never blocks intake
        logger.warning("[%s] Failed to observe WhatsApp group message: %s", adapter.name, exc)
        return False
    logger.info("[%s] WhatsApp group message observed (no bot trigger): chat=%s from=%s",
                adapter.name, chat_id, source.user_id or "unknown")
    return True
