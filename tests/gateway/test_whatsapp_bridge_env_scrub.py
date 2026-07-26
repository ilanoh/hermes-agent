"""The Node bridge (networked, third-party npm deps) never inherits Hermes' credentials (#38079)."""

import pytest

from gateway.config import PlatformConfig

_OPERATOR_SECRETS = {
    "OPENAI_API_KEY": "sk-operator-openai",
    "ANTHROPIC_API_KEY": "sk-operator-anthropic",
    "TELEGRAM_BOT_TOKEN": "operator-telegram-token",
    "GATEWAY_ALLOWED_USERS": "operator-gateway-allowlist",
    "MODAL_TOKEN_SECRET": "operator-modal-secret",
    "GH_TOKEN": "operator-gh-token",
}


@pytest.fixture
def operator_env(monkeypatch):
    for key, value in _OPERATOR_SECRETS.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("WHATSAPP_ALLOWED_USERS", "15550001111")
    monkeypatch.setenv("WHATSAPP_MODE", "bot")


def test_bridge_env_drops_operator_credentials_keeps_bridge_config(operator_env):
    from plugins.platforms.whatsapp.adapter import WhatsAppAdapter

    adapter = WhatsAppAdapter(PlatformConfig(enabled=True, extra={"reply_prefix": "Bot: "}))
    env = adapter._bridge_env()

    leaked = sorted(k for k in _OPERATOR_SECRETS if k in env)
    assert leaked == []
    # What bridge.js reads is still delivered, including names the scrub blocklists for ordinary children.
    assert env["WHATSAPP_ALLOWED_USERS"] == "15550001111"
    assert env["WHATSAPP_MODE"] == "bot"
    assert env["WHATSAPP_REPLY_PREFIX"] == "Bot: "
    assert env["HERMES_IMAGE_CACHE_DIR"] and env["HERMES_DOCUMENT_CACHE_DIR"] and env["HERMES_AUDIO_CACHE_DIR"]
    assert env.get("PATH")


def test_bridge_env_keeps_inbound_webhook_and_spool_settings(operator_env, monkeypatch, tmp_path):
    from plugins.platforms.whatsapp.adapter import WhatsAppAdapter

    settings = {
        "WHATSAPP_INBOUND_WEBHOOK_URL": "https://ops.example/whatsapp/inbound",
        "WHATSAPP_INBOUND_WEBHOOK_NUMBERS_URL": "https://ops.example/whatsapp/numbers",
        "WHATSAPP_INBOUND_WEBHOOK_SECRET": "inbound-webhook-secret",
        "WHATSAPP_INBOUND_WHISPER_PYTHON": str(tmp_path / "venv" / "bin" / "python"),
        "WHATSAPP_INBOUND_WHISPER_MODEL": str(tmp_path / "model"),
        "WHATSAPP_BRIDGE_SPOOL_DIR": str(tmp_path / "spool"),
    }
    for key, value in settings.items():
        monkeypatch.setenv(key, value)

    env = WhatsAppAdapter(PlatformConfig(enabled=True))._bridge_env()

    assert {key: env.get(key) for key in settings} == settings
