"""Tests for the shared hardened `docker run` helper.

This file guards the sandbox itself: every plugin's isolation comes from the
flags assembled here, and until now nothing verified they actually reach the
command line. A silently dropped `--cap-drop=ALL` would leave every tool
running with full capabilities and no test would notice.

No Docker is involved — `create_subprocess_exec` is stubbed and the assertions
are about the argv that would have been executed.
"""

import asyncio

import pytest

from argustrace.plugins import _docker_runner
from argustrace.plugins._docker_runner import HARDENING_FLAGS, run_hardened


class FakeProcess:
    def __init__(self, stdout=b"", stderr=b"", returncode=0, hang=False):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self._hang = hang
        self.killed = False

    async def communicate(self):
        if self._hang:
            await asyncio.Event().wait()  # never resolves
        return self._stdout, self._stderr

    def kill(self):
        self.killed = True

    async def wait(self):
        return self.returncode


@pytest.fixture
def spy_exec(monkeypatch):
    """Capture the argv `run_hardened` would execute."""
    captured = {}

    def install(process=None, raises=None):
        async def _fake_exec(*cmd, **kwargs):
            captured["cmd"] = list(cmd)
            if raises is not None:
                raise raises
            return process if process is not None else FakeProcess()

        monkeypatch.setattr(_docker_runner.asyncio, "create_subprocess_exec", _fake_exec)
        return captured

    return install


async def test_every_hardening_flag_reaches_the_command_line(spy_exec):
    captured = spy_exec()
    await run_hardened("some-image:1.0", ["--arg"], timeout_s=10)

    cmd = captured["cmd"]
    for flag in HARDENING_FLAGS:
        assert flag in cmd, f"{flag!r} missing — the sandbox is weaker than it claims"


async def test_container_is_removed_and_image_and_args_are_last(spy_exec):
    captured = spy_exec()
    await run_hardened("some-image:1.0", ["a", "b"], timeout_s=10)

    cmd = captured["cmd"]
    assert cmd[:3] == ["docker", "run", "--rm"]
    # The image must come after every flag, otherwise docker parses our
    # hardening flags as arguments to the containerised tool.
    assert cmd[-3:] == ["some-image:1.0", "a", "b"]


async def test_optional_isolation_knobs_are_absent_by_default(spy_exec):
    captured = spy_exec()
    await run_hardened("img", [], timeout_s=10)

    cmd = captured["cmd"]
    assert "-v" not in cmd
    assert "-e" not in cmd
    assert not any(c.startswith("--network") for c in cmd)


async def test_volume_env_and_network_are_passed_when_given(spy_exec):
    captured = spy_exec()
    await run_hardened(
        "img", [], timeout_s=10,
        volume=("/host/dir", "/output"),
        env={"HOME": "/tmp"},
        network="none",
    )

    cmd = captured["cmd"]
    assert cmd[cmd.index("-v") + 1] == "/host/dir:/output"
    assert cmd[cmd.index("-e") + 1] == "HOME=/tmp"
    assert "--network=none" in cmd


async def test_missing_docker_is_reported_as_not_ok(spy_exec):
    spy_exec(raises=FileNotFoundError())
    result = await run_hardened("img", [], timeout_s=10)

    # ok=False is what makes plugins report ERROR rather than guessing a
    # negative result — the tri-state invariant depends on it.
    assert result.ok is False
    assert result.returncode is None
    assert "docker executable not found" in result.error


async def test_timeout_is_reported_as_not_ok_and_kills_the_client(spy_exec):
    process = FakeProcess(hang=True)
    spy_exec(process=process)

    result = await run_hardened("img", [], timeout_s=0)

    assert result.ok is False
    assert result.returncode is None
    assert "timed out" in result.error
    assert process.killed is True


async def test_successful_run_returns_streams_and_returncode(spy_exec):
    spy_exec(process=FakeProcess(stdout=b"out", stderr=b"err", returncode=0))
    result = await run_hardened("img", [], timeout_s=10)

    assert result.ok is True
    assert result.returncode == 0
    assert result.stdout == b"out"
    assert result.stderr == b"err"
    assert result.error is None


async def test_nonzero_exit_still_counts_as_a_completed_run(spy_exec):
    """ok=True means "the run completed"; the plugin decides what a non-zero
    exit means for its own tool (Maigret exits non-zero after a good scan)."""
    spy_exec(process=FakeProcess(stdout=b"", stderr=b"boom", returncode=1))
    result = await run_hardened("img", [], timeout_s=10)

    assert result.ok is True
    assert result.returncode == 1
