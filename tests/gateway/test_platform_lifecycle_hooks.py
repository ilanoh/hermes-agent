"""platform:connected, platform:fatal and platform:needs_attention reach the HookRegistry, so a hook can
report a platform going down or coming back (a WhatsApp device unlinked by the phone, a revoked token)."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform
from tests.gateway.test_platform_reconnect import StubAdapter, _make_runner


def _runner_with_hooks():
    runner = _make_runner()
    runner.hooks = MagicMock()
    runner.hooks.emit = AsyncMock()
    runner._background_tasks = set()
    runner._fatal_handler_tasks = set()
    runner._reconnect_watcher_task = None
    runner._update_platform_runtime_status = MagicMock()
    return runner


async def _emitted(runner):
    """Let the background emit tasks run, then return the (event, context) pairs."""
    await asyncio.gather(*runner._background_tasks)
    return [call.args for call in runner.hooks.emit.await_args_list]


@pytest.mark.asyncio
@pytest.mark.parametrize("is_reconnect", [False, True])
async def test_successful_connect_emits_platform_connected(is_reconnect):
    runner = _runner_with_hooks()

    await runner._connect_adapter_with_timeout(StubAdapter(succeed=True), Platform.TELEGRAM, is_reconnect=is_reconnect)

    assert await _emitted(runner) == [("platform:connected", {"platform": "telegram", "reconnect": is_reconnect})]


@pytest.mark.asyncio
async def test_failed_connect_emits_nothing():
    runner = _runner_with_hooks()

    await runner._connect_adapter_with_timeout(StubAdapter(succeed=False), Platform.TELEGRAM)

    assert await _emitted(runner) == []


@pytest.mark.asyncio
async def test_runtime_fatal_error_emits_platform_fatal():
    runner = _runner_with_hooks()
    adapter = StubAdapter(succeed=True)
    adapter._set_fatal_error("whatsapp_logged_out", "WhatsApp logged this device out", retryable=False)
    runner.adapters[Platform.TELEGRAM] = adapter
    runner.adapters[Platform.DISCORD] = StubAdapter(succeed=True)  # another platform stays up

    with patch.object(runner, "_ensure_reconnect_watcher_running"):
        await runner._handle_adapter_fatal_error(adapter)

    assert ("platform:fatal", {
        "platform": "telegram",
        "error_code": "whatsapp_logged_out",
        "error_message": "WhatsApp logged this device out",
        "retryable": False,
    }) in await _emitted(runner)


@pytest.mark.asyncio
async def test_needs_attention_emits_once():
    runner = _runner_with_hooks()
    now = time.monotonic()
    info = {"queued_at": now - 7200, "attempts": 26}

    with patch("gateway.run._reconnect_needs_attention", return_value=True):
        assert runner._flag_reconnect_needs_attention(Platform.TELEGRAM, info, now) is True
        assert runner._flag_reconnect_needs_attention(Platform.TELEGRAM, info, now + 60) is False

    assert await _emitted(runner) == [("platform:needs_attention", {
        "platform": "telegram",
        "status_key": "telegram",
        "attempts": 26,
        "down_for_seconds": 7200,
    })]


@pytest.mark.asyncio
async def test_runner_without_hooks_still_connects():
    runner = _make_runner()

    assert await runner._connect_adapter_with_timeout(StubAdapter(succeed=True), Platform.TELEGRAM) is True
