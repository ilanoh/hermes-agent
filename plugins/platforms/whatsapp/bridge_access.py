"""Isolation of the Node.js bridge from the gateway process (counterpart: scripts/whatsapp-bridge/bridge_access.js).

The bridge listens on loopback, which every local account reaches, and ``/send-media`` reads the file a caller names.
When the gateway runs with privileges (a root ops gateway), these settings keep the bridge from lending them out:

    WHATSAPP_BRIDGE_TOKEN       bearer token the adapter sends and the bridge requires on every request
    WHATSAPP_BRIDGE_USER        Unix account the bridge runs as (POSIX, gateway started as root): ffmpeg runs as it too
    WHATSAPP_BRIDGE_SPOOL_DIR   folder each outgoing file is copied into before ``/send-media``, the only one the bridge
                                sends from; it should be owned by the gateway and group readable by the bridge account
    WHATSAPP_BRIDGE_MEDIA_DIR   folder the bridge account writes inbound media into (image/, audio/, document/), accepted
                                by the adapter next to its own cache folders
    WHATSAPP_BRIDGE_NODE        node executable the bridge account may run, when the managed one sits in a private home

Each unset setting keeps the previous behaviour.
"""

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

TOKEN_ENV = "WHATSAPP_BRIDGE_TOKEN"
USER_ENV = "WHATSAPP_BRIDGE_USER"
SPOOL_ENV = "WHATSAPP_BRIDGE_SPOOL_DIR"
MEDIA_ENV = "WHATSAPP_BRIDGE_MEDIA_DIR"
NODE_ENV = "WHATSAPP_BRIDGE_NODE"
MEDIA_KINDS = ("image", "audio", "document")
SPOOL_FILE_MODE = 0o640


def auth_headers(token: str) -> dict:
    """Headers for every bridge request: the bearer token when one is configured."""
    return {"Authorization": f"Bearer {token}"} if token else {}


def media_dirs(media_dir: str) -> dict:
    """Bridge env cache variables pointing at the bridge account's media folder, or {} when unset."""
    if not media_dir:
        return {}
    return {f"HERMES_{kind.upper()}_CACHE_DIR": str(Path(media_dir) / kind) for kind in MEDIA_KINDS}


def popen_identity(user: str) -> dict:
    """Popen keyword arguments that start the bridge as ``user`` with only that account's groups, or {} when unset."""
    if not user or os.name != "posix":
        return {}
    import grp
    import pwd
    account = pwd.getpwnam(user)
    groups = [g.gr_gid for g in grp.getgrall() if user in g.gr_mem]
    return {"user": account.pw_uid, "group": account.pw_gid, "extra_groups": groups}


def bridge_home(user: str) -> Optional[str]:
    """Home directory of the bridge account, for its HOME, or None when unset."""
    if not user or os.name != "posix":
        return None
    import pwd
    return pwd.getpwnam(user).pw_dir


@contextmanager
def spooled(file_path: str, spool_dir: str) -> Iterator[str]:
    """The path to hand to ``/send-media``: a copy inside the spool folder, removed afterwards, or the file itself."""
    if not spool_dir:
        yield file_path
        return
    suffix = Path(file_path).suffix
    handle, copy = tempfile.mkstemp(prefix="send-", suffix=suffix, dir=spool_dir)
    try:
        with os.fdopen(handle, "wb") as target, open(file_path, "rb") as source:
            shutil.copyfileobj(source, target)
        os.chmod(copy, SPOOL_FILE_MODE)
        yield copy
    finally:
        Path(copy).unlink(missing_ok=True)
