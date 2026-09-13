from __future__ import annotations

import fcntl
from pathlib import Path

import pytest

from things_agent_workflow import locking
from things_agent_workflow.locking import default_lock_path, exclusive_write_lock
from things_agent_workflow.models import ConflictError


def test_default_lock_path_honors_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configured = tmp_path / "custom.lock"
    monkeypatch.setenv("THINGS_AGENT_LOCK_PATH", str(configured))
    assert default_lock_path() == configured

    monkeypatch.delenv("THINGS_AGENT_LOCK_PATH")
    monkeypatch.setattr(locking.Path, "home", lambda: tmp_path)
    assert default_lock_path() == tmp_path / ".local/state/things-agent-workflow/write.lock"


def test_exclusive_lock_creates_private_lock_file(tmp_path: Path) -> None:
    path = tmp_path / "state" / "write.lock"

    with exclusive_write_lock(path):
        assert path.exists()

    assert path.stat().st_mode & 0o777 == 0o600


def test_exclusive_lock_times_out_on_contention(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    times = iter([0.0, 2.0])

    def flock(_descriptor: int, operation: int) -> None:
        if operation == fcntl.LOCK_EX | fcntl.LOCK_NB:
            raise BlockingIOError

    monkeypatch.setattr(locking.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(locking.fcntl, "flock", flock)

    with pytest.raises(ConflictError, match="timed out"):
        with exclusive_write_lock(tmp_path / "write.lock", timeout=1):
            raise AssertionError("lock must not be acquired")
