"""Isolation of the WhatsApp bridge from a privileged gateway (plugins/platforms/whatsapp/bridge_access.py)."""

import getpass
import os
import stat

from plugins.platforms.whatsapp import bridge_access


def test_media_dirs_point_every_cache_at_the_media_folder(tmp_path):
    dirs = bridge_access.media_dirs(str(tmp_path))
    assert dirs == {f"HERMES_{kind.upper()}_CACHE_DIR": str(tmp_path / kind) for kind in ("image", "audio", "document")}
    assert bridge_access.media_dirs("") == {}


def test_spooled_copy_lives_in_the_spool_and_goes_away(tmp_path):
    source = tmp_path / "out.png"
    source.write_bytes(b"png")
    spool = tmp_path / "spool"
    spool.mkdir()
    with bridge_access.spooled(str(source), str(spool)) as copy:
        assert os.path.dirname(copy) == str(spool)
        assert copy.endswith(".png")
        assert open(copy, "rb").read() == b"png"
        assert stat.S_IMODE(os.stat(copy).st_mode) == bridge_access.SPOOL_FILE_MODE
    assert not os.path.exists(copy)
    assert source.exists()


def test_spooled_without_spool_hands_the_file_itself(tmp_path):
    source = tmp_path / "out.png"
    source.write_bytes(b"png")
    with bridge_access.spooled(str(source), "") as path:
        assert path == str(source)


def test_popen_identity_drops_to_the_account_and_its_groups_only():
    assert bridge_access.popen_identity("") == {}
    identity = bridge_access.popen_identity(getpass.getuser())
    assert identity["user"] == os.getuid()
    assert identity["group"] == os.getgid()
    assert isinstance(identity["extra_groups"], list)


def test_pinned_token_stays_the_session_bearer_across_spawns(tmp_path):
    from plugins.platforms.whatsapp.adapter import _load_or_create_bridge_token, _read_bridge_token

    pinned = "p" * 64
    assert _load_or_create_bridge_token(tmp_path, pinned=pinned) == pinned
    assert _load_or_create_bridge_token(tmp_path, rotate=True, pinned=pinned) == pinned
    assert _read_bridge_token(tmp_path) == pinned
    assert _load_or_create_bridge_token(tmp_path, rotate=True) != pinned
