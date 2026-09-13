from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .models import ConflictError


def default_lock_path() -> Path:
    configured = os.environ.get("THINGS_AGENT_LOCK_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".local" / "state" / "things-agent-workflow" / "write.lock"


@contextmanager
def exclusive_write_lock(path: Path | None = None, timeout: float = 10.0) -> Iterator[None]:
    lock_path = path or default_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ConflictError(
                        "timed out waiting for another Things workflow write"
                    ) from None
                time.sleep(0.05)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
